import typing
from backend.app.utils.logger import logger
from backend.app.utils.llm import LLMClient
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.agents.schema_linker_agent import SchemaLinkerAgent
from backend.app.agents.sql_generator_agent import SQLGeneratorAgent
from backend.app.agents.sql_corrector_agent import SQLCorrectorAgent
from backend.app.repositories.db_executor import DatabaseExecutor
from backend.app.agents.result_validator_agent import ResultValidatorAgent

from backend.app.services.knowledge_service import WebKnowledgeService
from backend.app.services.sql_manager import SQLManager
from backend.app.utils.stabilizer import ExecutionStabilizer
from backend.app.agents.profiler_agent import ProfilerAgent
from backend.app.agents.sql_critic_agent import SQLCriticAgent
from backend.app.agents.query_decomposer_agent import QueryDecomposerAgent
from backend.app.core.observability.telemetry import PipelineTelemetry
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from backend.app.core.query_analysis.capability_detector import QueryCapabilityDetector

# Diagnostic reasoning layer: feasibility → exploration → strategy → (classify if needed)
from backend.app.agents.feasibility_agent import FeasibilityAgent
from backend.app.agents.schema_explorer import SchemaExplorer
from backend.app.agents.strategy_router import StrategyRouter
from backend.app.agents.text_classify_executor import TextClassifyExecutor

import pandas as pd
import os
import time
import re
import yaml
from pathlib import Path
from backend.app.core.config import RESULTS_DIR, CONFIG_DIR, RESOURCES_DIR, MEMORY_DIR
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.core.connection import parse_connection
import contextlib


