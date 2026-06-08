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

import pandas as pd
import os
import time
import re
import yaml
from pathlib import Path
from backend.app.core.config import RESULTS_DIR, CONFIG_DIR, RESOURCES_DIR, MEMORY_DIR
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.core.connection import parse_connection

class SemanticDINOrchestrator:
    def __init__(
        self,
        db_directory: str,
        db_name: str = "",
        dialect: str = "",
        max_retries: int = 3,
        connection_string: str = None,
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
        dialect  = dialect  or "snowflake"
        db_name  = db_name  or "UNKNOWN"

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

        # Load System Parameters
        params_path = CONFIG_DIR / "system_params.yaml"
        with open(params_path, 'r', encoding='utf-8') as f:
            self.params = yaml.safe_load(f)

        self.max_retries = self.params['orchestrator'].get('max_retries', max_retries)

        # Build context immediately
        self.semantic_engine.build_context()

    def _safe_markdown_preview(self, df: pd.DataFrame, max_rows: int = 10, max_col_width: int = 100) -> str:
        if df.empty:
            return "No preview available (0 rows)."
        preview_df = df.head(max_rows).copy()
        for col in preview_df.columns:
            preview_df[col] = preview_df[col].astype(str).apply(lambda x: x[:max_col_width] + "..." if len(x) > max_col_width else x)
        md = preview_df.to_markdown(index=False)
        if len(md) > 4000:
            md = md[:4000] + "\n...[TRUNCATED]"
        return md

    def _get_base_lessons(self, intent, external_knowledge: str = None) -> str:
        rule_retriever = DialectRuleRetriever(self.executor.dialect)
        # Use adaptive in-code rule families — works for every dialect without requiring a YAML handbook.
        # retrieve_relevant_rules() is YAML-only and returns "not found" for DuckDB, Postgres, etc.
        profile = QueryCapabilityDetector.detect(
            intent.intent if hasattr(intent, "intent") else "", intent
        )
        rule_list = rule_retriever.get_adaptive_rules(profile, max_rules=15)
        lessons = "=== DIALECT RULES ===\n" + "\n".join(f"- {r}" for r in rule_list)
        
        # Load dynamically synthesized lessons (completely generic, no hardcoding)
        dynamic_lessons_path = MEMORY_DIR / "dynamic_lessons.json"
        if dynamic_lessons_path.exists():
            try:
                import json
                with open(dynamic_lessons_path, 'r', encoding='utf-8') as df:
                    dyn_data = json.load(df)
                active_rules = [r for r in dyn_data if r.get('status') == 'ACTIVE']
                
                # Select lessons that share intent keyword / schema overlap
                matched_rules = []
                query_words = set(intent.intent.lower().split() + intent.tables_referred) if hasattr(intent, 'intent') else set()
                for rule in active_rules:
                    pattern = rule.get('intent_pattern', '').lower()
                    pattern_words = set(pattern.split())
                    if pattern_words.intersection(query_words) or rule.get('db_name', '').upper() == self.db_name.upper():
                        matched_rules.append(rule)
                
                # Fetch general fallback lessons if matching pool is small
                if len(matched_rules) < 3:
                    general_rules = [r for r in active_rules if not r.get('db_name') and r not in matched_rules]
                    matched_rules.extend(general_rules[:3 - len(matched_rules)])
                
                if matched_rules:
                    lessons += "\n\n=== DYNAMICALLY RETRIEVED LESSONS FROM HISTORICAL RUNS ===\n"
                    for r in matched_rules:
                        lessons += f"RULE: {r['rule_title']}\nGuideline: {r['generic_rule']}\n\n"
                    logger.info(f"Dynamically loaded {len(matched_rules)} dynamic lessons into the pipeline context.")
            except Exception as de:
                logger.warning(f"Failed to load dynamic lessons: {de}")

        if external_knowledge:
            doc_path = RESOURCES_DIR / "documents" / external_knowledge
            if doc_path.exists():
                try:
                    doc_content = doc_path.read_text(encoding='utf-8')
                    lessons += f"\n\nEXTERNAL KNOWLEDGE / DOMAIN SPECIFICATIONS:\n{doc_content}\n"
                    logger.info(f"Loaded external knowledge from {external_knowledge}")
                except Exception as e:
                    logger.warning(f"Failed to read external knowledge file {external_knowledge}: {e}")
        return lessons

    def execute_query(self, user_query: str, instance_id: str = "test_instance", external_knowledge: str = None) -> str:
        start_time = time.time()
        telemetry = PipelineTelemetry(query_id=instance_id)
        telemetry.start_stage("schema_linking")

        logger.log_section(f"Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")
        
        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)
        lessons_context = self._get_base_lessons(intent, external_knowledge)
        
        # Estimate full schema size to decide on pruning
        full_schema_str = self.semantic_engine.format_for_prompt()
        h = self.params['orchestrator']['token_heuristic']
        estimated_tokens = len(full_schema_str) // h
        threshold = self.params['orchestrator']['pruning_threshold_tokens']
        
        logger.info(f"Schema density evaluated (~{estimated_tokens} tokens vs threshold {threshold}).")
        linked_schema = self.schema_linker.link_schema(user_query, dialect=self.executor.dialect, lessons=lessons_context, force_full=(estimated_tokens <= threshold))

        # FK/PK join graph — computed over already-pruned tables only, always O(small)
        join_graph = self.semantic_engine.extract_join_graph(linked_schema.selected_tables)
        if join_graph:
            logger.info(f"[JoinGraph] Injecting join paths for {len(linked_schema.selected_tables)} selected tables.")
            lessons_context += f"\n\n{join_graph}"

        table_columns_map = {}
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
        telemetry.start_stage("profiling_and_generation")

        # Dynamic Profiling Probe (Reflective schema exploration before generation)
        profiling_insights = self.profiler.profile_columns(
            user_query, linked_schema.selected_columns, self.executor, dialect=self.executor.dialect
        )
        if profiling_insights:
            logger.info("Injecting live profiling insights into SQL generation context...")
            lessons_context += f"\n\nDYNAMIC PROFILING INSIGHTS FROM DATA AUDIT:\n{profiling_insights}\n"

        # Retrieve Reference SQL for Convergence
        reference_context = self.sql_manager.get_reference_context(instance_id)

        # Query Decomposition — inject CTE blueprint for multi-hop questions (zero LLM cost for simple queries)
        decomp_plan = self.decomposer.decompose(user_query, linked_schema.selected_tables)
        decomp_section = QueryDecomposerAgent.format_plan_for_prompt(decomp_plan)
        if decomp_section:
            logger.info("[Decomposer] Multi-hop CTE blueprint injected into generation context.")
            lessons_context += f"\n\n{decomp_section}"

        # Module 3: SQL Generation — simple single-pass or complex diverse-candidates
        lessons_context = self._safeguard_lessons(lessons_context)
        profile = QueryCapabilityDetector.detect(user_query, intent, self.semantic_engine.context)
        n_tables = len(linked_schema.selected_tables) if linked_schema and linked_schema.selected_tables else 0
        is_simple_query = (
            not profile.requires_joins and
            not profile.requires_windows and
            not profile.requires_variants and
            not profile.requires_flatten
        )

        # Module 3.5: Knowledge Acquisition (Web Search if needed) — runs before generation for all queries
        unclear_terms = [m.user_term for m in (linked_schema.value_mappings or []) if not m.db_value]
        if unclear_terms:
            logger.info(f"Unclear terms detected: {unclear_terms}. Triggering Web Research...")
            limit = self.params['orchestrator']['research_term_limit']
            for term in unclear_terms[:limit]:
                external_info = self.knowledge_tool.search_term(term, context=f"Database: {self.db_name}")
                logger.info(f"Research Result for '{term}': {external_info[:200]}...")
                lessons_context += f"\nEXTERNAL KNOWLEDGE ACQUIRED:\n{external_info}\n"
                logger.info(f"WEB_KNOWLEDGE: {external_info}")
            lessons_context = self._safeguard_lessons(lessons_context)

        combined_lessons = f"{lessons_context}\n{reference_context}"
        is_complex_question = not is_simple_query or QueryDecomposerAgent._is_complex_question(user_query)

        if is_complex_question:
            # Diverse generation: 3 structurally different candidates, critic picks the best
            logger.info(f"Complex query detected ({n_tables} tables). Using diverse 3-candidate generation with critic selection.")
            candidates = self.sql_generator.generate_diverse(
                user_query, linked_schema, lessons=combined_lessons, intent=intent, n=3
            )
            if not candidates:
                logger.error(f"FATAL: All generation candidates failed for {instance_id}")
                return "ERROR: SQL Generation Failed"
            current_sql = candidates[0].sql

            critic_schema_context = self.semantic_engine.format_for_prompt(
                relevant_tables=linked_schema.selected_tables, include_samples=False
            )
            last_critic_res = None
            critic_accepted = False
            for cand in candidates:
                last_critic_res = self.critic.critique_sql(
                    user_query, cand.sql, critic_schema_context, combined_lessons,
                    self.executor.dialect, relevant_tables=linked_schema.selected_tables,
                    table_columns=None, intent=intent
                )
                if last_critic_res.is_valid:
                    current_sql = cand.sql
                    critic_accepted = True
                    logger.info("[DiverseGen] Critic-selected candidate accepted.")
                    break

            if not critic_accepted and last_critic_res:
                logger.warning(f"[DiverseGen] All {len(candidates)} candidates rejected by critic. Regenerating with feedback.")
                critic_feedback = (
                    f"\n\n[ADVERSARIAL CRITIC FEEDBACK]: {last_critic_res.criticism}"
                    f"\nProposed Fix:\n{last_critic_res.proposed_fix}"
                    f"\nYou MUST rewrite the SQL to resolve these criticisms!"
                )
                lessons_context = self._safeguard_lessons(lessons_context + critic_feedback)
                fallback = self.sql_generator.generate(
                    user_query, linked_schema,
                    lessons=f"{lessons_context}\n{reference_context}", intent=intent
                )
                if fallback and fallback.sql:
                    current_sql = fallback.sql
        else:
            # Simple query: single-pass generation, no critic overhead
            logger.info(f"Simple query detected ({n_tables} table(s), no joins/windows/variants). Bypassing diverse generation and critic.")
            generation_result = self.sql_generator.generate(
                user_query, linked_schema, lessons=combined_lessons, intent=intent
            )
            if not generation_result or not generation_result.sql:
                logger.error(f"FATAL: SQL Generator failed to produce initial SQL for {instance_id}")
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
            expanded_schema.selected_tables = [t.name for t in self.semantic_engine.context.tables] if self.semantic_engine.context else linked_schema.selected_tables
            expanded_schema.selected_columns = []  # let PromptAssembler use all columns
            recovery = self.sql_generator.generate(
                user_query, expanded_schema, lessons=combined_lessons, intent=intent
            )
            if recovery and recovery.sql and recovery.sql.strip():
                current_sql = recovery.sql
                logger.info("[Generation] Full-schema recovery attempt produced SQL.")
            else:
                logger.error(f"FATAL: Full-schema recovery also failed for {instance_id}")
                return "ERROR: SQL Generation Failed"

        # Pre-flight Schema Verification
        is_valid, schema_err = self.stabilizer.verify_schema_reference(current_sql, self.semantic_engine)
        if not is_valid:
            logger.warning(f"[SCHEMA HALLUCINATION] {schema_err}")
            error_context = f"SCHEMA ERROR: {schema_err}"
            attempts = 0
        
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

            if 'error_context' in locals() and error_context and attempts == 0:
                success = False
                result_msg = error_context
                logger.info(f"Skipping execution due to pre-flight error: {error_context}")
            else:
                sqlite_path, duckdb_path, pg_conn_str = self.executor._resolve_paths()
                preflight_error = None
                if sqlite_path:
                    preflight_error = self.executor._preflight_sqlite_statement(current_sql)

                sql_hash = self.stabilizer.get_sql_hash(current_sql)
                if preflight_error:
                    logger.error(f"[PRE-FLIGHT SQL REJECTION] {preflight_error}")
                    success = False
                    result_msg = preflight_error
                elif sql_hash in self.stabilizer.retry_history:
                    logger.warning(f"[RETRY MEMORY] Semantically identical SQL. Forcing pivot.")
                    table_to_probe = linked_schema.selected_tables[0] if linked_schema.selected_tables else None
                    evidence = self.stabilizer.get_sample_evidence(table_to_probe, instance_id) if table_to_probe else ""
                    evidence_section = f"\nEVIDENCE from {table_to_probe}:\n{evidence}" if table_to_probe and evidence else ""
                    error_context = f"REPETITION ERROR: Do not repeat previous SQL.{evidence_section}"
                    success = False
                    result_msg = error_context
                else:
                    self.stabilizer.retry_history.add(sql_hash)
                    success, result_msg, row_count = self.executor.execute(current_sql, instance_id)
            
            if success:
                diag_info = ""
                if row_count == 0:
                    logger.warning("Query returned 0 rows. Invoking Data IQ for discovery/probing.")
                    diag_info = self.stabilizer.diagnose_filter_collapse(current_sql, instance_id)
                    logger.info(f"[EMPTY RESULT DIAGNOSTIC] {diag_info}")
                else:
                    logger.success(f"Query returned {row_count} rows. Invoking Data IQ for quality audit.")

                csv_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}.csv")
                preview_str = "No preview available (0 rows)."
                stats = {"total_rows": 0, "total_columns": 0}
                
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            preview_str = self._safe_markdown_preview(df)
                        
                        placeholders = self.params['data_iq']['placeholders']
                        placeholder_counts = {}
                        if not df.empty:
                            for p in placeholders:
                                c = int((df.astype(str).map(lambda x: x.strip() if isinstance(x, str) else x) == p).sum().sum())
                                if c > 0: placeholder_counts[f"count_of_{p}"] = c

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
                                    "null_count": int(s.isnull().sum())
                                }
                                
                                if is_num:
                                    col_info["min"] = float(s.min()) if not s.empty and not s.isnull().all() else 0
                                    col_info["max"] = float(s.max()) if not s.empty and not s.isnull().all() else 0
                                    col_info["mean"] = float(s.mean()) if not s.empty and not s.isnull().all() else 0
                                    std_val = s.std()
                                    col_info["std"] = float(std_val) if pd.notnull(std_val) else 0.0
                                    
                                    # Check for all-zero column
                                    if total_rows > 1 and (s.dropna() == 0).all():
                                        data_iq_alerts.append(f"ALERT: Column '{col}' contains ONLY numeric zero (0.0) across all {total_rows} rows!")
                                else:
                                    col_info["sample_values"] = s.dropna().astype(str).head(3).tolist()
                                    
                                # Check for zero variance
                                if total_rows > 5 and nunique == 1:
                                    val_str = str(s.iloc[0]) if not s.empty else "NULL"
                                    data_iq_alerts.append(f"ALERT: Column '{col}' has ZERO VARIANCE! Every single row across all {total_rows} rows has the identical value: '{val_str}'")
                                    
                                column_profiles[col] = col_info

                        stats = {
                            "total_rows": total_rows,
                            "total_columns": len(df.columns),
                            "column_names": df.columns.tolist(),
                            "column_profiles": column_profiles,
                            "duplicate_rows": int(df.duplicated().sum()) if not df.empty else 0,
                            "placeholder_counts": placeholder_counts,
                            "data_iq_alerts": data_iq_alerts
                        }
                    except Exception as e:
                        logger.warning(f"Failed to generate stats for Data IQ: {e}")
                
                is_zero_row = row_count == 0
                validation_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables,
                    include_samples=is_zero_row
                )
                
                validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info, relevant_tables=linked_schema.selected_tables, table_columns=table_columns_map, intent=intent)
                
                if validation.exploration_sql:
                    logger.info(f"Data IQ requesting exploration probe: {validation.exploration_sql}")
                    probe_success, probe_msg, probe_rows = self.executor.execute(validation.exploration_sql, f"{instance_id}_probe")
                    probe_data = f"Probe failed: {probe_msg}"
                    if probe_success:
                        probe_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}_probe.csv")
                        try:
                            probe_df = pd.read_csv(probe_path)
                            probe_data = self._safe_markdown_preview(probe_df)
                        except: probe_data = "Probe returned no readable data."
                    else:
                        logger.warning("Exploration probe failed — reusing cached lessons context.")
                    
                    logger.info(f"Probe Result:\n{probe_data}")
                    validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, exploration_results=probe_data, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info, relevant_tables=linked_schema.selected_tables, table_columns=table_columns_map, intent=intent)

                logger.log_parsed_data("Data IQ Audit Reasoning", validation.audit_reasoning)
                
                if validation.is_valid or attempts == self.max_retries:
                    self.sql_manager.cache_success(instance_id, current_sql, validation.audit_reasoning)

                    if validation.is_valid and attempts > 0 and initial_failed_sql and initial_error_context:
                        try:
                            from backend.app.core.rules.lesson_synthesizer import LessonSynthesizer
                            synthesizer = LessonSynthesizer(llm_client=self.llm)
                            synthesizer.synthesize_and_save(
                                question=user_query,
                                failed_sql=initial_failed_sql,
                                error_message=initial_error_context,
                                corrected_sql=current_sql,
                                dialect=self.executor.dialect,
                                dataset=self.db_name,
                                instance_id=instance_id
                            )
                        except Exception as se:
                            logger.warning(f"Failed to synthesize lesson: {se}")

                    logger.info(f"RESULT PREVIEW:\n{preview_str}")
                    total_time = time.time() - start_time
                    telemetry.end_stage("execution_and_audit")
                    telemetry.log_summary()
                    logger.log_final_results(sql=current_sql, row_count=row_count, latency=f"{total_time:.2f}s")
                    return current_sql
                else:
                    error_context = f"DATA QUALITY FAIL: {validation.feedback}"
                    logger.warning(f"Data IQ Check Failed! {validation.feedback}")
            else:
                logger.error(f"Execution failed: {result_msg}")
                logger.info("Bypassing Data IQ audit due to execution error.")
                
                missing_obj_match = re.search(r"(?:Object|Table|View)\s+'?([a-zA-Z0-9_\.]+)'?\s+(?:does not exist|not found)", result_msg, re.IGNORECASE)
                discovery_feedback = ""
                if missing_obj_match:
                    missing_obj = missing_obj_match.group(1).split('.')[-1]
                    logger.info(f"Detected missing table/object reference: '{missing_obj}'. Running dynamic cross-database table discovery...")
                    discovered = self.semantic_engine.discover_and_load_table(missing_obj)
                    if discovered:
                        fqns = ", ".join(f"'{t.name}'" for t in discovered)
                        discovery_feedback = f"\n[CROSS-DATABASE DISCOVERY] The table '{missing_obj}' was not found in the active database. However, we dynamically discovered and loaded the matching authoritative cross-database table(s): {fqns}. You MUST modify the SQL query to join/query from {fqns} instead of the missing '{missing_obj}'!"
                
                failed_table = None
                patterns = self.dialect_loader.get_error_patterns(self.executor.dialect)
                pattern = r"invalid identifier '\"?([A-Z0-9_]+)\"?\.\"?([A-Z0-9_]+)\"?'"
                if isinstance(patterns, dict):
                    pattern = patterns.get('invalid_identifier', pattern)
                
                table_match = re.search(pattern, result_msg, re.IGNORECASE)
                if table_match:
                    alias = table_match.group(1).upper()
                    join_pattern = rf'(?:FROM|JOIN)\s+((?:\"[^\"]+\"\.)*(?:\"[^\"]+\"|[A-Z0-9_]+))\s+(?:AS\s+)?\"?{alias}\"?\b'
                    alias_map = re.findall(join_pattern, current_sql, re.IGNORECASE)
                    if alias_map:
                        raw = alias_map[0].replace('"', '')
                        failed_table = raw.split('.')[-1]
                
                valid_table = None
                if failed_table:
                    for t_fqn in linked_schema.selected_tables:
                        if t_fqn.upper().endswith(f".{failed_table.upper()}") or t_fqn.upper() == failed_table.upper():
                            valid_table = t_fqn
                            break
                if not valid_table and linked_schema.selected_tables:
                    valid_table = linked_schema.selected_tables[0]
                
                table_to_probe = valid_table if valid_table else None
                evidence = self.stabilizer.get_sample_evidence(table_to_probe, instance_id) if table_to_probe else ""
                evidence_section = f"\nEVIDENCE from {table_to_probe}:\n{evidence}" if table_to_probe and evidence else ""
                error_context = f"EXECUTION ERROR: {result_msg}{discovery_feedback}{evidence_section}"

            if attempts < self.max_retries:
                logger.info("Generating corrected SQL...")
                is_zero_row = (success and row_count == 0) or ("DATA QUALITY FAIL" in error_context)
                
                unpruned_tables = linked_schema.selected_tables
                if "invalid identifier" in error_context.lower() or "does not exist" in error_context.lower() or "unknown table" in error_context.lower() or attempts >= 1:
                    logger.info("Dynamic Schema Unpruning: Expanding schema context to full database view for recovery discovery.")
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
                        logger.warning(f"Database schema exceeds 40 tables. Restricting unpruned recovery context to top 40 tables of database {self.db_name}.")
                        unpruned_tables = all_db_tables[:40]
                    else:
                        unpruned_tables = None
                
                correction_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=unpruned_tables,
                    include_samples=is_zero_row
                )
                strategy = self._get_correction_strategy(error_context, attempts)
                correction_lessons = self._safeguard_lessons(f"{lessons_context}\n\n{strategy}" if strategy else lessons_context)
                correction = self.corrector.correct_sql(
                    user_query=user_query,
                    failed_sql=current_sql,
                    error_message=error_context,
                    linked_schema=linked_schema,
                    schema_context=correction_context,
                    lessons=correction_lessons,
                    relevant_tables=unpruned_tables,
                    table_columns=table_columns_map if unpruned_tables == linked_schema.selected_tables else None,
                    intent=intent
                )
                current_sql = correction.sql
                last_correction_thought = correction.thought_process
            
            if attempts == 0 and (not success or (locals().get('validation') and not validation.is_valid)):
                initial_failed_sql = current_sql
                initial_error_context = error_context

            attempts += 1

        best_sql = self.sql_manager.get_best_sql(instance_id)
        if best_sql and best_sql != current_sql:
            logger.warning(f"FALLBACK: Max retries exceeded. Reverting to cached best_sql for {instance_id}")
            fb_success, fb_msg, fb_row_count = self.executor.execute(best_sql, instance_id)
            if fb_success:
                logger.success(f"FALLBACK SUCCESS: Restored best_sql result ({fb_row_count} rows)")
                total_time = time.time() - start_time
                telemetry.end_stage("execution_and_audit")
                telemetry.log_summary()
                logger.log_final_results(sql=best_sql, row_count=fb_row_count, latency=f"{total_time:.2f}s (FALLBACK)")
                return best_sql

        total_time = time.time() - start_time
        telemetry.end_stage("execution_and_audit")
        telemetry.log_summary()
        logger.log_final_results(sql=current_sql, row_count=row_count if success else 0, error=error_context if 'error_context' in locals() else "Max retries exceeded", latency=f"{total_time:.2f}s")
        return current_sql

    def _get_correction_strategy(self, error_context: str, attempt: int) -> str:
        """Return an escalating correction strategy directive based on error type and attempt number."""
        err_lower = error_context.lower()
        if attempt == 0:
            if "does not exist" in err_lower or "invalid identifier" in err_lower or "object" in err_lower:
                return "[CORRECTION STRATEGY]: A table or column reference was invalid. Check the exact fully-qualified names in the schema. Only use names visible in the schema context — do not guess."
            if "syntax" in err_lower or "parse" in err_lower:
                return "[CORRECTION STRATEGY]: There is a SQL syntax error. Rewrite only the broken portion — do not restructure the entire query."
            if "data quality" in err_lower or "zero variance" in err_lower:
                return "[CORRECTION STRATEGY]: The query returned suspicious results. Re-examine every WHERE clause, JOIN condition, and GROUP BY grain."
            return "[CORRECTION STRATEGY]: Apply a minimal targeted fix for the specific error. Do not restructure the entire query."
        if attempt == 1:
            return "[CORRECTION STRATEGY]: Expand your approach — reconsider which tables are relevant, check for bridge/junction tables, and verify the join path uses the correct key columns."
        if attempt == 2:
            return "[CORRECTION STRATEGY]: Previous corrections failed. Loosen WHERE filters, remove aggressive predicates, and validate that filter values actually exist in the data."
        return "[CORRECTION STRATEGY]: All targeted corrections have failed. Completely rewrite the SQL from scratch using the most minimal approach possible — fewest JOINs and filters first."

    def _safeguard_lessons(self, lessons_context: str) -> str:
        if len(lessons_context) > 6000:
            logger.info("Token Safeguard: Condensing context by keeping only the most recent core lessons.")
            return lessons_context[:2000] + "\n\n... [TRUNCATED FOR TOKEN CONVERGENCE] ...\n\n" + lessons_context[-3500:]
        return lessons_context

if __name__ == "__main__":
    print("Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries.")
