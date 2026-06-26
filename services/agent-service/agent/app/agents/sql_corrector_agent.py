import sqlglot

import re

from typing import List, Dict, Optional, Tuple

from agent.services.llm import LLMClient

from agent.app.utils.dialect_loader import DialectLoader

from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever

from agent.app.models.schemas import SelfCorrectorOutput, SchemaLinkerOutput

from agent.services.logger import logger



from agent.app.core.config import get_prompt_path



PROMPT_PATH = get_prompt_path("self_corrector.yaml")





# ---------------------------------------------------------------------------

# Error-pattern => correction-hint mapping.

# Each entry is (compiled_regex, hint_text).  Matched at runtime from the

# actual execution error --  no dialect or dataset values are hard-coded here.

# ---------------------------------------------------------------------------

_ERROR_PATTERNS: List[Tuple[re.Pattern, str]] = [

    (
        re.compile(r"attempted to access index 0 within vector of size 0", re.I),
        "ROOT CAUSE DETECTED: DuckDB internal assertion failure triggered by using a "
        "function expression (e.g. TRY_CAST, json_extract) DIRECTLY inside a JOIN ON "
        "clause.  MANDATORY FIX: move every derived/computed value into a CTE or "
        "subquery first, then JOIN on the plain scalar column.  "
        "Example (WRONG):  JOIN t ON TRY_CAST(json_extract(t.col, '$.key') AS BOOLEAN) = true  "
        "Example (CORRECT): WITH filtered AS (SELECT * FROM t WHERE TRY_CAST(json_extract(col, '$.key') AS BOOLEAN) = true) ... JOIN filtered ON ...",
    ),

    (

        re.compile(r"could not parse string .+ according to format specifier", re.I),

        "ROOT CAUSE DETECTED: STRPTIME raised an error because the date string did not "

        "match the format pattern.  STRPTIME is strict --  it throws on any mismatch.  "

        "MANDATORY FIX: replace every STRPTIME(...) call with TRY_STRPTIME(...) and wrap "

        "multiple patterns in COALESCE so rows with different formats are all handled.  "

        "Example: COALESCE(TRY_STRPTIME(col, fmt1), TRY_STRPTIME(col, fmt2), ...).",

    ),

    (

        re.compile(r"no function matches.*to_timestamp.*varchar.*string_literal", re.I),

        "ROOT CAUSE DETECTED: TO_TIMESTAMP(string, format) is not a valid DuckDB signature.  "

        "MANDATORY FIX: use TRY_STRPTIME(col, format) for custom formats, or "

        "TRY_CAST(col AS TIMESTAMP) for ISO-format strings.",

    ),

    (

        re.compile(r"no function matches.*to_timestamp", re.I),

        "ROOT CAUSE DETECTED: TO_TIMESTAMP with a format argument is not supported in this "

        "dialect.  MANDATORY FIX: use TRY_STRPTIME(col, format) instead.",

    ),

    (

        re.compile(r"binder error.*column.*does not exist", re.I),

        "ROOT CAUSE DETECTED: A referenced column does not exist in the schema.  "

        "MANDATORY FIX: check the exact column names from the schema and correct the reference.",

    ),

    (

        re.compile(r"repetition error", re.I),

        "ROOT CAUSE DETECTED: The corrected SQL was identical to a previously failed attempt.  "

        "MANDATORY FIX: write structurally different SQL --  change the join strategy, "

        "aggregation approach, or CTE decomposition.",

    ),

    (

        re.compile(r"no expression was parsed from --", re.I),

        "ROOT CAUSE DETECTED: The SQL generator produced an empty string.  "

        "MANDATORY FIX: ensure the sql field in your JSON output contains a complete, "

        "non-empty SELECT statement.",

    ),

    (

        # DuckDB Catalog Error - 'Did you mean "alias"."table"?'

        # Extract the exact alias.table suggestion from the error message and mandate its use.

        re.compile(r"catalog error.*does not exist|schema.*does not exist", re.I),

        "ROOT CAUSE DETECTED: DuckDB Catalog/Schema Error - the table qualifier is wrong.  "

        "MANDATORY FIX: look for 'Did you mean \"<alias>\".\"<table>\"?' in the error below.  "

        "If found, rewrite EVERY occurrence of the wrong table reference using EXACTLY that "

        "alias and table name (both double-quoted).  "

        "If no suggestion appears, run SHOW ALL TABLES to discover the correct alias, then "

        "qualify all table references as \"<alias>\".\"<table>\".",

    ),

]





