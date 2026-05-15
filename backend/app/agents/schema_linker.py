from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.models.schemas import SchemaLinkerOutput
from backend.app.utils.logger import logger
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.services.schema_pruner import TablePruner, ColumnPruner

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("schema_linker.yaml")


class SchemaLinker:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.table_pruner = TablePruner(llm_client, semantic_engine)
        self.column_pruner = ColumnPruner(llm_client, semantic_engine)

    def link_schema(self, user_query: str, dialect: str = "snowflake", lessons: str = "", force_full: bool = False) -> SchemaLinkerOutput:
        logger.set_agent("SCHEMA_LINKER")
        
        if force_full:
            logger.info("Small schema detected. Forcing full context.")
            all_tables = [t.name for t in self.semantic_engine.context.tables]
            # Flatten all columns into FQNs for deterministic mapping
            all_columns_fqn = []
            for t in self.semantic_engine.context.tables:
                for c in t.columns:
                    all_columns_fqn.append(f"{t.name}.{c.name}")
                
            return SchemaLinkerOutput(
                reasoning="Small schema; using full context for 100% precision.",
                selected_tables=all_tables,
                selected_columns=all_columns_fqn,
                value_mappings=[]
            )

        logger.info(f"Linking schema for query: '{user_query}'")

        # 1. Prune Tables First (Slim)
        relevant_tables = self.table_pruner.prune(user_query, lessons=lessons)
        
        # 2. Prune Columns for those tables
        table_columns = self.column_pruner.prune(user_query, relevant_tables, lessons=lessons)
        
        # 3. Get reduced context with full column info AND SAMPLES for the relevant columns only
        semantic_context_str = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            include_samples=True
        )

        dialect_rules = DialectLoader().load_dialect_rules(dialect)
        messages = PromptLoader.load(PROMPT_PATH, variables={
            "SEMANTIC_CONTEXT": semantic_context_str,
            "USER_QUERY": user_query,
            "LESSONS": lessons,
            "DIALECT_RULES": dialect_rules
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SchemaLinkerOutput,
            )
            logger.log_parsed_data("Linked Schema", result)
            return result
        except Exception:
            logger.error("Schema linking failed.")
            raise
        finally:
            logger.reset_agent()
