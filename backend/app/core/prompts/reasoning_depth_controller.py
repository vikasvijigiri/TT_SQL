from typing import List
from backend.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from backend.app.utils.logger import logger

class ReasoningDepthController:
    """
    Enterprise Dynamic Reasoning Depth Controller.
    Selects reasoning depth modes (minimal, balanced, deep_reasoning) based on query complexity.
    """

    DIRECTIVES_MINIMAL = [
        "1. Identify exact required columns from SCHEMA verbatim.",
        "2. Formulate concise single-pass SQL respecting filters."
    ]

    DIRECTIVES_BALANCED = [
        "1. Deconstruct query intent into discrete logical steps.",
        "2. Verify data types and apply dialect-safe casts.",
        "3. Ensure exact identifier quoting matching SCHEMA casing.",
        "4. Validate aggregation grain and ensure non-aggregated columns appear in GROUP BY."
    ]

    DIRECTIVES_DEEP = [
        "1. Multi-Step Execution Plan: Map each logical transformation to a named CTE.",
        "2. Variant & Array Unnesting: Apply LATERAL FLATTEN in FROM clause for array fields.",
        "3. Null & Missing Key Safeguards: Check join predicates and variant keys for silent NULL propagation.",
        "4. Granular Aggregation & Windowing: Ensure window function partitions exactly match target metrics.",
        "5. Final Projection Audit: Verify column names, data types, and ordering exactness."
    ]

    @classmethod
    def get_directives(
        cls,
        query: str,
        profile: QueryCapabilityProfile,
        domain: str = "General Enterprise",
        dialect: str = "snowflake"
    ) -> List[str]:
        # Determine mode
        if profile.requires_variants or (profile.requires_windows and profile.requires_joins) or len(query.split()) > 25:
            mode = "deep_reasoning"
            directives = cls.DIRECTIVES_DEEP
        elif not profile.requires_joins and not profile.requires_aggregation and not profile.requires_windows and not profile.requires_variants:
            mode = "minimal"
            directives = cls.DIRECTIVES_MINIMAL
        else:
            mode = "balanced"
            directives = cls.DIRECTIVES_BALANCED

        d = dialect.lower()
        if d == "sqlite" and (profile.requires_windows or profile.requires_timestamps or profile.requires_aggregation):
            directives = directives + [
                "5. For SQLite time-series queries, compute aggregates before recursion and use WITH RECURSIVE only once at the top.",
                "6. Use CAST(expr AS INTEGER/REAL/TEXT) syntax in SQLite; never use PostgreSQL-style ::TYPE casts.",
                "7. Validate recursive CTE base rows first, then advance row-by-row with a stable ordering column.",
            ]
        elif d in ("duckdb",):
            directives = directives + [
                "5. DuckDB supports STRUCT, LIST, and MAP types — use list_contains() / list_filter() for array predicates.",
                "6. Prefer epoch_ms() / strftime() for timestamp arithmetic; avoid EXTRACT(EPOCH) which is PostgreSQL syntax.",
                "7. Use COLUMNS(*) glob expansion only when all projected columns share the same type.",
            ]
        elif d in ("postgres", "postgresql", "redshift"):
            directives = directives + [
                "5. Use ::TYPE double-colon casts consistently; avoid CAST() in window function OVER clauses.",
                "6. For date arithmetic use INTERVAL '1 day' syntax; avoid DATE_ADD() which is MySQL-only.",
                "7. Use FILTER (WHERE ...) on aggregate functions instead of CASE WHEN inside SUM/COUNT.",
            ]
        elif d in ("mysql",):
            directives = directives + [
                "5. MySQL GROUP BY must include all non-aggregated SELECT columns (ONLY_FULL_GROUP_BY mode).",
                "6. Use CAST(expr AS CHAR) for string coercion; ::TYPE and TO_CHAR() are not valid in MySQL.",
                "7. Use LIMIT n OFFSET m for pagination; FETCH FIRST / ROWS ONLY is not supported.",
            ]

        logger.info(f"[ReasoningDepthController] Selected reasoning depth mode: '{mode}' ({len(directives)} directives).")
        return directives
