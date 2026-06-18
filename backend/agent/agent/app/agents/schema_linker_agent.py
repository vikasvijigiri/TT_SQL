import typing
from agent.app.utils.llm import LLMClient
from agent.app.models.schemas import SchemaLinkerOutput
from agent.app.utils.logger import logger
from agent.app.services.semantic_engine import SemanticContextEngine
from agent.app.services.schema_pruner import TablePruner, ColumnPruner
from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from agent.app.core.retrieval.fallback_strategy import ProgressiveExpansionStrategy

from agent.app.core.config import get_prompt_path

PROMPT_PATH = get_prompt_path("schema_linker.yaml")


class SchemaLinkerAgent:
    def __init__(self, llm_client: LLMClient, semantic_engine: SemanticContextEngine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.table_pruner = TablePruner(llm_client, semantic_engine)
        self.column_pruner = ColumnPruner(llm_client, semantic_engine)

    def _restore_join_keys(self, result: SchemaLinkerOutput) -> SchemaLinkerOutput:
        """
        Post-processing safety guard applied to the SchemaLinker LLM output.

        The SQL Generator builds its schema context exclusively from
        result.selected_columns. If a lookup table's identifier/Code column is
        missing from that list (while its Description column was kept), the
        generator will be forced to join on Description text instead of the Code
        column Ã¢â‚¬â€ which always produces zero matching rows.

        This method inspects the full schema for each table whose columns appear
        in selected_columns. For any lookup-like table (has both a code-type
        column AND a description-type column) where the description was selected
        but the code column was omitted, the code column is automatically added.

        """
        JOIN_KEY_HINTS = {"code", "id", "key", "num", "number", "ref", "fk", "pk"}
        DESC_HINTS = {"description", "desc", "name", "label", "text", "title"}

        if not self.semantic_engine.context:
            return result

        # Build a map keyed by the SHORT table name (last segment, lowercased, unquoted)
        # so that "ICD10CODE" matches "DEATH.DEATH.ICD10CODE".
        # Value is (full_fqn, [all_column_names]).
        short_to_full = {}
        for tbl in self.semantic_engine.context.tables:
            short_key = tbl.name.lower().replace('"', "").split(".")[-1]
            short_to_full[short_key] = (tbl.name, [col.name for col in tbl.columns])

        # Parse selected_columns into {table_short_name: [col_name, ...]}
        # Strips quotes first so both "ICD10CODE"."Description" and
        # DEATH.DEATH.ICD10CODE.Description map to short key "icd10code".
        selected_map: dict[str, typing.Any] = {}  # short_key -> [col_name, ...]
        for fqn in result.selected_columns:
            clean = fqn.replace('"', "")  # remove all surrounding quotes
            parts = clean.split(".")
            if len(parts) >= 2:
                col_name = parts[-1]
                tbl_short = parts[-2].lower()  # second-to-last segment = table name
                selected_map.setdefault(tbl_short, []).append(col_name)

        added_fqns = []
        for tbl_short, selected_cols in selected_map.items():
            if tbl_short not in short_to_full:
                continue
            full_fqn, all_cols = short_to_full[tbl_short]

            selected_set = {c.lower() for c in selected_cols}

            # Identify identifier-like and description-like columns in this table
            code_cols = [
                c for c in all_cols if any(h in c.lower() for h in JOIN_KEY_HINTS)
            ]
            desc_cols = [c for c in all_cols if any(h in c.lower() for h in DESC_HINTS)]

            # Lookup pattern: table has BOTH a code-type AND a desc-type column.
            # If the desc column was selected but the code column was omitted,
            # the SQL Generator will be forced to join on text Ã¢â‚¬â€ restore it.
            has_desc_selected = any(c.lower() in selected_set for c in desc_cols)
            missing_code_cols = [c for c in code_cols if c.lower() not in selected_set]

            if has_desc_selected and missing_code_cols:
                for col in missing_code_cols:
                    # Use the canonical full FQN from the schema so the SQL Generator
                    # can filter the schema context correctly
                    fqn_to_add = f"{full_fqn}.{col}"
                    if fqn_to_add not in result.selected_columns:
                        result.selected_columns.append(fqn_to_add)
                        added_fqns.append(fqn_to_add)
                        logger.info(
                            f"[SchemaLinker.JoinKeyGuard] Restored '{fqn_to_add}' Ã¢â‚¬â€ "
                            f"description column in '{full_fqn}' was selected but "
                            f"join-key '{col}' was absent from selected_columns."
                        )

        if added_fqns:
            logger.warning(
                f"[SchemaLinker.JoinKeyGuard] Auto-restored {len(added_fqns)} "
                f"join-key column(s): {added_fqns}. This prevents the SQL "
                f"Generator from joining on the wrong column."
            )

        return result

    def _enforce_valuemapping_tables(
        self, result: SchemaLinkerOutput
    ) -> SchemaLinkerOutput:
        """
        Ensure every table referenced in a value mapping column is present in selected_tables.

        The schema linker sometimes correctly maps a column (e.g. "contents.content")
        in value_mappings but omits the owning table from selected_tables. This leaves
        the SQL generator without the table schema it needs to write a valid join.

        Column references can be:
          - "table.column"         Ã¢â€ â€™ table name is the first segment
          - "db.schema.table.col"  Ã¢â€ â€™ table name is the third-to-last segment
        Plain column names with no dot prefix are skipped (table is ambiguous).
        """
        if not result.value_mappings or not self.semantic_engine.context:
            return result

        # Build short base name Ã¢â€ â€™ full FQN for all tables in the context
        known: dict = {}
        for t in self.semantic_engine.context.tables:
            short = t.name.lower().replace('"', "").split(".")[-1]
            known[short] = t.name

        selected_short = {
            t.lower().replace('"', "").split(".")[-1] for t in result.selected_tables
        }
        added = []

        for vm in result.value_mappings:
            col_ref = (vm.column or "").replace('"', "")
            if "." not in col_ref:
                continue  # no table prefix Ã¢â‚¬â€ cannot determine owning table
            # Take the segment immediately before the column name
            parts = col_ref.split(".")
            tbl_short = parts[-2].lower()

            if tbl_short in selected_short:
                continue  # already selected

            if tbl_short in known:
                full_fqn = known[tbl_short]
                result.selected_tables.append(full_fqn)
                selected_short.add(tbl_short)
                added.append(full_fqn)
                logger.info(
                    f"[SchemaLinker.ValueMapGuard] Added missing table '{full_fqn}' "
                    f"referenced by value mapping column '{col_ref}'."
                )

        if added:
            logger.warning(
                f"[SchemaLinker.ValueMapGuard] Auto-added {len(added)} table(s) "
                f"whose columns appear in value mappings: {added}"
            )
        return result

    def link_schema(
        self,
        user_query: str,
        dialect: str = "snowflake",
        lessons: str = "",
        force_full: bool = False,
        relevant_tables: List[str] | None = None,
        table_columns: Dict[str, List[str]] | None = None,
    ) -> SchemaLinkerOutput:
        logger.set_agent("SCHEMA_LINKER")
        logger.info(f"Linking schema for query: '{user_query}'")

        if not self.semantic_engine.context:
            self.semantic_engine.build_context()

        all_tables = [t.name for t in self.semantic_engine.context.tables]
        full_slim = self.semantic_engine.format_for_prompt(slim=True)
        full_tokens = len(full_slim) // 4

        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)

        # 1. Multi-Tier Table Pruning Check with Progressive Fallback
        if relevant_tables is not None:
            logger.info(f"Using pre-pruned table list with {len(relevant_tables)} tables.")
        elif force_full or full_tokens <= 4000 or len(all_tables) <= 5:
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
                fallback = ProgressiveExpansionStrategy(retriever)
                narrowed_ctx, _, _ = fallback.execute_with_fallback(
                    user_query, self.semantic_engine.context
                )
                relevant_tables = [t.name for t in narrowed_ctx.tables]

        # 2. Multi-Tier Column Pruning Check
        if table_columns is not None:
            logger.info(f"Using pre-pruned column mapping.")
        else:
            pruned_context = self.semantic_engine.format_for_prompt(
                relevant_tables=relevant_tables, include_samples=True
            )
            pruned_tokens = len(pruned_context) // 4

            # Absolute Token Safety Guard for Bedrock 131K limit
            if pruned_tokens > 95000:
                logger.warning(
                    f"Pruned context (~{pruned_tokens} tokens) exceeds safe Bedrock limits. Restricting table subset."
                )
                relevant_tables = relevant_tables[:35]
                pruned_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=relevant_tables, include_samples=True
                )
                pruned_tokens = len(pruned_context) // 4

            if pruned_tokens <= 4500:
                logger.info(
                    f"Pruned table context is compact (~{pruned_tokens} tokens). Skipping Column Pruner."
                )
                table_columns = None
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

        # 3. Assemble surgical prompt using PromptAssembler
        from agent.app.core.prompts.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(dialect=dialect, stage="SCHEMA_LINKER")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="SCHEMA_LINKER",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons=lessons,
        )

        system_prompt = assembled.system_prompt
        user_prompt = assembled.user_prompt

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SchemaLinkerOutput,
            )
            # 4. Post-processing: restore any join-key columns the LLM omitted
            result = self._restore_join_keys(result)
            # 5. Post-processing: ensure tables referenced in value mappings are selected
            result = self._enforce_valuemapping_tables(result)
            logger.log_parsed_data("Linked Schema", result)
            return result
        except Exception:
            logger.error("Schema linking failed.")
            raise
        finally:
            logger.reset_agent()
