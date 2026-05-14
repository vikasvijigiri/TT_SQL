from src.utils.llm import LLMClient
from src.utils.prompt_loader import PromptLoader
from src.schema.models import SchemaLinkerOutput
from src.utils.logger import logger
from src.utils.dialect_loader import DialectLoader
from src.indexing.semantic_engine import SemanticContextEngine
from src.mapping.pruner import TablePruner, ColumnPruner

PROMPT_PATH = "src/prompts/schema_linker.yaml"


class SchemaLinker:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.table_pruner = TablePruner(llm_client, semantic_engine)
        self.column_pruner = ColumnPruner(llm_client, semantic_engine)

    def link_schema(self, user_query: str, dialect: str = "snowflake", lessons: str = "") -> SchemaLinkerOutput:
        logger.set_agent("SCHEMA_LINKER")
        logger.info(f"Linking schema for query: '{user_query}'")

        # 1. Prune Tables First (Slim)
        relevant_tables = self.table_pruner.prune(user_query)
        
        # 2. Prune Columns for those tables
        table_columns = self.column_pruner.prune(user_query, relevant_tables)
        
        # 3. Get reduced context with full column info AND SAMPLES for the relevant columns only
        semantic_context_str = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            include_samples=True
        )

        dialect_rules = DialectLoader.load_dialect_rules(dialect)
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
