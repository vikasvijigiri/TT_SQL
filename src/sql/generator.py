import sqlglot
from src.utils.llm import LLMClient
from src.utils.prompt_loader import PromptLoader
from src.utils.dialect_loader import DialectLoader
from src.schema.models import SQLGeneratorOutput, SchemaLinkerOutput, QueryClassifierOutput
from src.utils.logger import logger
from src.indexing.semantic_engine import SemanticContextEngine

PROMPT_PATH = "src/prompts/sql_generator.yaml"




class AdaptiveSQLGenerator:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine, dialect: str = "snowflake"):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.dialect = dialect.lower()

    def _validate_syntax(self, sql: str) -> bool:
        try:
            sqlglot.parse_one(sql, read=self.dialect)
            return True
        except Exception as e:
            logger.warning(f"SQLGlot syntax validation failed: {e}")
            return False

    def _format_value_mappings(self, linked_schema: SchemaLinkerOutput) -> str:
        if not linked_schema.value_mappings:
            return "None"
        lines = []
        for m in linked_schema.value_mappings:
            lines.append(f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}")
        return "\n".join(lines)

    def generate(self, user_query: str, linked_schema: SchemaLinkerOutput, classification: QueryClassifierOutput, lessons: str = "") -> SQLGeneratorOutput:
        logger.set_agent("SQL_GENERATOR")
        
        semantic_context_str = self.semantic_engine.format_for_prompt(
            relevant_tables=linked_schema.selected_tables,
            include_samples=False
        )

        dialect_rules = DialectLoader.load_dialect_rules(self.dialect)

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "DIALECT":             self.dialect.upper(),
            "DIALECT_RULES":       dialect_rules,
            "USER_QUERY":          user_query,
            "SEMANTIC_CONTEXT":    semantic_context_str,
            "SELECTED_TABLES":     ", ".join(linked_schema.selected_tables),
            "SELECTED_COLUMNS":    ", ".join(linked_schema.selected_columns),
            "VALUE_MAPPINGS":      self._format_value_mappings(linked_schema),
            "COMPLEXITY":          classification.complexity,
            "LESSONS":             lessons
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SQLGeneratorOutput,
            )
            if not self._validate_syntax(result.sql):
                logger.warning("Generated SQL failed static syntax validation — proceeding to execution.")
            logger.log_parsed_data("Generation Output", result)
            return result
        except Exception:
            logger.error("SQL generation failed.")
            raise
        finally:
            logger.reset_agent()
