from typing import List, Dict
from pydantic import BaseModel
from backend.app.utils.llm import LLMClient
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.utils.logger import logger
from backend.app.core.config import get_prompt_path
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

    def prune(self, user_query: str, lessons: str = "", dialect: str = "snowflake", intent: QueryIntentAnalysis = None) -> List[str]:
        logger.set_agent("TABLE_PRUNER")
        logger.info(f"Pruning tables for query: '{user_query}'")

        retriever = HierarchicalRetriever()
        if intent is None:
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

    def _restore_join_keys(
        self,
        selected_columns: Dict[str, List[str]],
        relevant_tables: List[str],
        full_ctx
    ) -> Dict[str, List[str]]:
        """
        Post-pruning safety guard: restores join-key columns that the LLM may have
        incorrectly pruned. 

        For each selected table, if the table appears to be a lookup/dimension table
        (i.e. it has both a 'Code'-like column AND a 'Description'-like column), and
        the 'Code' column is missing from the selection while the 'Description' column
        was kept, we restore the 'Code' column.

        This prevents the SQL Generator from being forced to join on Description text
        instead of the actual code identifier, which always produces 0 matching rows.
        """
        # Heuristics: column name patterns that indicate identifier/join-key columns
        JOIN_KEY_HINTS = {"code", "id", "key", "num", "number", "ref", "fk", "pk"}
        # Heuristics: column name patterns that indicate description/text columns
        DESC_HINTS = {"description", "desc", "name", "label", "text", "title"}

        # Build a fast lookup: table_name -> all columns in that table
        all_table_cols: Dict[str, List[str]] = {}
        if full_ctx:
            for tbl in full_ctx.tables:
                tbl_clean = tbl.name.lower().replace('"', '')
                is_relevant = any(
                    rt.lower().replace('"', '') == tbl_clean or
                    tbl_clean.endswith('.' + rt.lower().split('.')[-1])
                    for rt in relevant_tables
                )
                if is_relevant:
                    all_table_cols[tbl.name] = [col.name for col in tbl.columns]

        restored_count = 0
        for tbl_name, all_cols in all_table_cols.items():
            current_cols = set(selected_columns.get(tbl_name, []))

            # Identify which columns in this table are "code-like" vs "desc-like"
            code_cols = [c for c in all_cols if any(h in c.lower() for h in JOIN_KEY_HINTS)]
            desc_cols = [c for c in all_cols if any(h in c.lower() for h in DESC_HINTS)]

            # If this table has BOTH code-like and description-like columns, it's likely
            # a lookup table. If we selected a desc column but NOT the code column,
            # restore the code column.
            has_desc_selected = any(c in current_cols for c in desc_cols)
            missing_code_cols = [c for c in code_cols if c not in current_cols]

            if has_desc_selected and missing_code_cols:
                if tbl_name not in selected_columns:
                    selected_columns[tbl_name] = list(current_cols)
                for col in missing_code_cols:
                    selected_columns[tbl_name].append(col)
                    restored_count += 1
                    logger.info(
                        f"[JoinKeyGuard] Restored pruned join-key column: {tbl_name}.{col} "
                        f"(description column was kept but join-key was missing)"
                    )

        if restored_count:
            logger.warning(
                f"[JoinKeyGuard] Restored {restored_count} join-key column(s) that were "
                f"incorrectly pruned. This prevents joins on wrong columns."
            )
        return selected_columns

    def prune(self, user_query: str, relevant_tables: List[str], lessons: str = "", dialect: str = "snowflake", intent: QueryIntentAnalysis = None) -> Dict[str, List[str]]:
        logger.set_agent("COLUMN_PRUNER")
        logger.info(f"Pruning columns for {len(relevant_tables)} tables.")

        retriever = HierarchicalRetriever()
        if intent is None:
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
            
            # Apply code-level join-key safety guard AFTER LLM pruning
            final_table_columns = self._restore_join_keys(final_table_columns, relevant_tables, full_ctx)

            logger.info(f"Selected columns across {len(final_table_columns)} tables.")
            return final_table_columns
        except Exception as e:
            logger.error(f"Column pruning failed: {e}")
            return table_cols_map
        finally:
            logger.reset_agent()
