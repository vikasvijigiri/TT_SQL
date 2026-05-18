import sqlglot
import re
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from backend.app.models.schemas import SQLGeneratorOutput, SchemaLinkerOutput
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

    def generate(self, user_query: str, linked_schema: SchemaLinkerOutput, lessons: str = "") -> SQLGeneratorOutput:
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

        intent = HierarchicalRetriever().analyze_intent(user_query)
        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"
        combined_lessons = f"{val_mappings_str}\n\n{lessons}" if lessons else val_mappings_str

        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=self.dialect, stage="SQL_GENERATOR")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="SQL_GENERATOR",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=linked_schema.selected_tables,
            table_columns=table_columns_map,
            lessons=combined_lessons
        )
        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt

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
