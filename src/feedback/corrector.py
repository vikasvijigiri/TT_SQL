import sqlglot
from src.utils.llm import LLMClient
from src.utils.prompt_loader import PromptLoader
from src.schema.models import SelfCorrectorOutput, SchemaLinkerOutput
from src.utils.logger import logger

PROMPT_PATH = "src/prompts/self_corrector.yaml"


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
    ) -> SelfCorrectorOutput:
        logger.set_agent("SELF_CORRECTOR")
        logger.info("Executing Self-Correction Module")

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "DIALECT":          self.dialect.upper(),
            "USER_QUERY":       user_query,
            "SELECTED_TABLES":  ", ".join(linked_schema.selected_tables),
            "SELECTED_COLUMNS": ", ".join(linked_schema.selected_columns),
            "VALUE_MAPPINGS":   self._format_value_mappings(linked_schema),
            "FAILED_SQL":       failed_sql,
            "ERROR_MESSAGE":    error_message,
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
