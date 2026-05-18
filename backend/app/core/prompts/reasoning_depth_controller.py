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
        "2. Verify data types and apply explicit double-colon casts (::TYPE).",
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
        domain: str = "General Enterprise"
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

        logger.info(f"[ReasoningDepthController] Selected reasoning depth mode: '{mode}' ({len(directives)} directives).")
        return directives
