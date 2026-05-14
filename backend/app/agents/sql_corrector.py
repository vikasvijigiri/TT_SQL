import sqlglot
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.models.schemas import SelfCorrectorOutput, SchemaLinkerOutput
from backend.app.utils.logger import logger

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("self_corrector.yaml")


class ExecutionCorrector:
    def __init__(self, llm_client: LLMClient, dialect: str = "snowflake"):
        self.llm = llm_client
        self.dialect = dialect.lower()

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
            lines.append(f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}")
        return "\n".join(lines)

    def correct_sql(
        self,
        user_query: str,
        failed_sql: str,
        error_message: str,
        linked_schema: SchemaLinkerOutput,
        schema_context: str = ""
    ) -> SelfCorrectorOutput:
        logger.set_agent("SELF_CORRECTOR")
        logger.info("Executing Self-Correction Module")

        dialect_rules = DialectLoader.load_dialect_rules(self.dialect)

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "DIALECT":          self.dialect.upper(),
            "DIALECT_RULES":    dialect_rules,
            "USER_QUERY":       user_query,
            "SELECTED_TABLES":  ", ".join(linked_schema.selected_tables),
            "SELECTED_COLUMNS": ", ".join(linked_schema.selected_columns),
            "VALUE_MAPPINGS":   self._format_value_mappings(linked_schema),
            "FAILED_SQL":       failed_sql,
            "ERROR_MESSAGE":    error_message,
            "SCHEMA_CONTEXT":    schema_context,
            "LESSONS":          "" # Corrector also gets lessons if we pass them
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SelfCorrectorOutput,
            )
            self._validate_syntax(result.sql)
            logger.log_parsed_data("Correction Output", result)
            return result
        except Exception:
            logger.error("Self-correction failed.")
            raise
        finally:
            logger.reset_agent()
