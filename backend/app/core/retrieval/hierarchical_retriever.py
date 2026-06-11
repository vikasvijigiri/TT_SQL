import re
from typing import List, Dict, Tuple
from pydantic import BaseModel
from backend.app.models.schemas import SemanticContext, SemanticTable
from backend.app.core.pipeline_config import PipelineModeConfig, BALANCED_CONFIG
from backend.app.core.retrieval.schema_retriever import SchemaRetriever
from backend.app.core.schema.semantic_tags import SemanticTagger
from backend.app.utils.logger import logger


class QueryIntentAnalysis(BaseModel):
    inferred_domain: str
    target_entities: List[str]
    target_metrics: List[str]
    filter_conditions: List[str]
    estimated_join_paths: List[str]
    requires_variant_expansion: bool
    requires_geospatial: bool
    requires_temporal: bool


class HierarchicalRetriever:
    """
    Hierarchical multi-stage schema narrowing engine. Performs intent analysis,
    selects top candidate tables, and narrows columns per table.
    """

    def __init__(self, config: PipelineModeConfig = BALANCED_CONFIG):
        self.config = config
        self.retriever = SchemaRetriever(config)
        self.tagger = SemanticTagger()

    def analyze_intent(self, query: str) -> QueryIntentAnalysis:
        q_lower = query.lower()

        # Domain classification
        if any(
            w in q_lower
            for w in (
                "gene",
                "variant",
                "chromosome",
                "allele",
                "genotype",
                "mutation",
                "cnv",
                "cytoband",
            )
        ):
            domain = "Genomics & Healthcare"
        elif any(
            w in q_lower
            for w in (
                "revenue",
                "profit",
                "sales",
                "customer",
                "invoice",
                "payment",
                "tax",
            )
        ):
            domain = "E-commerce & Financial"
        elif any(
            w in q_lower
            for w in (
                "latitude",
                "longitude",
                "distance",
                "area",
                "polygon",
                "within",
                "intersects",
            )
        ):
            domain = "Geospatial"
        else:
            domain = "General Enterprise"

        # Flags
        has_var = any(
            w in q_lower
            for w in (
                "json",
                "key",
                "array",
                "nested",
                "flatten",
                "object",
                "genotype",
                "payload",
                "parse_json",
                "variant",
            )
        )
        has_geo = any(
            w in q_lower
            for w in (
                "distance",
                "area",
                "within",
                "latitude",
                "longitude",
                "spatial",
                "polygon",
                "st_",
                "geography",
                "geometry",
            )
        )
        has_tmp = any(
            w in q_lower
            for w in (
                "date",
                "month",
                "year",
                "day",
                "before",
                "after",
                "time",
                "quarter",
                "when",
                "timestamp",
                "datediff",
            )
        )

        # Extract entities / terms
        clean_words = re.sub(r"[^a-zA-Z0-9]", " ", q_lower).split()
        entities = [
            w
            for w in clean_words
            if len(w) > 3
            and w
            not in (
                "select",
                "where",
                "from",
                "find",
                "show",
                "count",
                "average",
                "total",
                "what",
                "which",
                "how",
                "many",
            )
        ]

        metrics = [
            w
            for w in clean_words
            if w
            in (
                "count",
                "sum",
                "average",
                "avg",
                "max",
                "min",
                "total",
                "percentage",
                "ratio",
                "proportion",
            )
        ]

        return QueryIntentAnalysis(
            inferred_domain=domain,
            target_entities=list(set(entities[:10])),
            target_metrics=list(set(metrics[:5])),
            filter_conditions=[q_lower[:100]],
            estimated_join_paths=[],
            requires_variant_expansion=has_var,
            requires_geospatial=has_geo,
            requires_temporal=has_tmp,
        )

    def narrow_schema(
        self, query: str, context: SemanticContext, force_tables: List[str] | None = None
    ) -> Tuple[SemanticContext, Dict[str, List[str]], QueryIntentAnalysis]:
        logger.debug(
            f"[HierarchicalRetriever] Analyzing intent and narrowing schema for query: '{query[:60]}...'"
        )
        intent = self.analyze_intent(query)

        # Enrich context with ontology tags
        if context and context.tables:
            for t in context.tables:
                self.tagger.enrich_table(t)

        # 1. Table narrowing
        if force_tables and context and context.tables:
            tbl_map = {t.name.lower(): t for t in context.tables}
            tbl_base_map = {t.name.lower().split(".")[-1]: t for t in context.tables}
            narrowed_tables = []
            for ft in force_tables:
                ft_clean = ft.lower().replace('"', "")
                if ft_clean in tbl_map:
                    narrowed_tables.append(tbl_map[ft_clean])
                elif ft_clean.split(".")[-1] in tbl_base_map:
                    narrowed_tables.append(tbl_base_map[ft_clean.split(".")[-1]])
        else:
            narrowed_tables = self.retriever.retrieve_tables(
                query, context, top_k=self.config.max_tables_per_query
            )

        # Ensure we have at least 1 table
        if not narrowed_tables and context and context.tables:
            narrowed_tables = context.tables[: min(5, len(context.tables))]

        # 2. Column narrowing
        table_cols_map: Dict[str, List[str]] = {}
        final_tables: List[SemanticTable] = []

        for t in narrowed_tables:
            narrowed_cols = self.retriever.retrieve_columns(
                query, t, top_k=self.config.max_columns_per_table
            )
            if not narrowed_cols and t.columns:
                narrowed_cols = t.columns[: min(10, len(t.columns))]

            table_cols_map[t.name] = [c.name for c in narrowed_cols]

            # create narrowed table object
            new_t = SemanticTable(
                name=t.name,
                description=t.description,
                columns=narrowed_cols,
                foreign_keys=t.foreign_keys,
                sample_rows=t.sample_rows
                if self.config.include_raw_sample_rows
                else [],
            )
            final_tables.append(new_t)

        narrowed_ctx = SemanticContext(tables=final_tables)
        logger.info(
            f"[HierarchicalRetriever] Narrowed schema to {len(final_tables)} tables."
        )
        return narrowed_ctx, table_cols_map, intent
