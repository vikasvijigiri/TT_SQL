import re
from typing import List, Optional, Dict, Tuple
from backend.app.utils.llm import LLMClient
from backend.app.models.schemas import CriticOutput
from backend.app.utils.logger import logger


# ---------------------------------------------------------------------------
# Static SQL analysis: dialect-aware unsafe patterns detected before execution.
# Each entry: (dialect_set, regex, warning_text).
# Triggered purely from the SQL text — no prompt or dataset values hard-coded.
# ---------------------------------------------------------------------------
_STATIC_SQL_WARNINGS: List[Tuple[frozenset, re.Pattern, str]] = [
    (
        frozenset({"duckdb"}),
        re.compile(r"\bSTRPTIME\s*\(", re.I),
        "STATIC ANALYSIS WARNING: STRPTIME() detected in DuckDB SQL.  STRPTIME raises "
        "an exception when ANY row's string doesn't match the format — it does NOT return "
        "NULL.  If the date column has heterogeneous formats, this will fail at runtime.  "
        "Use TRY_STRPTIME() instead (returns NULL on mismatch) and wrap multiple format "
        "attempts in COALESCE.  Verify this is intentional before approving the SQL.",
    ),
    (
        frozenset({"duckdb"}),
        re.compile(r"\bTO_TIMESTAMP\s*\([^)]*,\s*['\"]", re.I),
        "STATIC ANALYSIS WARNING: TO_TIMESTAMP(col, format) is not a valid DuckDB "
        "function signature — DuckDB's TO_TIMESTAMP accepts only a numeric epoch argument.  "
        "Use TRY_STRPTIME(col, format) for custom string-to-timestamp conversion.",
    ),
    (
        frozenset(
            {
                "duckdb",
                "sqlite",
                "postgres",
                "postgresql",
                "snowflake",
                "mssql",
                "mysql",
            }
        ),
        re.compile(r"/\s*(?!NULLIF\b)[a-zA-Z_\"\[`]", re.I),
        "STATIC ANALYSIS WARNING: Division operator detected without NULLIF guard on the "
        "denominator.  If any denominator row is zero this will raise a division-by-zero "
        "error.  Wrap the denominator: expr / NULLIF(denominator, 0).",
    ),
]


def _static_sql_analysis(sql: str, dialect: str) -> str:
    """
    Scan the SQL for known unsafe patterns and return a warning block (or empty string).
    Triggered by the SQL content alone — no hard-coded column/table/dataset names.
    """
    d = dialect.lower()
    warnings = []
    for dialect_set, pattern, warning in _STATIC_SQL_WARNINGS:
        if d in dialect_set and pattern.search(sql):
            warnings.append(warning)
    if not warnings:
        return ""
    joined = "\n\n".join(warnings)
    return f"[STATIC SQL ANALYSIS — review before approving]\n{joined}\n"


class SQLCriticAgent:
    """
    Adversarial Database Forensic Auditor.
    Applies 10 structured directives to detect structural flaws in generated SQL before
    execution: alias validity, dialect casing, escape safety, division-by-zero,
    join cardinality, opaque code projection, JSON casting, spatial integrity,
    temporal boundary correctness, and semantic grain/determinism.
    """

    def __init__(self, llm_client: LLMClient, semantic_engine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine

    def critique_sql(
        self,
        user_query: str,
        proposed_sql: str,
        schema_context: str,
        lessons: str,
        dialect: str = "snowflake",
        relevant_tables: Optional[List[str]] = None,
        table_columns: Optional[Dict[str, List[str]]] = None,
        intent=None,
        executor=None,
    ) -> CriticOutput:
        """
        Runs a structured, 10-directive adversarial forensic audit of the proposed SQL.
        If a flaw is found, outputs a precise criticism and an actionable fix recipe.
        """
        logger.set_agent("CRITIC")
        logger.info("Executing adversarial Planner-Critic query audit...")

        from backend.app.core.retrieval.hierarchical_retriever import (
            HierarchicalRetriever,
        )

        # Reuse pre-computed intent from orchestrator to avoid redundant analysis
        if intent is None:
            intent = HierarchicalRetriever().analyze_intent(user_query)

        # Run static analysis on the SQL before bundling — flags unsafe patterns
        # (e.g. STRPTIME without TRY_, division without NULLIF) from the SQL text itself.
        static_warnings = _static_sql_analysis(proposed_sql, dialect)

        # SOTA Execution-Guided Decoding Probe
        probe_warnings = ""
        if executor:
            try:
                # Wrap proposed SQL to check if it returns 0 rows or syntax errors
                probe_sql = f"SELECT * FROM ({proposed_sql}) AS __probe LIMIT 1"
                ok, _, rows = executor.execute_direct(probe_sql)
                if ok and not rows:
                    probe_warnings = "EXECUTION PROBE WARNING: The proposed SQL executed successfully but returned ZERO rows! If the user query expects an answer, this means your JOINs or WHERE clauses are hallucinated and filtering out all data. You MUST rewrite the SQL to return data.\n\n"
                elif not ok:
                    # Capture runtime errors that static analysis missed
                    probe_warnings = f"EXECUTION PROBE ERROR: The proposed SQL failed at runtime with error: {rows}. You MUST fix this error.\n\n"
            except Exception as e:
                probe_warnings = f"EXECUTION PROBE ERROR: The proposed SQL failed at runtime with error: {e}. You MUST fix this error.\n\n"

        # Bundle SQL and schema context into the lessons stream so the compression pipeline
        # injects them into the user section via {SQL} and {SCHEMA_CONTEXT} template vars
        combined_lessons = (
            f"SQL TO AUDIT:\n```sql\n{proposed_sql}\n```\n\n"
            f"{probe_warnings}"
            f"{static_warnings}"
            f"SCHEMA:\n{schema_context}\n\n"
            f"PAST LESSONS:\n{lessons}"
        )

        from backend.app.core.prompts.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(dialect=dialect, stage="CRITIC")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="CRITIC",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons=combined_lessons,
        )

        system_prompt = assembled.system_prompt
        user_prompt = assembled.user_prompt

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=CriticOutput,
            )

            logger.log_parsed_data("Critic Output", result)
            return result

        except Exception as e:
            # Safe Fallback: if Critic LLM call fails, let the query proceed to execution
            logger.warning(
                f"Critic audit failed to compile structured response: {e}. Bypassing audit to prevent bottleneck."
            )
            return CriticOutput(is_valid=True)  # type: ignore
        finally:
            logger.reset_agent()
