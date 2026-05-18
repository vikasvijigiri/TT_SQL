from typing import List, Dict, Optional
from pydantic import BaseModel
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.utils.logger import logger
from backend.app.core.config import get_prompt_path
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever, QueryIntentAnalysis
from backend.app.models.schemas import SemanticContext

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

    def prune(self, user_query: str, lessons: str = "", dialect: str = "snowflake") -> List[str]:
        logger.set_agent("TABLE_PRUNER")
        logger.info(f"Pruning tables for query: '{user_query}'")

        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)

        # Pre-filter candidate tables using hierarchical retrieval to avoid token overload
        full_ctx = self.semantic_engine.context or self.semantic_engine.build_context()
        narrowed_ctx, _, _ = retriever.narrow_schema(user_query, full_ctx)
        
        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=dialect, stage="TABLE_PRUNER")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="TABLE_PRUNER",
            context=narrowed_ctx,
            intent=intent,
            relevant_tables=[t.name for t in narrowed_ctx.tables],
            lessons=lessons
        )

        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt

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
            return [t.name for t in narrowed_ctx.tables]
        finally:
            logger.reset_agent()

class ColumnPruner:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.prompt_path = get_prompt_path("column_pruner.yaml")

    def prune(self, user_query: str, relevant_tables: List[str], lessons: str = "", dialect: str = "snowflake") -> Dict[str, List[str]]:
        logger.set_agent("COLUMN_PRUNER")
        logger.info(f"Pruning columns for {len(relevant_tables)} tables.")

        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)

        full_ctx = self.semantic_engine.context or self.semantic_engine.build_context()
        selected_tbl_objs = [t for t in full_ctx.tables if any(rt.lower().replace('"', '') in t.name.lower().replace('"', '') for rt in relevant_tables)]
        
        narrowed_ctx, table_cols_map, _ = retriever.narrow_schema(user_query, SemanticContext(tables=selected_tbl_objs), force_tables=relevant_tables)

        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=dialect, stage="COLUMN_PRUNER")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="COLUMN_PRUNER",
            context=narrowed_ctx,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_cols_map,
            lessons=lessons
        )

        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ColumnPruningResult,
            )
            
            # Convert flat list "table.column" to Dict[table, List[column]]
            final_table_columns = {}
            for fqn in result.selected_columns:
                if "." in fqn:
                    parts = fqn.split(".")
                    col = parts[-1]
                    tbl = ".".join(parts[:-1])
                    if tbl not in final_table_columns:
                        final_table_columns[tbl] = []
                    final_table_columns[tbl].append(col)
            
            logger.info(f"Selected columns across {len(final_table_columns)} tables.")
            return final_table_columns
        except Exception as e:
            logger.error(f"Column pruning failed: {e}")
            return table_cols_map
        finally:
            logger.reset_agent()
