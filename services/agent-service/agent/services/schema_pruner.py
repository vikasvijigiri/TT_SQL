import typing
from typing import List, Dict
from pydantic import BaseModel
from agent.services.llm import LLMClient
from agent.services.semantic_engine import SemanticContextEngine
from agent.services.logger import logger
from agent.app.core.config import get_prompt_path
from agent.app.core.retrieval.hierarchical_retriever import (
    HierarchicalRetriever,
    QueryIntentAnalysis,
)
from agent.contracts.schemas import SemanticContext


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

    def prune(
        self,
        user_query: str,
        lessons: str = "",
        dialect: str = "snowflake",
        intent: QueryIntentAnalysis = None,  # type: ignore
    ) -> List[str]:
        logger.set_agent("TABLE_PRUNER")
        logger.info(f"Pruning tables (hybrid/vector retrieval) for query: '{user_query}'")

        retriever = HierarchicalRetriever()
        if intent is None:
            intent = retriever.analyze_intent(user_query)

        full_ctx = self.semantic_engine.context or self.semantic_engine.build_context()

        # [META-CATALOG IMPLEMENTATION]
        if len(full_ctx.tables) > 100:
            logger.info(f"[TablePruner] Massive schema detected ({len(full_ctx.tables)} tables). Bypassing BM25 and utilizing Meta-Catalog injection.")
            
            # Generate highly compressed meta-catalog string
            catalog_lines = ["[META-CATALOG INDEX (Table Names and Descriptions)]"]
            for t in full_ctx.tables:
                desc = t.description[:100].replace('\n', ' ') if t.description else "No description available"
                catalog_lines.append(f"- {t.name}: {desc}")
            meta_catalog_str = "\n".join(catalog_lines)
            
            try:
                with open(self.prompt_path, "r", encoding="utf-8") as f:
                    sys_prompt = f.read().strip()
            except Exception:
                sys_prompt = "You are a TablePruner. Select the exact tables needed."
                
            sys_prompt += "\n\n" + meta_catalog_str
            user_prompt = f"User Query: {user_query}\n\nBased on the META-CATALOG INDEX above, select the exact minimal set of tables needed to answer this query. Remember to include the anchor fact table and any metadata/lookup tables required."
            
            try:
                result = self.llm.generate_structured(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    response_model=TablePruningResult,
                )
                logger.info(f"[MetaCatalog] PRUNING REASONING: {result.reasoning}")
                valid_tables = [t for t in result.selected_tables if any(t.lower() == ft.name.lower() for ft in full_ctx.tables)]
                if valid_tables:
                    logger.info(f"[MetaCatalog] Selected {len(valid_tables)} tables: {valid_tables}")
                    logger.reset_agent()
                    return valid_tables
                else:
                    logger.warning("[MetaCatalog] LLM selected 0 valid tables. Falling back to BM25.")
            except Exception as e:
                logger.error(f"[MetaCatalog] LLM refinement failed: {e}. Falling back to BM25.")

        # [FALLBACK TO HIERARCHICAL BM25]
        narrowed_ctx, _, _ = retriever.narrow_schema(user_query, full_ctx)
        selected_tables = [t.name for t in narrowed_ctx.tables]
        
        # Expand tables dynamically to include direct foreign-key-linked neighbors
        # to prevent join-path retrieval bias on tables with low semantic query matching.
        import re
        selected_set = {t.lower().replace('"', "").replace('`', "") for t in selected_tables}
        expanded_any = False
        
        for tbl in full_ctx.tables:
            tbl_clean = tbl.name.lower().replace('"', "").replace('`', "")
            if tbl_clean in selected_set:
                for fk_str in tbl.foreign_keys or []:
                    # FK format: FOREIGN KEY (col) REFERENCES ref_table(ref_col)
                    match = re.search(r"REFERENCES\s+([^\s(]+)", fk_str, re.IGNORECASE)
                    if match:
                        ref_tbl = match.group(1).strip().strip('"').strip('`')
                        ref_clean = ref_tbl.lower().split(".")[-1]
                        
                        # Find matching table in full schema
                        for cand in full_ctx.tables:
                            cand_clean = cand.name.lower().replace('"', "").replace('`', "")
                            if cand_clean == ref_clean or cand_clean.endswith("." + ref_clean):
                                if cand_clean not in selected_set:
                                    selected_tables.append(cand.name)
                                    selected_set.add(cand_clean)
                                    expanded_any = True
                                    logger.info(f"[VectorPruner] Expanded neighbors: added join anchor '{cand.name}'")

        if expanded_any:
            logger.info(f"[VectorPruner] Selected tables after FK expansion: {selected_tables}")

        # If candidate table count is small, skip LLM pruning entirely to save cost and avoid LLM hallucinations/errors
        if len(selected_tables) <= 4:
            logger.info(f"[TablePruner] Candidate table count is small ({len(selected_tables)} tables). Skipping LLM table pruning.")
            logger.reset_agent()
            return selected_tables

        logger.info(f"[TablePruner] Running LLM table pruning on {len(selected_tables)} candidate tables.")
        from agent.app.core.prompts.prompt_assembler import PromptAssembler
        
        # Build a filtered context containing only the candidate tables
        filtered_tables = [t for t in full_ctx.tables if t.name in selected_tables]
        filtered_ctx = SemanticContext(tables=filtered_tables)

        assembler = PromptAssembler(dialect=dialect, stage="TABLE_PRUNER")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="TABLE_PRUNER",
            context=filtered_ctx,
            intent=intent,
            relevant_tables=selected_tables,
            lessons=lessons,
        )

        try:
            result = self.llm.generate_structured(
                system_prompt=assembled.system_prompt,
                user_prompt=assembled.user_prompt,
                response_model=TablePruningResult,
            )
            logger.info(f"PRUNING REASONING: {result.reasoning}")
            logger.info(
                f"Selected {len(result.selected_tables)} tables: {result.selected_tables}"
            )
            # Ensure selected tables actually exist in our candidate set (failsafe)
            valid_tables = [t for t in result.selected_tables if t in selected_tables]
            if not valid_tables:
                logger.warning("[TablePruner] LLM selected 0 valid tables. Falling back to all candidate tables.")
                return selected_tables
            return valid_tables
        except Exception as e:
            logger.error(f"Table pruning LLM refinement failed: {e}")
            return selected_tables
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
        full_ctx,
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
                tbl_clean = tbl.name.lower().replace('"', "")
                is_relevant = any(
                    rt.lower().replace('"', "") == tbl_clean
                    or tbl_clean.endswith("." + rt.lower().split(".")[-1])
                    for rt in relevant_tables
                )
                if is_relevant:
                    all_table_cols[tbl.name] = [col.name for col in tbl.columns]

        restored_count = 0
        for tbl_name, all_cols in all_table_cols.items():
            current_cols = set(selected_columns.get(tbl_name, []))

            # Identify which columns in this table are "code-like" vs "desc-like"
            code_cols = [
                c for c in all_cols if any(h in c.lower() for h in JOIN_KEY_HINTS)
            ]
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

    def prune(
        self,
        user_query: str,
        relevant_tables: List[str],
        lessons: str = "",
        dialect: str = "snowflake",
        intent: QueryIntentAnalysis = None,  # type: ignore
    ) -> Dict[str, List[str]]:
        logger.set_agent("COLUMN_PRUNER")
        logger.info(f"Pruning columns (hybrid/vector retrieval) for {len(relevant_tables)} tables.")

        retriever = HierarchicalRetriever()
        if intent is None:
            intent = retriever.analyze_intent(user_query)

        full_ctx = self.semantic_engine.context or self.semantic_engine.build_context()
        selected_tbl_objs = [
            t
            for t in full_ctx.tables
            if any(
                rt.lower().replace('"', "") in t.name.lower().replace('"', "")
                for rt in relevant_tables
            )
        ]

        narrowed_ctx, table_cols_map, _ = retriever.narrow_schema(
            user_query,
            SemanticContext(tables=selected_tbl_objs),
            force_tables=relevant_tables,
        )

        # Estimate the token count of this narrowed context
        slim_context = self.semantic_engine.format_for_prompt(
            relevant_tables=relevant_tables, include_samples=False
        )
        estimated_tokens = len(slim_context) // 4

        # If context is already small (<= 3000 tokens), skip LLM column pruning entirely
        if estimated_tokens <= 3000:
            logger.info(f"[ColumnPruner] Candidate columns context is small (~{estimated_tokens} tokens). Skipping LLM column pruning.")
            final_table_columns = self._restore_join_keys(
                table_cols_map, relevant_tables, full_ctx
            )
            logger.reset_agent()
            return final_table_columns

        logger.info(f"[ColumnPruner] Running LLM column pruning on context with ~{estimated_tokens} tokens.")
        from agent.app.core.prompts.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(dialect=dialect, stage="COLUMN_PRUNER")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="COLUMN_PRUNER",
            context=narrowed_ctx,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_cols_map,
            lessons=lessons,
        )

        try:
            result = self.llm.generate_structured(
                system_prompt=assembled.system_prompt,
                user_prompt=assembled.user_prompt,
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
            final_table_columns = self._restore_join_keys(
                final_table_columns, relevant_tables, full_ctx
            )

            logger.info(f"Selected columns across {len(final_table_columns)} tables.")
            return final_table_columns
        except Exception as e:
            logger.error(f"Column pruning LLM refinement failed: {e}")
            final_table_columns = self._restore_join_keys(
                table_cols_map, relevant_tables, full_ctx
            )
            return final_table_columns
        finally:
            logger.reset_agent()


class ContextPruner:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.table_pruner = TablePruner(llm_client, semantic_engine)
        self.column_pruner = ColumnPruner(llm_client, semantic_engine)

    def prune(
        self,
        user_query: str,
        dialect: str = "snowflake",
        lessons: str = "",
        intent = None,
        force_full: bool = False,
    ) -> tuple[List[str], Dict[str, List[str]] | None]:
        logger.set_agent("CONTEXT_PRUNER")
        logger.info("Context optimization requested from Context Pruner.")
        logger.info("Analyzing column dependencies...")

        if not self.semantic_engine.context:
            self.semantic_engine.build_context()

        all_tables = [t.name for t in self.semantic_engine.context.tables]
        full_slim = self.semantic_engine.format_for_prompt(slim=True)
        full_tokens = len(full_slim) // 4

        try:
            # 1. Table Pruning Check with Progressive Fallback
            if force_full or full_tokens <= 20000 or len(all_tables) <= 15:
                logger.info(
                    f"Compact database schema detected (~{full_tokens} tokens, {len(all_tables)} tables). Skipping Table Pruner."
                )
                relevant_tables = all_tables
            else:
                logger.info(
                    f"Extensive database schema detected (~{full_tokens} tokens, {len(all_tables)} tables). Running Table Pruner."
                )
                relevant_tables = self.table_pruner.prune(
                    user_query, lessons=lessons, dialect=dialect, intent=intent
                )
                if not relevant_tables:
                    logger.warning(
                        "Table pruning returned empty. Utilizing Progressive Expansion Fallback."
                    )
                    from agent.app.core.retrieval.fallback_strategy import ProgressiveExpansionStrategy
                    fallback = ProgressiveExpansionStrategy(HierarchicalRetriever())
                    narrowed_ctx, _, _ = fallback.execute_with_fallback(
                        user_query, self.semantic_engine.context
                    )
                    relevant_tables = [t.name for t in narrowed_ctx.tables]

            # 2. Column Pruning Check
            pruned_context = self.semantic_engine.format_for_prompt(
                relevant_tables=relevant_tables, include_samples=True
            )
            pruned_tokens = len(pruned_context) // 4

            # Absolute Token Safety Guard for Bedrock 131K limit
            if pruned_tokens > 95000:
                logger.warning(
                    f"Pruned context (~{pruned_tokens} tokens) exceeds safe limits. Restricting table subset."
                )
                relevant_tables = relevant_tables[:35]
                pruned_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=relevant_tables, include_samples=True
                )
                pruned_tokens = len(pruned_context) // 4

            table_columns = None
            if pruned_tokens <= 20000:
                logger.info(
                    f"Pruned table context is compact (~{pruned_tokens} tokens). Skipping Column Pruner."
                )
            else:
                logger.info(
                    f"Pruned table context is extensive (~{pruned_tokens} tokens). Running Column Pruner."
                )
                table_columns = self.column_pruner.prune(
                    user_query,
                    relevant_tables,
                    lessons=lessons,
                    dialect=dialect,
                    intent=intent,
                )

            logger.info("Context pruning successful.")
            return relevant_tables, table_columns
        except Exception as e:
            logger.error(f"Context pruning failed: {e}")
            return all_tables, None
        finally:
            logger.reset_agent()