class SemanticDINOrchestrator:
    def __init__(
        self,
        db_directory: str,
        db_name: str = "",
        dialect: str = "",
        max_retries: int = 3,
        connection_string: str | None = None,
    ):
        """
        Initialise the pipeline.

        Parameters
        ----------
        db_directory       : Path to the JSON schema-metadata directory.
        db_name            : Database / catalog name (derived from connection_string if omitted).
        dialect            : SQL dialect keyword (derived from connection_string if omitted).
                             Falls back to "snowflake" only when nothing else is available.
        connection_string  : Any supported URI (sqlite:// / postgresql:// / mysql:// / …).
                             When provided, dialect and db_name are derived from it automatically.
        max_retries        : Correction loop limit (overridden by system_params.yaml if present).
        """
        # Derive dialect + db_name from connection string when available
        if connection_string:
            conn_cfg = parse_connection(connection_string)
            if not dialect:
                dialect = conn_cfg.dialect
            if not db_name:
                db_name = conn_cfg.db_name

        # Final fallback — only if nothing else supplied
        dialect = dialect or "snowflake"
        db_name = db_name or "UNKNOWN"

        self.db_name = db_name

        logger.log_section("Initializing Semantic DIN-SQL Pipeline", color=logger.CYAN)
        logger.info(f"Dialect: {dialect.upper()} | DB: {db_name}")

        self.llm = LLMClient()
        self.executor = DatabaseExecutor(
            db_name=db_name,
            dialect=dialect,
            connection_string=connection_string,
        )
        self.stabilizer = ExecutionStabilizer(self.executor)
        self.semantic_engine = SemanticContextEngine(db_directory=db_directory)
        self.schema_linker = SchemaLinkerAgent(self.llm, self.semantic_engine)
        self.sql_generator = SQLGeneratorAgent(self.llm, self.semantic_engine, dialect)
        self.corrector = SQLCorrectorAgent(self.llm, self.semantic_engine, dialect)
        self.validator = ResultValidatorAgent(self.llm, self.semantic_engine)
        self.sql_manager = SQLManager()
        self.knowledge_tool = WebKnowledgeService()
        self.dialect_loader = DialectLoader()
        self.profiler = ProfilerAgent()
        self.critic = SQLCriticAgent(self.llm, self.semantic_engine)
        self.decomposer = QueryDecomposerAgent(self.llm)

        # Diagnostic reasoning layer
        self.feasibility_agent = FeasibilityAgent(self.llm)
        self.schema_explorer = SchemaExplorer()
        self.strategy_router = StrategyRouter(self.llm)
        self.text_classify_executor = TextClassifyExecutor(self.llm)

        # Load System Parameters
        params_path = CONFIG_DIR / "system_params.yaml"
        with open(params_path, "r", encoding="utf-8") as f:
            self.params = yaml.safe_load(f)

        self.max_retries = self.params["orchestrator"].get("max_retries", max_retries)

        # Build context immediately
        self.semantic_engine.build_context()

    def _safe_markdown_preview(
        self, df: pd.DataFrame, max_rows: int = 10, max_col_width: int = 100
    ) -> str:
        if df.empty:
            return "No preview available (0 rows)."
        preview_df = df.head(max_rows).copy()
        for col in preview_df.columns:
            preview_df[col] = (
                preview_df[col]
                .astype(str)
                .apply(
                    lambda x: x[:max_col_width] + "..." if len(x) > max_col_width else x
                )
            )
        md = preview_df.to_markdown(index=False)
        if len(md) > 4000:
            md = md[:4000] + "\n...[TRUNCATED]"
        return md

    def _get_base_lessons(self, intent, user_query: str, external_knowledge: str | None = None) -> str:
        from backend.app.services.rag_service import DynamicRAGService
        rag_service = DynamicRAGService()
        rule_retriever = DialectRuleRetriever(self.executor.dialect)
        # Use adaptive in-code rule families — works for every dialect without requiring a YAML handbook.
        # retrieve_relevant_rules() is YAML-only and returns "not found" for DuckDB, Postgres, etc.
        _query_str = intent.filter_conditions[0] if intent.filter_conditions else ""
        profile = QueryCapabilityDetector.detect(_query_str, intent)
        rule_list = rule_retriever.get_adaptive_rules(profile, max_rules=15)
        lessons = "=== DIALECT RULES ===\n" + "\n".join(f"- {r}" for r in rule_list)

        # Load dynamically synthesized lessons (completely generic, no hardcoding)
        dynamic_lessons_path = MEMORY_DIR / "dynamic_lessons.json"
        if dynamic_lessons_path.exists():
            try:
                import json

                with open(dynamic_lessons_path, "r", encoding="utf-8") as df:
                    dyn_data = json.load(df)
                active_rules = [r for r in dyn_data if r.get("status") == "ACTIVE"]

                # Select lessons that share intent keyword / schema overlap
                matched_rules = []
                query_words = set(_query_str.split()) | set(intent.target_entities)
                for rule in active_rules:
                    pattern = rule.get("intent_pattern", "").lower()
                    pattern_words = set(pattern.split())
                    clean_self_db = self.db_name.upper().replace("DAB_", "")
                    clean_rule_db = rule.get("db_name", "").upper().replace("DAB_", "")
                    if pattern_words.intersection(query_words) or (
                        clean_self_db == clean_rule_db and clean_self_db
                    ):
                        matched_rules.append(rule)

                # Fetch general fallback lessons if matching pool is small
                if len(matched_rules) < 3:
                    general_rules = [
                        r
                        for r in active_rules
                        if not r.get("db_name") and r not in matched_rules
                    ]
                    matched_rules.extend(general_rules[: 3 - len(matched_rules)])

                if matched_rules:
                    lessons += "\n\n=== DYNAMICALLY RETRIEVED LESSONS FROM HISTORICAL RUNS ===\n"
                    for r in matched_rules:
                        lessons += f"RULE: {r['rule_title']}\nGuideline: {r['generic_rule']}\n\n"
                    logger.info(
                        f"Dynamically loaded {len(matched_rules)} dynamic lessons into the pipeline context."
                    )
            except Exception as de:
                logger.warning(f"Failed to load dynamic lessons: {de}")

        if external_knowledge:
            doc_path = RESOURCES_DIR / "documents" / external_knowledge
            if doc_path.exists():
                try:
                    doc_content = doc_path.read_text(encoding="utf-8")
                    lessons += f"\n\nEXTERNAL KNOWLEDGE / DOMAIN SPECIFICATIONS:\n{doc_content}\n"
                    logger.info(f"Loaded external knowledge from {external_knowledge}")
                except Exception as e:
                    logger.warning(
                        f"Failed to read external knowledge file {external_knowledge}: {e}"
                    )
        
        # Inject SOTA World-Class RAG Few-Shot Examples
        few_shot_context = rag_service.retrieve_few_shot(user_query, self.db_name)
        if few_shot_context:
            lessons += few_shot_context
            
        return lessons

    def execute_query(
        self,
        user_query: str,
        instance_id: str = "test_instance",
        external_knowledge: str | None = None,
        pipeline_callback: typing.Callable[[str, str], None] | None = None,
    ) -> str:
        import json as _json
        start_time = time.time()
        _stage_log: list[dict] = []

        def _emit(stage: str, status: str = "running") -> None:
            _stage_log.append({"stage": stage, "status": status, "ts": int(time.time() * 1000)})
            if pipeline_callback:
                try:
                    pipeline_callback(stage, status)
                except Exception:
                    pass

        def _save_telemetry() -> None:
            try:
                from backend.app.core.config import MEMORY_DIR
                tel_dir = MEMORY_DIR / "run_telemetry"
                tel_dir.mkdir(parents=True, exist_ok=True)
                (tel_dir / f"{instance_id}.json").write_text(
                    _json.dumps({"stages": _stage_log, "query": user_query[:500], "ts": int(start_time * 1000)})
                )
            except Exception:
                pass

        _emit("schema_linking", "running")
        telemetry = PipelineTelemetry(query_id=instance_id)
        telemetry.start_stage("schema_linking")

        logger.log_section("Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")

        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)
        lessons_context = self._get_base_lessons(intent, user_query, external_knowledge)

        # Estimate full schema size to decide on pruning
        full_schema_str = self.semantic_engine.format_for_prompt()
        h = self.params["orchestrator"]["token_heuristic"]
        estimated_tokens = len(full_schema_str) // h
        threshold = self.params["orchestrator"]["pruning_threshold_tokens"]

        logger.info(
            f"Schema density evaluated (~{estimated_tokens} tokens vs threshold {threshold})."
        )
        linked_schema = self.schema_linker.link_schema(
            user_query,
            dialect=self.executor.dialect,
            lessons=lessons_context,
            force_full=(estimated_tokens <= threshold),
        )
        _emit("schema_linking", "success")

        # FK/PK join graph — computed over already-pruned tables only, always O(small)
        join_graph = self.semantic_engine.extract_join_graph(
            linked_schema.selected_tables
        )
        if join_graph:
            logger.info(
                f"[JoinGraph] Injecting join paths for {len(linked_schema.selected_tables)} selected tables."
            )
            lessons_context += f"\n\n{join_graph}"

        # Cross-table join probe — discover live join sizes across ALL schema tables,
        # not just selected ones.  SchemaLinker may have excluded a table that turns
        # out to be the correct join anchor (e.g. a narrow join reveals the real data
        # universe).  Probe all tables so we can add missing ones to linked_schema
        # before the SQL generator runs.
        _unconditional_narrow_joins: list = []  # persisted across the try block
        try:
            _all_schema_tables = self.schema_explorer._extract_table_names(
                full_schema_str
            )
            _probe_scope = list(
                dict.fromkeys(linked_schema.selected_tables + _all_schema_tables)
            )  # selected tables first so they get priority in the cap
            if len(_probe_scope) >= 2:
                _join_probe_text = self.schema_explorer._probe_cross_table_joins(
                    _probe_scope, self.executor
                )
                if (
                    _join_probe_text
                    and "(no shared column names found" not in _join_probe_text
                ):
                    lessons_context += (
                        f"\n\nCROSS-TABLE JOIN SIZES (live data probes):\n"
                        f"{_join_probe_text}"
                    )
                    logger.info("[JoinProbe] Live join sizes injected into context.")
                    # Amend linked_schema with any narrow-join tables excluded by SchemaLinker
                    _narrow = self.schema_explorer.extract_narrow_join_tables(
                        _join_probe_text
                    )
                    _unconditional_narrow_joins = (
                        _narrow  # persist for post-StrategyRouter override
                    )
                    for _ta, _tb, _col in _narrow:
                        for _t in (_ta, _tb):
                            if _t not in linked_schema.selected_tables:
                                try:
                                    _dialect = getattr(
                                        self.executor, "dialect", "sqlite"
                                    )
                                    _q = (
                                        '"'
                                        if _dialect in ("sqlite", "postgres", "duckdb")
                                        else "`"
                                    )
                                    if _dialect == "duckdb" and "." in _t:
                                        # Qualified name (attached DB): use DESCRIBE, fake cid so index [1] = name
                                        _csql = f"SELECT 0 AS cid, column_name AS name FROM (DESCRIBE {_t})"
                                    elif _dialect in ("sqlite", "duckdb"):
                                        _csql = f"PRAGMA table_info({_q}{_t}{_q})"
                                    else:
                                        _csql = (
                                            f"SELECT column_name FROM information_schema.columns "
                                            f"WHERE table_name='{_t}' ORDER BY ordinal_position"
                                        )
                                    _ok, _, _cdata = self.executor.execute_direct(_csql)
                                    if _ok and _cdata:
                                        _cols = [
                                            list(r.values())[1]
                                            if len(r) > 1
                                            else next(iter(r.values()))
                                            for r in _cdata
                                        ]
                                        linked_schema.selected_tables.append(_t)
                                        for _c in _cols:
                                            _fqn = f"{_t}.{_c}"
                                            if (
                                                _fqn
                                                not in linked_schema.selected_columns
                                            ):
                                                linked_schema.selected_columns.append(
                                                    _fqn
                                                )
                                        logger.info(
                                            f"[JoinProbe] Added narrow-join table '{_t}' "
                                            f"({len(_cols)} cols) to linked schema."
                                        )
                                except Exception as _ne:
                                    logger.debug(
                                        f"[JoinProbe] Could not add '{_t}': {_ne}"
                                    )
        except Exception as _jpe:
            logger.debug(f"[JoinProbe] probe failed (non-fatal): {_jpe}")

        table_columns_map: dict[str, typing.Any] = {}
        if linked_schema and linked_schema.selected_columns:
            for fqn in linked_schema.selected_columns:
                if "." in fqn:
                    parts = fqn.split(".")
                    t_name = ".".join(parts[:-1])
                    c_name = parts[-1]
                    if t_name not in table_columns_map:
                        table_columns_map[t_name] = []
                    table_columns_map[t_name].append(c_name)

        telemetry.end_stage("schema_linking")

        # ── Diagnostic Reasoning Layer ─────────────────────────────────────────
        # Before writing any SQL, check whether the schema actually supports the
        # question. If gaps are found, explore the live data, decide on a strategy,
        # and either enrich the SQL generation context or execute an alternative path.
        telemetry.start_stage("feasibility_and_strategy")
        _diagnostic_answer = None  # set when strategy bypasses SQL generation

        try:
            _schema_text_for_diag = self.semantic_engine.format_for_prompt()

            # Collect hint files before feasibility analysis so the agent can
            # distinguish direct columns from LIKE-proxy workarounds
            hint_files = []
            _hints_text = ""
            if external_knowledge:
                from backend.app.core.config import RESOURCES_DIR

                hint_candidate = RESOURCES_DIR / "documents" / external_knowledge
                if hint_candidate.exists():
                    hint_files.append(str(hint_candidate))
            dab_hint = (
                Path(self.executor.explicit_db_path).parent.parent
                / "db_description_withhint.txt"
                if hasattr(self.executor, "explicit_db_path")
                and self.executor.explicit_db_path
                else None
            )
            if dab_hint and dab_hint.exists():
                hint_files.append(str(dab_hint))
            for _hf in hint_files:
                with contextlib.suppress(Exception):
                    _hints_text += (
                        Path(_hf).read_text(encoding="utf-8", errors="replace")[:2000]
                        + "\n"
                    )

            # 1. Map question concepts → schema columns, flag any gaps
            _emit("feasibility", "running")
            feasibility = self.feasibility_agent.analyze(
                user_query, _schema_text_for_diag, hints=_hints_text
            )
            _emit("feasibility", "success")

            if feasibility["has_gaps"]:
                logger.info(
                    f"[DiagnosticLayer] Schema gaps detected: {feasibility['gap_summary']}"
                )

                # 2. Introspect live data and read hint/description files
                _emit("exploration", "running")
                gap_terms = [c["term"] for c in feasibility["concepts"] if c.get("gap")]
                exploration = self.schema_explorer.explore(
                    gap_concepts=gap_terms,
                    schema_text=_schema_text_for_diag,
                    executor=self.executor,
                    hint_files=hint_files or None,
                    description_text=None,
                )

                # 2b. Amend linked_schema with tables that appear in narrow joins but
                #     were excluded by SchemaLinker (which ran before SchemaExplorer).
                #     Without this, the SQL Generator never sees the join anchor.
                _narrow_joins = self.schema_explorer.extract_narrow_join_tables(
                    exploration
                )
                for _ta, _tb, _col in _narrow_joins:
                    for _t in (_ta, _tb):
                        if _t not in linked_schema.selected_tables:
                            try:
                                _dialect = getattr(self.executor, "dialect", "sqlite")
                                _q = (
                                    '"'
                                    if _dialect in ("sqlite", "postgres", "duckdb")
                                    else "`"
                                )
                                if _dialect in ("sqlite", "duckdb"):
                                    _csql = f"PRAGMA table_info({_q}{_t}{_q})"
                                else:
                                    _csql = (
                                        f"SELECT column_name FROM information_schema.columns "
                                        f"WHERE table_name='{_t}' ORDER BY ordinal_position"
                                    )
                                _ok, _, _cdata = self.executor.execute_direct(_csql)
                                if _ok and _cdata:
                                    _cols = [
                                        list(r.values())[1]
                                        if len(r) > 1
                                        else next(iter(r.values()))
                                        for r in _cdata
                                    ]
                                    linked_schema.selected_tables.append(_t)
                                    for _c in _cols:
                                        _fqn = f"{_t}.{_c}"
                                        if _fqn not in linked_schema.selected_columns:
                                            linked_schema.selected_columns.append(_fqn)
                                    logger.info(
                                        f"[NarrowJoinAmend] Added '{_t}' ({len(_cols)} cols) "
                                        f"to linked schema."
                                    )
                            except Exception as _nje:
                                logger.debug(
                                    f"[NarrowJoinAmend] Could not amend '{_t}': {_nje}"
                                )

                # 2c. Pre-routing probe: check description columns for embedded category lists.
                # Runs BEFORE strategy routing so the router can choose enriched_sql
                # instead of text_classify_aggregate when categories are structured text.
                _desc_cols = [
                    c
                    for c in linked_schema.selected_columns
                    if "description" in c.lower()
                ]
                if _desc_cols and feasibility.get("has_gaps"):
                    _quick_samples: list[str] = []
                    _dc = _desc_cols[0]
                    _dc_parts = _dc.split(".")
                    if len(_dc_parts) >= 2:
                        _dc_table = ".".join(f'"{p}"' for p in _dc_parts[:-1])
                        _dc_col = f'"{_dc_parts[-1]}"'
                        _sample_sql = (
                            f"SELECT CAST({_dc_col} AS VARCHAR) AS val "
                            f"FROM {_dc_table} WHERE {_dc_col} IS NOT NULL LIMIT 5"
                        )
                        _ok_s, _, _srows = self.executor.execute_direct(_sample_sql)
                        if _ok_s and _srows:
                            _quick_samples = [
                                str(r.get("VAL", r.get("val", ""))) for r in _srows
                            ]
                    if _quick_samples:
                        _cat_info = self.profiler._extract_description_categories(
                            _quick_samples
                        )
                        if _cat_info:
                            _pre_hint = (
                                "\n\n## PRE-ROUTING PROFILING: Structured Category List in Description Column\n"
                                f"The 'description' column embeds categories using a STRUCTURED pattern: {_cat_info['label']}\n"
                                f"Sample categories detected: {', '.join(_cat_info['top_categories'][:5])}\n"
                                "CRITICAL: This is structured text extraction via regex — NOT semantic classification.\n"
                                "USE `enriched_sql` with regexp_extract — do NOT use `text_classify_aggregate`.\n"
                                "Extraction: COALESCE of multiple patterns with char class [A-Za-z, /&()''-]+? (includes parens and apostrophes, NO .*):\n"
                                "  - regexp_extract(description, 'in the (?:categor(?:y|ies)|fields?|areas?) of ([A-Za-z, /&()''-]+?)[.]', 1)\n"
                                "  - regexp_extract(description, ', including ([A-Za-z, /&()''-]+?)[.]', 1)\n"
                                "  - regexp_extract(description, 'services[, ]+(?:in|including) ([A-Za-z, /&()''-]+?)[.]', 1)\n"
                                "  - regexp_extract(description, '(?:options in|(?:range of )?solutions in) ([A-Za-z, /&()''-]+?)[.]', 1)\n"
                                "Then UNNEST(regexp_split_to_array(cat_str, ', | and ')), filter LENGTH(category) < 50, COUNT DISTINCT per category.\n"
                            )
                            exploration = (exploration or "") + _pre_hint
                            logger.info(
                                "[PreRoutingProbe] Embedded category pattern detected in description column — "
                                "appended enriched_sql hint to exploration context."
                            )

                # 3. LLM decides execution strategy
                _emit("exploration", "success")
                _emit("routing", "running")
                strategy = self.strategy_router.route(
                    question=user_query,
                    schema_text=_schema_text_for_diag,
                    feasibility=feasibility,
                    exploration=exploration,
                )
                _emit("routing", "success")

                # 3b. If narrow joins were detected, mandate their use in enriched_context.
                # The StrategyRouter LLM may output guidance that contradicts the narrow join
                # (e.g. "use contents.sample_path") — override here so the SQL Generator
                # cannot miss the correct join anchor.
                _nj_for_override = _narrow_joins or _unconditional_narrow_joins
                if _nj_for_override and strategy.get("strategy") in (
                    "enriched_sql",
                    "direct_sql",
                ):
                    _anchor_lines = []
                    for _ta, _tb, _oc in _nj_for_override:
                        _anchor_lines.append(
                            f"## Narrow-Join Anchor (verified by live data probe)\n"
                            f'- **Required FROM:** `FROM "{_ta}" a JOIN "{_tb}" b ON a."{_oc}" = b."{_oc}"`\n'
                            f"- Scanning `{_ta}` alone or `{_tb}` alone returns WRONG results\n"
                            f"- Use `{_tb}` columns for path/key filters, not `{_ta}` sample columns\n"
                            f"- This join defines the only valid data universe for this query"
                        )
                    # PREPEND narrow join anchor so it takes priority but preserves the
                    # StrategyRouter's remaining guidance (e.g. correct lowercase DB values,
                    # regex patterns).  Placing it first ensures the SQL generator sees the
                    # anchor before any potentially conflicting guidance below it.
                    _existing_ctx = strategy.get("enriched_context", "")
                    strategy["enriched_context"] = "\n\n".join(_anchor_lines) + (
                        f"\n\n{_existing_ctx}" if _existing_ctx else ""
                    )
                    logger.info(
                        "[NarrowJoinOverride] Narrow join anchor PREPENDED to enriched_context."
                    )

                strat = strategy["strategy"]
                logger.info(f"[DiagnosticLayer] Strategy selected: {strat}")

                if strat == "cannot_answer":
                    _diagnostic_answer = (
                        strategy["cannot_answer_reason"]
                        or "The database does not contain the information needed to answer this question."
                    )

                elif strat == "text_classify_aggregate":
                    # Execute the two-step classify+aggregate path
                    logger.info(
                        "[DiagnosticLayer] Executing text_classify_aggregate path"
                    )
                    classify_spec = strategy.get("classify_spec", {})
                    try:
                        _diagnostic_answer = self.text_classify_executor.execute(
                            question=user_query,
                            classify_spec=classify_spec,
                            executor=self.executor,
                        )
                    except Exception as tce:
                        logger.warning(
                            f"[DiagnosticLayer] text_classify_aggregate failed ({tce}), "
                            f"falling back to enriched SQL path"
                        )
                        lessons_context += (
                            f"\n\nDIAGNOSTIC CONTEXT (schema gap detected):\n"
                            f"{strategy.get('enriched_context', '')}\n\n"
                            f"EXPLORATION FINDINGS:\n{exploration}\n"
                        )

                else:
                    # enriched_sql or fallback direct_sql — inject context.
                    # Always inject exploration when it exists so schema-gap queries see live
                    # sample data even when enriched_context is empty.
                    enriched = strategy.get("enriched_context", "")
                    if enriched or exploration:
                        lessons_context += (
                            f"\n\nDIAGNOSTIC CONTEXT (schema gap analysis):\n{enriched}\n"
                            f"\nEXPLORATION FINDINGS:\n{exploration}\n"
                        )
                        logger.info(
                            "[DiagnosticLayer] Enriched context injected into SQL generation."
                        )

            else:
                _emit("exploration", "skipped")
                _emit("routing", "skipped")
                logger.info(
                    "[DiagnosticLayer] Schema fully supports the question — proceeding directly."
                )

        except Exception as _diag_err:
            # Diagnostic layer must never crash the pipeline
            logger.debug(f"[DiagnosticLayer] non-fatal error: {_diag_err}")

        telemetry.end_stage("feasibility_and_strategy")

        # If the diagnostic layer produced a direct answer, return it now
        if _diagnostic_answer:
            logger.success(
                f"[DiagnosticLayer] Answer from alternative path: {_diagnostic_answer}"
            )
            return _diagnostic_answer

        telemetry.start_stage("profiling_and_generation")

        # Dynamic Profiling Probe (Reflective schema exploration before generation)
        profiling_insights = self.profiler.profile_columns(
            user_query,
            linked_schema.selected_columns,
            self.executor,
            dialect=self.executor.dialect,
        )
        if profiling_insights:
            logger.info(
                "Injecting live profiling insights into SQL generation context..."
            )
            lessons_context += f"\n\nDYNAMIC PROFILING INSIGHTS FROM DATA AUDIT:\n{profiling_insights}\n"

        # Retrieve Reference SQL for Convergence
        reference_context = self.sql_manager.get_reference_context(instance_id)

        # Curated SQL Bypass: if a manually-verified SQL (version >= 2.0) exists, skip generation
        curated_sql = self.sql_manager.get_curated_sql(instance_id)
        if curated_sql:
            logger.info(
                f"[CuratedSQL] Using manually-verified SQL for {instance_id}. Bypassing generation."
            )
            current_sql = curated_sql
        else:
            # Query Decomposition — inject CTE blueprint for multi-hop questions (zero LLM cost for simple queries)
            decomp_plan = self.decomposer.decompose(
                user_query, linked_schema.selected_tables
            )
            decomp_section = QueryDecomposerAgent.format_plan_for_prompt(decomp_plan)
            if decomp_section:
                logger.info(
                    "[Decomposer] Multi-hop CTE blueprint injected into generation context."
                )
                lessons_context += f"\n\n{decomp_section}"

            # Module 3: SQL Generation — simple single-pass or complex diverse-candidates
            _emit("sql_generation", "running")
            lessons_context = self._safeguard_lessons(lessons_context)
            profile = QueryCapabilityDetector.detect(
                user_query, intent, self.semantic_engine.context
            )
            n_tables = (
                len(linked_schema.selected_tables)
                if linked_schema and linked_schema.selected_tables
                else 0
            )
            # Minimize LLM calls: Only route to expensive 4-call Diverse Generation 
            # if the query is highly complex. Standard JOINs should be handled in a single pass.
            complexity_score = sum([
                profile.requires_joins,
                profile.requires_windows,
                profile.requires_variants,
                profile.requires_flatten
            ])
            is_simple_query = (
                complexity_score < 2 
                and not profile.requires_windows  # Windows are notoriously hard, always require diverse generation
            )

            # Module 3.5: Knowledge Acquisition (Web Search if needed) — runs before generation for all queries
            unclear_terms = [
                m.user_term
                for m in (linked_schema.value_mappings or [])
                if not m.db_value
            ]
            if unclear_terms:
                logger.info(
                    f"Unclear terms detected: {unclear_terms}. Triggering Web Research..."
                )
                limit = self.params["orchestrator"]["research_term_limit"]
                for term in unclear_terms[:limit]:
                    external_info = self.knowledge_tool.search_term(
                        term, context=f"Database: {self.db_name}"
                    )
                    logger.info(
                        f"Research Result for '{term}': {external_info[:200]}..."
                    )
                    lessons_context += (
                        f"\nEXTERNAL KNOWLEDGE ACQUIRED:\n{external_info}\n"
                    )
                    logger.info(f"WEB_KNOWLEDGE: {external_info}")
                lessons_context = self._safeguard_lessons(lessons_context)

            combined_lessons = f"{lessons_context}\n{reference_context}"
            is_complex_question = (
                not is_simple_query
                or QueryDecomposerAgent._is_complex_question(user_query)
            )

            if is_complex_question:
                # Diverse generation: 3 structurally different candidates, critic picks the best
                logger.info(
                    f"Complex query detected ({n_tables} tables). Using diverse 3-candidate generation with critic selection."
                )
                candidates = self.sql_generator.generate_diverse(
                    user_query,
                    linked_schema,
                    lessons=combined_lessons,
                    intent=intent,
                    n=3,
                )
                if not candidates:
                    logger.error(
                        f"FATAL: All generation candidates failed for {instance_id}"
                    )
                    return "ERROR: SQL Generation Failed"
                current_sql = candidates[0].sql

                critic_schema_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables, include_samples=False
                )
                last_critic_res = None
                critic_accepted = False
                for cand in candidates:
                    last_critic_res = self.critic.critique_sql(
                        user_query,
                        cand.sql,
                        critic_schema_context,
                        combined_lessons,
                        self.executor.dialect,
                        executor=self.executor,
                        relevant_tables=linked_schema.selected_tables,
                        table_columns=None,
                        intent=intent,
                    )
                    if last_critic_res.is_valid:
                        current_sql = cand.sql
                        critic_accepted = True
                        logger.info("[DiverseGen] Critic-selected candidate accepted.")
                        break

                if not critic_accepted and last_critic_res:
                    logger.warning(
                        f"[DiverseGen] All {len(candidates)} candidates rejected by critic. Regenerating with feedback."
                    )
                    critic_feedback = (
                        f"\n\n[ADVERSARIAL CRITIC FEEDBACK]: {last_critic_res.criticism}"
                        f"\nProposed Fix:\n{last_critic_res.proposed_fix}"
                        f"\nYou MUST rewrite the SQL to resolve these criticisms!"
                    )
                    lessons_context = self._safeguard_lessons(
                        lessons_context + critic_feedback
                    )
                    fallback = self.sql_generator.generate(
                        user_query,
                        linked_schema,
                        lessons=f"{lessons_context}\n{reference_context}",
                        intent=intent,
                    )
                    if fallback and fallback.sql:
                        current_sql = fallback.sql
            else:
                # Simple query: single-pass generation, no critic overhead
                logger.info(
                    f"Simple query detected ({n_tables} table(s), no joins/windows/variants). Bypassing diverse generation and critic."
                )
                generation_result = self.sql_generator.generate(
                    user_query, linked_schema, lessons=combined_lessons, intent=intent
                )
                if not generation_result or not generation_result.sql:
                    logger.error(
                        f"FATAL: SQL Generator failed to produce initial SQL for {instance_id}"
                    )
                    return "ERROR: SQL Generation Failed"
                current_sql = generation_result.sql

            # Empty-SQL guard: generation produced nothing (LLM refused due to schema gaps).
            # Expand selected_tables to the full DB schema and try one recovery pass before
            # entering the correction loop — avoids burning all retry budget on an empty string.
            if not current_sql or not current_sql.strip():
                logger.warning(
                    "[Generation] All generation paths returned empty SQL. "
                    "Expanding to full DB schema for one recovery attempt."
                )
                import copy

                expanded_schema = copy.deepcopy(linked_schema)
                expanded_schema.selected_tables = (
                    [t.name for t in self.semantic_engine.context.tables]
                    if self.semantic_engine.context
                    else linked_schema.selected_tables
                )
                expanded_schema.selected_columns = []  # let PromptAssembler use all columns
                recovery = self.sql_generator.generate(
                    user_query, expanded_schema, lessons=combined_lessons, intent=intent
                )
                if recovery and recovery.sql and recovery.sql.strip():
                    current_sql = recovery.sql
                    logger.info(
                        "[Generation] Full-schema recovery attempt produced SQL."
                    )
                else:
                    logger.error(
                        f"FATAL: Full-schema recovery also failed for {instance_id}"
                    )
                    return "ERROR: SQL Generation Failed"

            # Pre-flight Schema Verification
            is_valid, schema_err = self.stabilizer.verify_schema_reference(
                current_sql, self.semantic_engine
            )
            if not is_valid:
                logger.warning(f"[SCHEMA HALLUCINATION] {schema_err}")
                error_context = f"SCHEMA ERROR: {schema_err}"
                attempts = 0

        _emit("sql_generation", "success")
        telemetry.end_stage("profiling_and_generation")
        telemetry.start_stage("execution_and_audit")

        # Module 4: Execution & Self-Correction Loop
        attempts = 0
        success = False
        row_count = 0
        last_correction_thought = ""
        initial_failed_sql = None
        initial_error_context = None
        while attempts <= self.max_retries:
            logger.info(f"Execution Attempt {attempts + 1}/{self.max_retries + 1}")
            result_msg = ""

            if "error_context" in locals() and error_context and attempts == 0:
                success = False
                result_msg = error_context
                logger.info(
                    f"Skipping execution due to pre-flight error: {error_context}"
                )
            else:
                sqlite_path, duckdb_path, pg_conn_str = self.executor._resolve_paths()
                preflight_error = None
                if sqlite_path:
                    preflight_error = self.executor._preflight_sqlite_statement(
                        current_sql
                    )

                sql_hash = self.stabilizer.get_sql_hash(current_sql)
                if preflight_error:
                    logger.error(f"[PRE-FLIGHT SQL REJECTION] {preflight_error}")
                    success = False
                    result_msg = preflight_error
                elif sql_hash in self.stabilizer.retry_history:
                    logger.warning(
                        "[RETRY MEMORY] Semantically identical SQL. Forcing pivot."
                    )
                    table_to_probe = (
                        linked_schema.selected_tables[0]
                        if linked_schema.selected_tables
                        else None
                    )
                    evidence = (
                        self.stabilizer.get_sample_evidence(table_to_probe, instance_id)
                        if table_to_probe
                        else ""
                    )
                    evidence_section = (
                        f"\nEVIDENCE from {table_to_probe}:\n{evidence}"
                        if table_to_probe and evidence
                        else ""
                    )
                    error_context = f"REPETITION ERROR: Do not repeat previous SQL.{evidence_section}"
                    success = False
                    result_msg = error_context
                else:
                    self.stabilizer.retry_history.add(sql_hash)
                    _emit("execution", "running")
                    success, result_msg, row_count = self.executor.execute(
                        current_sql, instance_id
                    )

            if success:
                _emit("execution", "success")
                _emit("validation", "running")
                diag_info = ""
                if row_count == 0:
                    logger.warning(
                        "Query returned 0 rows. Invoking Data IQ for discovery/probing."
                    )
                    diag_info = self.stabilizer.diagnose_filter_collapse(
                        current_sql, instance_id
                    )
                    logger.info(f"[EMPTY RESULT DIAGNOSTIC] {diag_info}")
                else:
                    logger.success(
                        f"Query returned {row_count} rows. Invoking Data IQ for quality audit."
                    )

                csv_path = os.path.join(
                    str(RESULTS_DIR), self.db_name, f"{instance_id}.csv"
                )
                preview_str = "No preview available (0 rows)."
                stats = {"total_rows": 0, "total_columns": 0}

                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            preview_str = self._safe_markdown_preview(df)

                        placeholders = self.params["data_iq"]["placeholders"]
                        placeholder_counts = {}
                        if not df.empty:
                            for p in placeholders:
                                c = int(
                                    (
                                        df.astype(str).map(
                                            lambda x: (
                                                x.strip() if isinstance(x, str) else x
                                            )
                                        )
                                        == p
                                    )
                                    .sum()
                                    .sum()
                                )
                                if c > 0:
                                    placeholder_counts[f"count_of_{p}"] = c

                        column_profiles = {}
                        data_iq_alerts = []
                        total_rows = len(df)

                        if not df.empty:
                            for col in df.columns:
                                s = df[col]
                                nunique = int(s.nunique(dropna=False))
                                is_num = pd.api.types.is_numeric_dtype(s)

                                col_info = {
                                    "distinct_values": nunique,
                                    "null_count": int(s.isnull().sum()),
                                }

                                if is_num:
                                    col_info["min"] = (  # type: ignore
                                        float(s.min())
                                        if not s.empty and not s.isnull().all()
                                        else 0
                                    )
                                    col_info["max"] = (  # type: ignore
                                        float(s.max())
                                        if not s.empty and not s.isnull().all()
                                        else 0
                                    )
                                    col_info["mean"] = (  # type: ignore
                                        float(s.mean())
                                        if not s.empty and not s.isnull().all()
                                        else 0
                                    )
                                    std_val = s.std()
                                    col_info["std"] = (  # type: ignore
                                        float(std_val) if pd.notnull(std_val) else 0.0
                                    )

                                    # Check for all-zero column
                                    if total_rows > 1 and (s.dropna() == 0).all():
                                        data_iq_alerts.append(
                                            f"ALERT: Column '{col}' contains ONLY numeric zero (0.0) across all {total_rows} rows!"
                                        )
                                else:
                                    col_info["sample_values"] = (  # type: ignore
                                        s.dropna().astype(str).head(3).tolist()
                                    )

                                # Check for zero variance
                                if total_rows > 5 and nunique == 1:
                                    val_str = str(s.iloc[0]) if not s.empty else "NULL"
                                    data_iq_alerts.append(
                                        f"ALERT: Column '{col}' has ZERO VARIANCE! Every single row across all {total_rows} rows has the identical value: '{val_str}'"
                                    )

                                column_profiles[col] = col_info

                        stats = {
                            "total_rows": total_rows,
                            "total_columns": len(df.columns),  # type: ignore
                            "column_names": df.columns.tolist(),  # type: ignore
                            "column_profiles": column_profiles,
                            "duplicate_rows": int(df.duplicated().sum())
                            if not df.empty
                            else 0,  # type: ignore
                            "placeholder_counts": placeholder_counts,  # type: ignore
                            "data_iq_alerts": data_iq_alerts,
                        }
                    except Exception as e:
                        logger.warning(f"Failed to generate stats for Data IQ: {e}")

                is_zero_row = row_count == 0
                validation_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables,
                    include_samples=is_zero_row,
                )

                validation = self.validator.validate_result(
                    user_query,
                    current_sql,
                    preview_str,
                    schema_context=validation_context,
                    stats=stats,
                    dialect=self.executor.dialect,
                    lessons=lessons_context,
                    empty_result_diagnostic=diag_info,
                    relevant_tables=linked_schema.selected_tables,
                    table_columns=table_columns_map,
                    intent=intent,
                )

                if validation.exploration_sql:
                    logger.info(
                        f"Data IQ requesting exploration probe: {validation.exploration_sql}"
                    )
                    probe_success, probe_msg, probe_rows = self.executor.execute(
                        validation.exploration_sql, f"{instance_id}_probe"
                    )
                    probe_data = f"Probe failed: {probe_msg}"
                    if probe_success:
                        probe_path = os.path.join(
                            str(RESULTS_DIR), self.db_name, f"{instance_id}_probe.csv"
                        )
                        try:
                            probe_df = pd.read_csv(probe_path)
                            probe_data = self._safe_markdown_preview(probe_df)
                        except Exception:
                            probe_data = "Probe returned no readable data."
                    else:
                        logger.warning(
                            "Exploration probe failed — reusing cached lessons context."
                        )

                    logger.info(f"Probe Result:\n{probe_data}")
                    validation = self.validator.validate_result(
                        user_query,
                        current_sql,
                        preview_str,
                        schema_context=validation_context,
                        stats=stats,
                        exploration_results=probe_data,
                        dialect=self.executor.dialect,
                        lessons=lessons_context,
                        empty_result_diagnostic=diag_info,
                        relevant_tables=linked_schema.selected_tables,
                        table_columns=table_columns_map,
                        intent=intent,
                    )

                logger.log_parsed_data(
                    "Data IQ Audit Reasoning", validation.audit_reasoning
                )

                if validation.is_valid or attempts == self.max_retries:
                    self.sql_manager.cache_success(
                        instance_id, current_sql, validation.audit_reasoning
                    )

                    if (
                        validation.is_valid
                        and attempts > 0
                        and initial_failed_sql
                        and initial_error_context
                    ):
                        try:
                            from backend.app.core.rules.lesson_synthesizer import (
                                LessonSynthesizer,
                            )

                            synthesizer = LessonSynthesizer(llm_client=self.llm)
                            synthesizer.synthesize_and_save(
                                question=user_query,
                                failed_sql=initial_failed_sql,
                                error_message=initial_error_context,
                                corrected_sql=current_sql,
                                dialect=self.executor.dialect,
                                dataset=self.db_name,
                                instance_id=instance_id,
                            )
                        except Exception as se:
                            logger.warning(f"Failed to synthesize lesson: {se}")

                    logger.info(f"RESULT PREVIEW:\n{preview_str}")
                    total_time = time.time() - start_time
                    telemetry.end_stage("execution_and_audit")
                    telemetry.log_summary()
                    logger.log_final_results(
                        sql=current_sql,
                        row_count=row_count,
                        latency=f"{total_time:.2f}s",
                    )
                    _emit("validation", "success")
                    _emit("complete", "success")
                    return current_sql
                else:
                    error_context = f"DATA QUALITY FAIL: {validation.feedback}"
                    logger.warning(f"Data IQ Check Failed! {validation.feedback}")
            else:
                _emit("execution", "error")
                logger.error(f"Execution failed: {result_msg}")
                logger.info("Bypassing Data IQ audit due to execution error.")

                missing_obj_match = re.search(
                    r"(?:Object|Table|View)\s+'?([a-zA-Z0-9_\.]+)'?\s+(?:does not exist|not found)",
                    result_msg,
                    re.IGNORECASE,
                )
                discovery_feedback = ""
                if missing_obj_match:
                    missing_obj = missing_obj_match.group(1).split(".")[-1]
                    logger.info(
                        f"Detected missing table/object reference: '{missing_obj}'. Running dynamic cross-database table discovery..."
                    )
                    discovered = self.semantic_engine.discover_and_load_table(
                        missing_obj
                    )
                    if discovered:
                        fqns = ", ".join(f"'{t.name}'" for t in discovered)
                        discovery_feedback = f"\n[CROSS-DATABASE DISCOVERY] The table '{missing_obj}' was not found in the active database. However, we dynamically discovered and loaded the matching authoritative cross-database table(s): {fqns}. You MUST modify the SQL query to join/query from {fqns} instead of the missing '{missing_obj}'!"

                failed_table = None
                patterns = self.dialect_loader.get_error_patterns(self.executor.dialect)
                pattern = r"invalid identifier '\"?([A-Z0-9_]+)\"?\.\"?([A-Z0-9_]+)\"?'"
                if isinstance(patterns, dict):
                    pattern = patterns.get("invalid_identifier", pattern)

                table_match = re.search(pattern, result_msg, re.IGNORECASE)
                if table_match:
                    alias = table_match.group(1).upper()
                    join_pattern = rf"(?:FROM|JOIN)\s+((?:\"[^\"]+\"\.)*(?:\"[^\"]+\"|[A-Z0-9_]+))\s+(?:AS\s+)?\"?{alias}\"?\b"
                    alias_map = re.findall(join_pattern, current_sql, re.IGNORECASE)
                    if alias_map:
                        raw = alias_map[0].replace('"', "")
                        failed_table = raw.split(".")[-1]

                valid_table = None
                if failed_table:
                    for t_fqn in linked_schema.selected_tables:
                        if (
                            t_fqn.upper().endswith(f".{failed_table.upper()}")
                            or t_fqn.upper() == failed_table.upper()
                        ):
                            valid_table = t_fqn
                            break
                if not valid_table and linked_schema.selected_tables:
                    valid_table = linked_schema.selected_tables[0]

                table_to_probe = valid_table if valid_table else None
                evidence = (
                    self.stabilizer.get_sample_evidence(table_to_probe, instance_id)
                    if table_to_probe
                    else ""
                )
                evidence_section = (
                    f"\nEVIDENCE from {table_to_probe}:\n{evidence}"
                    if table_to_probe and evidence
                    else ""
                )
                error_context = f"EXECUTION ERROR: {result_msg}{discovery_feedback}{evidence_section}"

            if attempts < self.max_retries:
                logger.info("Generating corrected SQL...")
                is_zero_row = (success and row_count == 0) or (
                    "DATA QUALITY FAIL" in error_context
                )

                unpruned_tables = linked_schema.selected_tables
                if (
                    "invalid identifier" in error_context.lower()
                    or "does not exist" in error_context.lower()
                    or "unknown table" in error_context.lower()
                    or attempts >= 1
                ):
                    logger.info(
                        "Dynamic Schema Unpruning: Expanding schema context to full database view for recovery discovery."
                    )
                    all_db_tables = []
                    if self.semantic_engine.context:
                        for t in self.semantic_engine.context.tables:
                            if "." in t.name:
                                db_part = t.name.split(".")[0].upper()
                                if db_part == self.db_name.upper():
                                    all_db_tables.append(t.name)
                            else:
                                all_db_tables.append(t.name)
                    if len(all_db_tables) > 40:
                        logger.warning(
                            f"Database schema exceeds 40 tables. Restricting unpruned recovery context to top 40 tables of database {self.db_name}."
                        )
                        unpruned_tables = all_db_tables[:40]
                    else:  # type: ignore
                        unpruned_tables = None

                correction_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=unpruned_tables, include_samples=is_zero_row
                )  # type: ignore
                strategy = self._get_correction_strategy(error_context, attempts)

                # Self-diagnosis injection: surface the precise Data IQ diagnosis as a
                # top-priority lesson so the corrector gets the named root cause + fix recipe.
                inline_diagnosis = self._build_inline_diagnosis(error_context)

                # Hot-reload dynamic rules: pick up lessons activated by earlier queries
                # in the same session (InlineRuleExtractor may have just added them).
                hot_lessons = self._reload_dynamic_lessons(intent)

                enriched_lessons = lessons_context
                if inline_diagnosis:
                    enriched_lessons = inline_diagnosis + "\n\n" + enriched_lessons
                    logger.info(
                        "[SelfDiagnosis] Inline diagnosis injected into corrector context."
                    )
                if hot_lessons:
                    enriched_lessons = enriched_lessons + hot_lessons
                    logger.info(
                        "[SelfDiagnosis] Hot-reloaded dynamic lessons injected into corrector context."
                    )
                # Prepend dataset-specific hints (db_description_withhint.txt) at highest priority
                # into the corrector context. Placed BEFORE existing lessons so the authoritative
                # data-format guidance takes priority over any conflicting patterns in lessons.
                if _hints_text:
                    enriched_lessons = (
                        f"=== DATASET-SPECIFIC HINTS (HIGHEST PRIORITY — OVERRIDES ALL BELOW) ===\n{_hints_text}\n\n"
                        + enriched_lessons
                    )
                    logger.info(
                        "[HintInjection] Dataset-specific hints PREPENDED to self-corrector context at highest priority."
                    )

                correction_lessons = self._safeguard_lessons(
                    f"{enriched_lessons}\n\n{strategy}"
                    if strategy
                    else enriched_lessons
                )
                correction = self.corrector.correct_sql(
                    user_query=user_query,
                    failed_sql=current_sql,
                    error_message=error_context,
                    linked_schema=linked_schema,
                    schema_context=correction_context,
                    lessons=correction_lessons,
                    relevant_tables=unpruned_tables,
                    table_columns=table_columns_map
                    if unpruned_tables == linked_schema.selected_tables
                    else None,
                    intent=intent,
                )

                # Dynamic probing loop to let Corrector inspect database values or schema dynamically
                probe_limit = 2
                probe_count = 0
                while (
                    getattr(correction, "probe_sql", None) and probe_count < probe_limit
                ):
                    probe_count += 1  # type: ignore
                    probe_query = correction.probe_sql.strip()
                    logger.info(
                        f"Self-Corrector requested database probe SQL (probe {probe_count}/{probe_limit}): {probe_query}"
                    )

                    probe_success, probe_msg, probe_rows = self.executor.execute(
                        probe_query, f"{instance_id}_corrector_probe_{probe_count}"
                    )

                    probe_preview = "No result returned."
                    if probe_success:
                        probe_csv_path = os.path.join(
                            str(RESULTS_DIR),
                            self.db_name,
                            f"{instance_id}_corrector_probe_{probe_count}.csv",
                        )
                        if os.path.exists(probe_csv_path):
                            try:
                                df_probe = pd.read_csv(probe_csv_path)
                                probe_preview = self._safe_markdown_preview(
                                    df_probe, max_rows=5
                                )
                            except Exception as pe:
                                probe_preview = f"Failed to format probe output: {pe}"
                    else:
                        probe_preview = f"Probe execution failed: {probe_msg}"

                    logger.info(f"Probe Result:\n{probe_preview}")

                    # Update error_context with probe outcomes
                    error_context += (
                        f"\n\n[DIAGNOSTIC DATABASE PROBE {probe_count} RESULT]\n"
                        f"PROBE SQL: {probe_query}\n"
                        f"PROBE OUTPUT:\n{probe_preview}"
                    )

                    # Call corrector again with updated error context containing probe evidence
                    correction = self.corrector.correct_sql(
                        user_query=user_query,
                        failed_sql=current_sql,
                        error_message=error_context,
                        linked_schema=linked_schema,
                        schema_context=correction_context,
                        lessons=correction_lessons,
                        relevant_tables=unpruned_tables,
                        table_columns=table_columns_map
                        if unpruned_tables == linked_schema.selected_tables
                        else None,
                        intent=intent,
                    )

                current_sql = correction.sql  # type: ignore
                last_correction_thought = correction.thought_process

            if attempts == 0 and (
                not success or (locals().get("validation") and not validation.is_valid)
            ):
                initial_failed_sql = current_sql
                initial_error_context = error_context

            attempts += 1

        best_sql = self.sql_manager.get_best_sql(instance_id)
        if best_sql and best_sql != current_sql:
            logger.warning(
                f"FALLBACK: Max retries exceeded. Reverting to cached best_sql for {instance_id}"
            )
            fb_success, fb_msg, fb_row_count = self.executor.execute(
                best_sql, instance_id
            )
            if fb_success:
                logger.success(
                    f"FALLBACK SUCCESS: Restored best_sql result ({fb_row_count} rows)"
                )
                total_time = time.time() - start_time
                telemetry.end_stage("execution_and_audit")
                telemetry.log_summary()
                logger.log_final_results(
                    sql=best_sql,
                    row_count=fb_row_count,
                    latency=f"{total_time:.2f}s (FALLBACK)",
                )
                _save_telemetry()
                return best_sql

        total_time = time.time() - start_time
        telemetry.end_stage("execution_and_audit")
        telemetry.log_summary()
        logger.log_final_results(
            sql=current_sql,
            row_count=row_count if success else 0,
            error=error_context
            if "error_context" in locals()
            else "Max retries exceeded",
            latency=f"{total_time:.2f}s",
        )
        _save_telemetry()
        return current_sql

    def _build_inline_diagnosis(self, error_context: str) -> str:
        """
        When Data IQ returns a failure, extract the precise feedback and surface it as a
        prominently-labeled self-diagnosis block injected at the top of the corrector's
        lessons context.  This is the within-run self-learning mechanism: the pipeline
        names its own disease and prescribes the cure before the next retry.
        """
        if "DATA QUALITY FAIL:" not in error_context:
            return ""
        feedback = error_context.split("DATA QUALITY FAIL:", 1)[-1].strip()
        if not feedback:
            return ""
        return (
            "=== SELF-DIAGNOSED ROOT CAUSE — APPLY THIS FIX IMMEDIATELY ===\n"
            f"{feedback}\n"
            "The corrected SQL MUST address the issue above before anything else.\n"
            "=== END SELF-DIAGNOSIS ==="
        )

    def _reload_dynamic_lessons(self, intent) -> str:
        """
        Hot-reload dynamic rules from the store mid-run.  Called at each retry so that
        rules activated by a previous query's InlineRuleExtractor in the same session
        are immediately available to the corrector.
        """
        try:
            from backend.app.core.rules.dynamic_rule_store import DynamicRuleStore

            store = DynamicRuleStore()
            store.reload()
            active_rules = store.retrieve_relevant(
                query_words=set(
                    (
                        intent.filter_conditions[0] if intent.filter_conditions else ""
                    ).split()
                ),
                top_k=5,
                db_name=self.db_name,
            )
            if not active_rules:
                return ""
            lines = ["\n\n=== HOT-RELOADED LESSONS (activated this session) ==="]
            for r in active_rules:
                lines.append(f"RULE: {r['rule_title']}\nGuideline: {r['generic_rule']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"_reload_dynamic_lessons failed (non-fatal): {e}")
            return ""

    def _get_correction_strategy(self, error_context: str, attempt: int) -> str:
        """Return an escalating correction strategy directive based on error type and attempt number."""
        err_lower = error_context.lower()
        if attempt == 0:
            if (
                "does not exist" in err_lower
                or "invalid identifier" in err_lower
                or "object" in err_lower
            ):
                return "[CORRECTION STRATEGY]: A table or column reference was invalid. Check the exact fully-qualified names in the schema. Only use names visible in the schema context — do not guess."
            if "syntax" in err_lower or "parse" in err_lower:
                return "[CORRECTION STRATEGY]: There is a SQL syntax error. Rewrite only the broken portion — do not restructure the entire query."
            if "exclusion fan-out" in err_lower or "anti-join" in err_lower:
                return "[CORRECTION STRATEGY]: Exclusion fan-out detected. Replace WHERE child.col NOT LIKE with WHERE parent_key NOT IN (SELECT parent_key FROM child WHERE condition)."
            if (
                "anchor" in err_lower
                or "narrow join" in err_lower
                or "data universe" in err_lower
            ):
                return "[CORRECTION STRATEGY]: Join anchor violation. Rebuild FROM clause starting with the anchor join — do not scan the base table alone via a proxy column."
            if "data quality" in err_lower or "zero variance" in err_lower:
                return "[CORRECTION STRATEGY]: The query returned suspicious results. Re-examine every WHERE clause, JOIN condition, and GROUP BY grain."
            return "[CORRECTION STRATEGY]: Apply a minimal targeted fix for the specific error. Do not restructure the entire query."
        if attempt == 1:
            return "[CORRECTION STRATEGY]: Expand your approach — reconsider which tables are relevant, check for bridge/junction tables, and verify the join path uses the correct key columns."
        if attempt == 2:
            return "[CORRECTION STRATEGY]: Previous corrections failed. Loosen WHERE filters, remove aggressive predicates, and validate that filter values actually exist in the data."
        return "[CORRECTION STRATEGY]: All targeted corrections have failed. Completely rewrite the SQL from scratch using the most minimal approach possible — fewest JOINs and filters first."

    def _safeguard_lessons(self, lessons_context: str) -> str:
        if len(lessons_context) <= 80000:
            return lessons_context

        logger.info(
            "Token Safeguard: Condensing context intelligently by section parsing."
        )

        # Split lessons_context into structural blocks
        blocks = lessons_context.split("\n\n")
        pruned_blocks = []

        for block in blocks:
            block_stripped = block.strip()
            if not block_stripped:
                continue

            # 1. Prune Dialect Rules: keep only first 5 rules
            if block_stripped.startswith("=== DIALECT RULES ==="):
                lines = block_stripped.split("\n")
                header = lines[0]
                rules = [line for line in lines[1:] if line.strip().startswith("-")]
                if len(rules) > 5:
                    logger.info(
                        f"Token Safeguard: Pruned dialect rules from {len(rules)} to 5."
                    )
                    rules = rules[:5]
                pruned_blocks.append(header + "\n" + "\n".join(rules))

            # 2. Prune Dynamically Retrieved Lessons: keep only first 3 rules
            elif block_stripped.startswith(
                "=== DYNAMICALLY RETRIEVED LESSONS FROM HISTORICAL RUNS ==="
            ):
                lines = block_stripped.split("\n")
                header = lines[0]
                rule_blocks = []  # type: ignore
                current_rule = []
                for line in lines[1:]:
                    if line.strip().startswith("RULE:") and current_rule:
                        rule_blocks.append("\n".join(current_rule))
                        current_rule = [line]
                    else:
                        current_rule.append(line)
                if current_rule:
                    rule_blocks.append("\n".join(current_rule))

                if len(rule_blocks) > 3:
                    logger.info(
                        f"Token Safeguard: Pruned historical lessons from {len(rule_blocks)} to 3."
                    )
                    rule_blocks = rule_blocks[:3]
                pruned_blocks.append(header + "\n\n" + "\n\n".join(rule_blocks))

            # 3. Prune External Knowledge sections: limit to max 1200 characters on clean sentence boundary
            elif "EXTERNAL KNOWLEDGE" in block_stripped:
                # Find the header/label lines
                lines = block_stripped.split("\n")
                header_lines = []
                content_lines = []
                for line in lines:
                    if line.isupper() or (":" in line and len(line) < 50):
                        header_lines.append(line)
                    else:
                        content_lines.append(line)

                content = "\n".join(content_lines)
                if len(content) > 1200:
                    logger.info(
                        f"Token Safeguard: Pruned external knowledge block from {len(content)} chars."
                    )
                    truncated = content[:1200]
                    # Try to terminate on a clean sentence boundary
                    last_period = max(
                        truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!")
                    )
                    if last_period > 600:
                        truncated = truncated[: last_period + 1]
                    else:
                        truncated += " ..."
                    content = truncated
                pruned_blocks.append("\n".join(header_lines) + "\n" + content)

            # 4. Keep structural blocks (join paths, profiling, CTE plans, strategies) intact
            else:
                pruned_blocks.append(block_stripped)

        condensed = "\n\n".join(pruned_blocks)

        # If still over limit, do a fallback cleanup: drop external knowledge or general hints first,
        # but always preserve database schema / join graph / strategies
        if len(condensed) > 80000:
            logger.info(
                "Token Safeguard: Condensed context still above limit. Running fallback pruning."
            )
            essential_blocks = []
            for block in pruned_blocks:
                # Always preserve: self-diagnosis, join anchors, join sizes, join paths, strategy, profiling
                if any(
                    x in block
                    for x in (
                        "SELF-DIAGNOSED ROOT CAUSE",
                        "CROSS-TABLE JOIN SIZES",
                        "Narrow-Join Anchor",
                        "NARROW JOIN",
                        "JOIN PATHS",
                        "FOREIGN KEYS",
                        "DYNAMIC PROFILING",
                        "BLUEPRINT",
                        "STRATEGY",
                        "HOT-RELOADED LESSONS",
                    )
                ):
                    essential_blocks.append(block)
                # Keep dialect rules but restrict to top 3
                elif "=== DIALECT RULES ===" in block:
                    lines = block.split("\n")
                    essential_blocks.append(lines[0] + "\n" + "\n".join(lines[1:4]))
            condensed = "\n\n".join(essential_blocks)

        return condensed


if __name__ == "__main__":
    print(
        "Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries."
    )
