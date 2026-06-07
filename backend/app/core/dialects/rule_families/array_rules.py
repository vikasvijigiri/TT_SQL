from typing import List

def get_array_rules() -> List[str]:
    return [
        "Access array elements with zero-based bracket notation and explicit cast: \"col\"[0]::TYPE. If the index is not deterministic, use LATERAL FLATTEN.",
        "Render array expansion as LATERAL FLATTEN in FROM: FROM \"TABLE\", LATERAL FLATTEN(input => \"TABLE\".\"col\") AS f. Reference via f.VALUE::TYPE, f.VALUE:\"key\"::TYPE, f.INDEX, f.PATH. Never use FLATTEN without LATERAL. Always place LATERAL FLATTEN directly in the main FROM clause.",
        "Test array membership with ARRAY_CONTAINS. First argument MUST be ::VARIANT cast: ARRAY_CONTAINS('v'::VARIANT, \"col\"). Never use IN, =, or LIKE against ARRAY or VARIANT columns.",
        "Aggregate to array: ARRAY_AGG(\"col\"). Ordered: ARRAY_AGG(\"col\") WITHIN GROUP (ORDER BY \"col\"). Exclude nulls: ARRAY_AGG(\"col\") IGNORE NULLS.",
        "When classifying integer-pair arrays from LATERAL FLATTEN, handle nullable second elements for haploid or sparse representations: use COALESCE(element1, 0) and check IS NULL before comparing elements.",
    ]