def _enrich_error_context(error_message: str) -> str:

    """

    Detect known execution-error patterns and prepend a targeted correction hint.

    The hint is derived solely from the error text --  no dataset or dialect values

    are hard-coded.  Returns the (possibly enriched) error string.

    """

    for pattern, hint in _ERROR_PATTERNS:

        if pattern.search(error_message):

            return f"[AUTO-DIAGNOSED CORRECTION REQUIRED]\n{hint}\n\n{error_message}"

    return error_message





class SQLCorrectorAgent:

    def __init__(

        self, llm_client: LLMClient, semantic_engine, dialect: str = "snowflake"

    ):

        self.llm = llm_client

        self.semantic_engine = semantic_engine

        self.dialect = dialect.lower()

        self.dialect_loader = DialectLoader()



    def _validate_syntax(self, sql: str) -> bool:

        try:

            sqlglot.parse_one(sql, read=self.dialect)

            return True

        except Exception as e:

            logger.warning(f"SQLGlot syntax validation failed on corrected SQL: {e}")

            return False



    def _format_value_mappings(self, linked_schema: SchemaLinkerOutput) -> str:

        if not linked_schema.value_mappings:

            return "None"

        lines = []

        for m in linked_schema.value_mappings:

            lines.append(

                f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}"

            )

        return "\n".join(lines)



    def correct_sql(

        self,

        user_query: str,

        failed_sql: str,

        error_message: str,

        linked_schema: SchemaLinkerOutput,

        schema_context: str = "",

        lessons: str = "",

        relevant_tables: Optional[List[str]] = None,

        table_columns: Optional[Dict[str, List[str]]] = None,

        intent=None,

    ) -> SelfCorrectorOutput:

        logger.set_agent("SELF_CORRECTOR")

        logger.info("Executing Self-Correction Module")



        # Reuse pre-computed intent from orchestrator to avoid redundant analysis

        if intent is None:

            intent = HierarchicalRetriever().analyze_intent(user_query)

        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"

        enriched_error = _enrich_error_context(error_message)

        combined_lessons = f"FAILED SQL:\n```sql\n{failed_sql}\n```\n\nERROR CONTEXT:\n{enriched_error}\n\n{val_mappings_str}\n\n{lessons}"



        if table_columns is None:

            table_columns = {}

            if linked_schema and linked_schema.selected_columns:

                for fqn in linked_schema.selected_columns:

                    if "." in fqn:

                        parts = fqn.split(".")

                        t_name = ".".join(parts[:-1])

                        c_name = parts[-1]

                        if t_name not in table_columns:

                            table_columns[t_name] = []

                        table_columns[t_name].append(c_name)



        if relevant_tables is None:

            relevant_tables = linked_schema.selected_tables if linked_schema else None



        from agent.app.core.prompts.prompt_assembler import PromptAssembler



        assembler = PromptAssembler(dialect=self.dialect, stage="SELF_CORRECTOR")

        assembled = assembler.assemble(

            user_query=user_query,

            agent_type="SELF_CORRECTOR",

            context=self.semantic_engine.context,

            intent=intent,

            relevant_tables=relevant_tables,

            table_columns=table_columns,

            lessons=combined_lessons,

            error_history=error_message,

        )



        system_prompt = assembled.system_prompt

        user_prompt = assembled.user_prompt



        try:

            result = self.llm.generate_structured(

                system_prompt=system_prompt,

                user_prompt=user_prompt,

                response_model=SelfCorrectorOutput,

            )

            # Apply Dialect Sanitizers (Generic)

            for sanitizer in self.dialect_loader.get_sanitizers(self.dialect):

                search = sanitizer.get("search")

                replace = sanitizer.get("replace")

                if search:

                    result.sql = re.sub(

                        re.escape(search), replace, result.sql, flags=re.IGNORECASE

                    )

            self._validate_syntax(result.sql)

            logger.log_parsed_data("Correction Output", result)

            return result

        except ValueError as json_err:
            # LLM output truncated before JSON completed (think-block too long).
            # Return the original failed SQL so the retry loop can pivot rather
            # than crashing the entire pipeline with an unhandled exception.
            logger.warning(
                f"[SelfCorrector] JSON generation failed ({json_err}). "
                "Falling back to original SQL — retry loop will pivot."
            )
            return SelfCorrectorOutput(
                error_analysis="Corrector output truncated; returning original SQL for retry pivot.",
                thought_process="JSON self-repair failed — passing original SQL through unchanged.",
                probe_sql=None,
                sql=failed_sql,
            )

        except Exception:

            logger.error("Self-correction failed.")

            raise

        finally:

            logger.reset_agent()

