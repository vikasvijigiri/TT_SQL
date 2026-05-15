import sqlglot
import re
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.models.schemas import SQLGeneratorOutput, SchemaLinkerOutput, QueryClassifierOutput
from backend.app.utils.logger import logger
from backend.app.services.semantic_engine import SemanticContextEngine

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("sql_generator.yaml")




class AdaptiveSQLGenerator:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine, dialect: str = "snowflake"):
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
            lines.append(f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}")
        return "\n".join(lines)

    def generate(self, user_query: str, linked_schema: SchemaLinkerOutput, classification: QueryClassifierOutput, lessons: str = "") -> SQLGeneratorOutput:
        logger.set_agent("SQL_GENERATOR")
        
        # Re-map the FQN columns back to their tables for precise context pruning
        table_columns_map = {}
        for fqn in linked_schema.selected_columns:
            if "." in fqn:
                parts = fqn.split(".")
                table_name = ".".join(parts[:-1]) # Handle multi-part FQNs
                col_name = parts[-1]
                
                if table_name not in table_columns_map:
                    table_columns_map[table_name] = []
                table_columns_map[table_name].append(col_name)

        # Decide whether to include samples based on total context size
        # We want "Complete Schema" (with samples) for small databases
        temp_context = self.semantic_engine.format_for_prompt(
            relevant_tables=linked_schema.selected_tables,
            table_columns=table_columns_map,
            include_samples=False
        )
        include_samples = (len(temp_context) // 4) < 2500 # If base context is small, add samples

        semantic_context_str = self.semantic_engine.format_for_prompt(
            relevant_tables=linked_schema.selected_tables,
            table_columns=table_columns_map,
            include_samples=include_samples
        )

        dialect_rules = DialectLoader().load_dialect_rules(self.dialect)

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "DIALECT":             self.dialect.upper(),
            "DIALECT_RULES":       dialect_rules,
            "USER_QUERY":          user_query,
            "SEMANTIC_CONTEXT":    semantic_context_str,
            "VALUE_MAPPINGS":      self._format_value_mappings(linked_schema),
            "COMPLEXITY":          classification.complexity,
            "ATOMIC_STEPS":        "\n".join([f"- {s}" for s in classification.atomic_steps]),
            "GRAIN_AUDIT":         classification.grain_audit,
            "REFERENCE_SQL":       lessons,
            "DYNAMIC_REASONING_PROTOCOL": "" # Lessons already in REFERENCE_SQL context
        })
        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SQLGeneratorOutput,
            )
            # Apply Dialect Sanitizers (Generic)
            for sanitizer in self.dialect_loader.get_sanitizers(self.dialect):
                search = sanitizer.get("search")
                replace = sanitizer.get("replace")
                if search:
                    result.sql = re.sub(re.escape(search), replace, result.sql, flags=re.IGNORECASE)
            
            if not self._validate_syntax(result.sql):
                logger.warning("Generated SQL failed static syntax validation — proceeding to execution.")
            logger.log_parsed_data("Generation Output", result)
            return result
        except Exception:
            logger.error("SQL generation failed.")
            raise
        finally:
            logger.reset_agent()
