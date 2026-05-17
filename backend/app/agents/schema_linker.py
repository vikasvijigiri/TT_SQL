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
        logger.info(f"Linking schema for query: '{user_query}'")
        
        if not self.semantic_engine.context:
            self.semantic_engine.build_context()

        all_tables = [t.name for t in self.semantic_engine.context.tables]
        full_slim = self.semantic_engine.format_for_prompt(slim=True)
        full_tokens = len(full_slim) // 4

        # 1. Multi-Tier Table Pruning Check
        if force_full or full_tokens <= 2000 or len(all_tables) <= 5:
            logger.info(f"Compact database schema detected (~{full_tokens} tokens, {len(all_tables)} tables). Skipping Table Pruner.")
            relevant_tables = all_tables
        else:
            logger.info(f"Extensive database schema detected (~{full_tokens} tokens, {len(all_tables)} tables). Running Table Pruner.")
            relevant_tables = self.table_pruner.prune(user_query, lessons=lessons)
            if not relevant_tables:
                logger.warning(f"Table pruning returned empty or failed. Fallback to top 45 tables to prevent exceeding 131K token limits.")
                relevant_tables = all_tables[:45]

        # 2. Multi-Tier Column Pruning Check
        pruned_context = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            include_samples=True
        )
        pruned_tokens = len(pruned_context) // 4
        
        # Absolute Token Safety Guard for Bedrock 131K limit
        if pruned_tokens > 95000:
            logger.warning(f"Pruned context (~{pruned_tokens} tokens) exceeds safe Bedrock limits. Restricting table subset.")
            relevant_tables = relevant_tables[:35]
            pruned_context = self.semantic_engine.format_for_prompt(
                relevant_tables=relevant_tables,
                include_samples=True
            )
            pruned_tokens = len(pruned_context) // 4
        
        if pruned_tokens <= 2500:
            logger.info(f"Pruned table context is compact (~{pruned_tokens} tokens). Skipping Column Pruner.")
            table_columns = None
        else:
            logger.info(f"Pruned table context is extensive (~{pruned_tokens} tokens). Running Column Pruner.")
            table_columns = self.column_pruner.prune(user_query, relevant_tables, lessons=lessons)

        # 3. Format final context for SCHEMA_LINKER
        semantic_context_str = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            include_samples=True
        )

        dialect_reasoning = DialectLoader().load_dialect_reasoning(dialect)
        messages = PromptLoader.load(PROMPT_PATH, variables={
            "SEMANTIC_CONTEXT": semantic_context_str,
            "USER_QUERY": user_query,
            "LESSONS": lessons,
            "DIALECT_RULES": dialect_reasoning
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
