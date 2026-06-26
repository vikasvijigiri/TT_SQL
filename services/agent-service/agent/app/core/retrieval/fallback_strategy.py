from typing import List, Dict, Tuple
from agent.app.models.schemas import SemanticContext
from agent.app.core.retrieval.hierarchical_retriever import (
    HierarchicalRetriever,
    QueryIntentAnalysis,
)
from agent.services.logger import logger


class ProgressiveExpansionStrategy:
    """
    Enterprise safe fallback mechanism. If initial schema narrowing yields low confidence
    or too few tables, progressively expands candidate table set (5 -> 10 -> all)
    to prevent zero-knowledge retrieval failures.
    """

    def __init__(self, retriever: HierarchicalRetriever):
        self.retriever = retriever

    def execute_with_fallback(
        self, query: str, context: SemanticContext, force_tables: List[str] | None = None
    ) -> Tuple[SemanticContext, Dict[str, List[str]], QueryIntentAnalysis]:
        if not context or not context.tables:
            return (
                SemanticContext(tables=[]),
                {},
                QueryIntentAnalysis(
                    inferred_domain="Unknown",
                    target_entities=[],
                    target_metrics=[],
                    filter_conditions=[],
                    estimated_join_paths=[],
                    requires_variant_expansion=False,
                    requires_geospatial=False,
                    requires_temporal=False,
                ),
            )

        narrowed_ctx, table_cols_map, intent = self.retriever.narrow_schema(
            query, context, force_tables=force_tables
        )

        # Check confidence / table count
        if len(narrowed_ctx.tables) >= 5 or force_tables:
            return narrowed_ctx, table_cols_map, intent

        logger.warning(
            "[FallbackStrategy] Low table retrieval confidence. Initiating progressive expansion (Tier 1: top 8 tables)."
        )
        # Step up to top 8
        self.retriever.config.max_tables_per_query = max(
            8, self.retriever.config.max_tables_per_query + 3
        )
        narrowed_ctx, table_cols_map, intent = self.retriever.narrow_schema(
            query, context, force_tables=None
        )

        if (
            len(narrowed_ctx.tables) < 3
            and context.tables
            and len(context.tables) > len(narrowed_ctx.tables)
        ):
            logger.warning(
                "[FallbackStrategy] Initiating progressive expansion (Tier 2: top 15 tables)."
            )
            self.retriever.config.max_tables_per_query = max(15, len(context.tables))
            narrowed_ctx, table_cols_map, intent = self.retriever.narrow_schema(
                query, context, force_tables=None
            )

        return narrowed_ctx, table_cols_map, intent
