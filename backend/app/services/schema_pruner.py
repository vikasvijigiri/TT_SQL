from typing import List, Dict
from pydantic import BaseModel
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.utils.logger import logger
from backend.app.core.config import get_prompt_path

class TablePruningResult(BaseModel):
    selected_tables: List[str]
    reasoning: str

class ColumnPruningResult(BaseModel):
    selected_columns: List[str]
    reasoning: str

class TablePruner:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.prompt_path = get_prompt_path("table_pruner.yaml")

    def prune(self, user_query: str, lessons: str = "") -> List[str]:
        logger.set_agent("TABLE_PRUNER")
        logger.info(f"Pruning tables for query: '{user_query}'")

        # Get full schema summary (no columns, no samples for pruning to save tokens)
        full_context = self.semantic_engine.format_for_prompt(slim=True)
        
        messages = PromptLoader.load(self.prompt_path, variables={
            "USER_QUERY": user_query,
            "SEMANTIC_CONTEXT": full_context,
            "DYNAMIC_REASONING_PROTOCOL": lessons
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=TablePruningResult,
            )
            logger.info(f"PRUNING REASONING: {result.reasoning}")
            logger.info(f"Selected {len(result.selected_tables)} tables: {result.selected_tables}")
            return result.selected_tables
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

    def prune(self, user_query: str, relevant_tables: List[str], lessons: str = "") -> Dict[str, List[str]]:
        logger.set_agent("COLUMN_PRUNER")
        logger.info(f"Pruning columns for {len(relevant_tables)} tables.")

        # Get context for selected tables (including samples for high-precision column matching)
        context = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables,
            include_samples=True
        )
        
        messages = PromptLoader.load(self.prompt_path, variables={
            "USER_QUERY": user_query,
            "SEMANTIC_CONTEXT": context,
            "DYNAMIC_REASONING_PROTOCOL": lessons
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ColumnPruningResult,
            )
            
            # Convert flat list "table.column" to Dict[table, List[column]]
            table_columns = {}
            for fqn in result.selected_columns:
                if "." in fqn:
                    parts = fqn.split(".")
                    col = parts[-1]
                    tbl = ".".join(parts[:-1])
                    if tbl not in table_columns:
                        table_columns[tbl] = []
                    table_columns[tbl].append(col)
            
            logger.info(f"Selected columns across {len(table_columns)} tables.")
            return table_columns
        except Exception as e:
            logger.error(f"Column pruning failed: {e}")
            return {}
        finally:
            logger.reset_agent()
