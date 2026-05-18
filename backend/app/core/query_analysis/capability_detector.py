import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.models.schemas import SemanticContext
from backend.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from backend.app.utils.logger import logger

class QueryCapabilityProfile(BaseModel):
    requires_variants: bool = False
    requires_windows: bool = False
    requires_ctes: bool = True      # Default best practice in Snowflake
    requires_arrays: bool = False
    requires_regex: bool = False
    requires_geospatial: bool = False
    requires_timestamps: bool = False
    requires_aggregation: bool = False
    requires_joins: bool = False
    requires_flatten: bool = False
    requires_ranking: bool = False
    requires_casting: bool = True   # Standard practice

class QueryCapabilityDetector:
    """
    Enterprise Query Capability Detector.
    Analyzes query text, intent analysis, and schema context to extract an 11-flag
    capability profile that drives adaptive rule retrieval and prompt compilation.
    """

    @staticmethod
    def detect(
        query: str,
        intent: Optional[QueryIntentAnalysis] = None,
        context: Optional[SemanticContext] = None
    ) -> QueryCapabilityProfile:
        q_lower = query.lower()

        # Check intent flags if available
        var_flag = intent.requires_variant_expansion if intent else False
        geo_flag = intent.requires_geospatial if intent else False
        tmp_flag = intent.requires_temporal if intent else False

        # 1. Variants / JSON / Arrays / Flatten
        requires_variants = var_flag or any(kw in q_lower for kw in ("json", "variant", "parse_json", "object", "key", "payload", "genotype", ":"))
        requires_arrays = var_flag or any(kw in q_lower for kw in ("array", "[]", "element", "index", "membership", "contains", "genotype"))
        requires_flatten = var_flag or any(kw in q_lower for kw in ("flatten", "lateral", "expand", "explode", "unnest", "genotype"))

        # 2. Windows / Ranking
        win_kws = ("window", "over", "partition by", "row_number", "rank", "dense_rank", "lead", "lag", "running total", "cumulative", "qualify")
        requires_windows = any(kw in q_lower for kw in win_kws) or (intent and any("rank" in m.lower() or "over" in m.lower() for m in intent.target_metrics))
        requires_ranking = any(kw in q_lower for kw in ("rank", "top", "bottom", "highest", "lowest", "leading", "row_number", "dense_rank", "nth"))

        # 3. Regex
        requires_regex = any(kw in q_lower for kw in ("regex", "regexp", "pattern", "matches", "like", "ilike", "starts with", "ends with"))

        # 4. Geospatial
        requires_geospatial = geo_flag or any(kw in q_lower for kw in ("distance", "within", "area", "polygon", "intersects", "st_", "spatial", "latitude", "longitude", "geography"))

        # 5. Timestamps / Temporal
        tmp_kws = ("date", "time", "month", "year", "day", "hour", "quarter", "week", "before", "after", "between", "timestamp", "datediff", "dateadd", "trunc")
        requires_timestamps = tmp_flag or any(kw in q_lower for kw in tmp_kws)

        # 6. Aggregation
        agg_kws = ("count", "sum", "avg", "average", "max", "min", "total", "percentage", "ratio", "proportion", "group by", "having")
        requires_aggregation = any(kw in q_lower for kw in agg_kws) or (intent and bool(intent.target_metrics))

        # 7. Joins
        requires_joins = any(kw in q_lower for kw in ("join", "inner", "left", "outer", "combine", "across"))
        if context and context.tables and len(context.tables) > 1:
            requires_joins = True

        profile = QueryCapabilityProfile(
            requires_variants=requires_variants,
            requires_windows=requires_windows or requires_ranking,
            requires_ctes=True,
            requires_arrays=requires_arrays,
            requires_regex=requires_regex,
            requires_geospatial=requires_geospatial,
            requires_timestamps=requires_timestamps,
            requires_aggregation=requires_aggregation,
            requires_joins=requires_joins,
            requires_flatten=requires_flatten,
            requires_ranking=requires_ranking,
            requires_casting=True
        )

        logger.debug(f"[CapabilityDetector] Detected capabilities: {profile.model_dump()}")
        return profile
