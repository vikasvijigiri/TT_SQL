import sqlglot
from src.utils.llm import LLMClient
from src.utils.prompt_loader import PromptLoader
from src.utils.dialect_loader import DialectLoader
from src.schema.models import SQLGeneratorOutput, SchemaLinkerOutput, QueryClassifierOutput
from src.utils.logger import logger
from src.indexing.semantic_engine import SemanticContextEngine

PROMPT_PATH = "src/prompts/sql_generator.yaml"

# Dialect-specific notes injected into the prompt
_DIALECT_NOTES = {
    "snowflake": "Follow all Snowflake rules in the system prompt.",
    "bigquery": "Follow BigQuery syntax rules.",
    "sqlite": "Follow SQLite syntax rules.",
}

# Complexity-specific guidance blocks injected into the prompt
_COMPLEXITY_GUIDANCE = {
    "easy": (
        "This is a SIMPLE query.\n"
        "Write a direct SELECT statement. No CTEs, no JOINs, no aggregations unless trivially required.\n"
        "Keep it concise and readable."
    ),
    "non_nested_complex": (
        "This query requires JOINs and/or aggregations.\n"
        "Guidelines:\n"
        "  - Identify the correct JOIN keys from the schema foreign key hints.\n"
        "  - Apply all filters in WHERE (pre-aggregation) or HAVING (post-aggregation).\n"
        "  - Ensure GROUP BY exactly matches the SELECT non-aggregate columns.\n"
        "  - Use window functions (RANK, ROW_NUMBER) for ranked/top-N results."
    ),
    "nested_complex": (
        "This is a COMPLEX multi-step query.\n"
        "You MUST use Common Table Expressions (CTEs) using the WITH clause to decompose the logic.\n"
        "Guidelines:\n"
        "  - Break the problem into named steps (e.g., step1_candidates, step2_ranked, etc.).\n"
        "  - Each CTE should do ONE logical thing.\n"
        "  - NEVER use correlated subqueries in WHERE if a CTE + JOIN can achieve the same result.\n"
        "  - Avoid deeply nested subqueries — Snowflake may not support all subquery types."
    ),
}


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
