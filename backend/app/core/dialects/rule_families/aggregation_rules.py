from typing import List

def get_aggregation_rules() -> List[str]:
    return [
        "Every non-aggregated SELECT column MUST appear in GROUP BY. Never use positional GROUP BY references.",
        "WHERE filters before aggregation. HAVING filters after. Never filter on aggregate results in WHERE. Never use HAVING for non-aggregated column filters.",
        "COUNT(col) excludes NULLs. COUNT(*) includes all. SUM returns NULL if all values NULL — use COALESCE(SUM(col), 0).",
        "COUNT(DISTINCT col) is exact. Use APPROX_COUNT_DISTINCT only when query explicitly requires approximate counting.",
        "Prevent division-by-zero: numerator / NULLIF(denominator, 0). Use NULLIF over CASE WHEN for conciseness."
    ]
