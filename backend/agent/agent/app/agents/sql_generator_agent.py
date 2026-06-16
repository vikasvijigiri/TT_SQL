import typing
import sqlglot
import re
from typing import List
from agent.app.utils.llm import LLMClient
from agent.app.utils.dialect_loader import DialectLoader
from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from agent.app.models.schemas import SQLGeneratorOutput, SchemaLinkerOutput
from agent.app.utils.logger import logger
from agent.app.services.semantic_engine import SemanticContextEngine

from agent.app.core.config import get_prompt_path

PROMPT_PATH = get_prompt_path("sql_generator.yaml")

# Structural approach directives for diverse candidate generation.
# Each directive forces a genuinely different SQL shape so the critic can pick the best grain.
_DIVERSITY_APPROACHES = [
    (
        "Use named CTEs Ã¢â‚¬â€ one CTE per logical step, each named after what it computes. "
        "This is the baseline approach."
    ),
    (
        "HARD CONSTRAINT: ABSOLUTELY NO CTEs (no WITH clause at all). "
        "Write a single SELECT using only inline subqueries in FROM or WHERE. "
        "If your SQL starts with WITH or contains 'AS (SELECT', you have violated this directive."
    ),
    (
        "Start from the final output row: decide exactly what one output row represents, "
        "then write window functions (ROW_NUMBER, RANK, or DENSE_RANK) to derive it directly. "
        "Use QUALIFY or a wrapping SELECT with a WHERE on the window result. No CTEs."
    ),
]


class SQLGeneratorAgent:
    def __init__(
        self,
        llm_client: LLMClient,
        semantic_engine: SemanticContextEngine,
        dialect: str = "snowflake",
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
            logger.warning(f"SQLGlot syntax validation failed: {e}")
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

    def _build_table_columns_map(self, linked_schema: SchemaLinkerOutput) -> dict:
        """Pre-compute {table_fqn: [col_name, ...]} from schema linker output."""
        table_columns_map: dict[str, typing.Any] = {}
        for fqn in linked_schema.selected_columns:
            if "." in fqn:
                parts = fqn.split(".")
                table_name = ".".join(parts[:-1])
                col_name = parts[-1]
                if table_name not in table_columns_map:
                    table_columns_map[table_name] = []
                table_columns_map[table_name].append(col_name)
        return table_columns_map

    def _build_prompt(
        self,
        user_query: str,
        linked_schema: SchemaLinkerOutput,
        combined_lessons: str,
        intent,
        table_columns_map: dict,
    ):
        """Assemble the system + user prompt for SQL generation."""
        from agent.app.core.prompts.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(dialect=self.dialect, stage="SQL_GENERATOR")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="SQL_GENERATOR",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=linked_schema.selected_tables,
            table_columns=table_columns_map,
            lessons=combined_lessons,
        )
        return assembled.system_prompt, assembled.user_prompt

    def _call_llm_and_sanitize(
        self, system_prompt: str, user_prompt: str
    ) -> SQLGeneratorOutput:
        """Call LLM and apply dialect-specific post-processing sanitizers."""
        result = self.llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=SQLGeneratorOutput,
        )
        for sanitizer in self.dialect_loader.get_sanitizers(self.dialect):
            search = sanitizer.get("search")
            replace = sanitizer.get("replace")
            if search:
                result.sql = re.sub(
                    re.escape(search), replace, result.sql, flags=re.IGNORECASE
                )
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        user_query: str,
        linked_schema: SchemaLinkerOutput,
        lessons: str = "",
        intent=None,
    ) -> SQLGeneratorOutput:
        """Single-attempt SQL generation (backward-compatible)."""
        logger.set_agent("SQL_GENERATOR")
        if intent is None:
            intent = HierarchicalRetriever().analyze_intent(user_query)
        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"
        combined_lessons = (
            f"{val_mappings_str}\n\n{lessons}" if lessons else val_mappings_str
        )
        table_columns_map = self._build_table_columns_map(linked_schema)
        system_prompt, user_prompt = self._build_prompt(
            user_query, linked_schema, combined_lessons, intent, table_columns_map
        )
        try:
            result = self._call_llm_and_sanitize(system_prompt, user_prompt)
            if not self._validate_syntax(result.sql):
                logger.warning(
                    "Generated SQL failed static syntax validation Ã¢â‚¬â€ proceeding to execution."
                )
            logger.log_parsed_data("Generation Output", result)
            return result
        except Exception:
            logger.error("SQL generation failed.")
            raise
        finally:
            logger.reset_agent()

    def generate_diverse(
        self,
        user_query: str,
        linked_schema: SchemaLinkerOutput,
        lessons: str = "",
        intent=None,
        n: int = 3,
    ) -> List[SQLGeneratorOutput]:
        """
        Generate N structurally diverse SQL candidates by providing a different
        structural approach directive to each LLM call.  Duplicate SQL strings
        are filtered so only genuinely distinct candidates are returned.

        Used for complex queries where a single generation may pick the wrong
        grain or join strategy.  Returns 1Ã¢â‚¬â€œN candidates; never empty (if every
        attempt fails, falls back to a single standard generate() call).
        """
        logger.set_agent("SQL_GENERATOR")
        if intent is None:
            intent = HierarchicalRetriever().analyze_intent(user_query)
        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"
        base_lessons = (
            f"{val_mappings_str}\n\n{lessons}" if lessons else val_mappings_str
        )
        table_columns_map = self._build_table_columns_map(linked_schema)

        candidates: List[SQLGeneratorOutput] = []
        seen_sql: set = set()

        try:
            for i, approach in enumerate(_DIVERSITY_APPROACHES[:n]):
                # Prepend the directive to the user prompt so it appears BEFORE all other context,
                # not buried at the end where it gets ignored by the LLM.
                directive_header = (
                    f"=== MANDATORY STRUCTURAL DIRECTIVE (candidate {i + 1}/{n}) ===\n"
                    f"{approach}\n"
                    f"You MUST follow this directive. Violating it produces a useless duplicate.\n"
                    f"=== END DIRECTIVE ===\n\n"
                )
                try:
                    system_prompt, user_prompt = self._build_prompt(
                        user_query,
                        linked_schema,
                        base_lessons,
                        intent,
                        table_columns_map,
                    )
                    user_prompt = directive_header + user_prompt
                    result = self._call_llm_and_sanitize(system_prompt, user_prompt)
                    if result and result.sql:
                        norm = " ".join(result.sql.split()).upper()
                        if norm not in seen_sql:
                            seen_sql.add(norm)
                            candidates.append(result)
                            logger.info(
                                f"[SQLGenerator] Diverse candidate {len(candidates)}/{n} accepted."
                            )
                except Exception as e:
                    logger.warning(
                        f"[SQLGenerator] Candidate {i + 1} generation failed: {e}"
                    )

            if not candidates:
                logger.warning(
                    "[SQLGenerator] All diverse attempts failed Ã¢â‚¬â€ falling back to standard generate()."
                )
                logger.reset_agent()
                fallback = self.generate(
                    user_query, linked_schema, lessons=lessons, intent=intent
                )
                return [fallback] if fallback else []

            logger.info(
                f"[SQLGenerator] Diverse generation complete: {len(candidates)} unique candidates."
            )
            return candidates
        finally:
            logger.reset_agent()
