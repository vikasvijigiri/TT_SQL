from typing import List, Dict
from pydantic import BaseModel
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.utils.logger import logger
from backend.app.core.config import get_prompt_path

class TablePruningResult(BaseModel):
    relevant_tables: List[str]
    reasoning: str

class ColumnPruningResult(BaseModel):
    table_columns: Dict[str, List[str]]
    reasoning: str

class TablePruner:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.prompt_path = get_prompt_path("table_pruner.yaml")

    def prune(self, user_query: str) -> List[str]:
        logger.set_agent("TABLE_PRUNER")
        logger.info(f"Pruning tables for query: '{user_query}'")

        # Get full schema summary (no columns, no samples for pruning to save tokens)
        full_context = self.semantic_engine.format_for_prompt(slim=True)
        
        messages = PromptLoader.load(self.prompt_path, variables={
            "USER_QUERY": user_query,
            "SEMANTIC_CONTEXT": full_context
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=TablePruningResult,
            )
            logger.info(f"Selected {len(result.relevant_tables)} tables: {result.relevant_tables}")
            return result.relevant_tables
        except Exception as e:
            logger.error(f"Table pruning failed: {e}")
            return []
        finally:
            logger.reset_agent()

class ColumnPruner:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.prompt_path = get_prompt_path("column_pruner.yaml")

    def prune(self, user_query: str, relevant_tables: List[str]) -> Dict[str, List[str]]:
        logger.set_agent("COLUMN_PRUNER")
        logger.info(f"Pruning columns for {len(relevant_tables)} tables.")

        # Get context for selected tables (columns included but no samples to save tokens)
        context = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            include_samples=False
        )
        
        messages = PromptLoader.load(self.prompt_path, variables={
            "USER_QUERY": user_query,
            "SEMANTIC_CONTEXT": context
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ColumnPruningResult,
            )
            logger.info(f"Selected columns across {len(result.table_columns)} tables.")
            return result.table_columns
        except Exception as e:
            logger.error(f"Column pruning failed: {e}")
            return {}
        finally:
            logger.reset_agent()
