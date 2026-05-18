from typing import List

def get_array_rules() -> List[str]:
    return [
        "Access array elements with zero-based bracket notation and explicit cast: \"col\"[0]::TYPE. If the index is not deterministic, use LATERAL FLATTEN.",
        "Render array expansion as LATERAL FLATTEN in FROM: FROM \"TABLE\", LATERAL FLATTEN(input => \"TABLE\".\"col\") AS f. Reference via f.VALUE::TYPE, f.VALUE:\"key\"::TYPE, f.INDEX, f.PATH. Never use FLATTEN without LATERAL. Always place LATERAL FLATTEN directly in the main FROM clause.",
        "Test array membership with ARRAY_CONTAINS. First argument MUST be ::VARIANT cast: ARRAY_CONTAINS('v'::VARIANT, \"col\"). Never use IN, =, or LIKE against ARRAY or VARIANT columns.",
        "Aggregate to array: ARRAY_AGG(\"col\"). Ordered: ARRAY_AGG(\"col\") WITHIN GROUP (ORDER BY \"col\"). Exclude nulls: ARRAY_AGG(\"col\") IGNORE NULLS.",
        "When classifying genotype arrays from LATERAL FLATTEN (e.g. g.VALUE:genotype), account for haploid chromosomes (such as males on Chr X where ARRAY_SIZE is 1 and index 1 is NULL). Classify homozygous reference as: (gt0 = 0 AND (gt1 = 0 OR gt1 IS NULL)). Classify homozygous alternate as: (gt0 = gt1 AND gt0 > 0). Classify heterozygous as: ((gt0 <> gt1 OR (gt0 > 0 AND gt1 IS NULL) OR (gt1 > 0 AND gt0 IS NULL)) AND (COALESCE(gt0, 0) > 0 OR COALESCE(gt1, 0) > 0))."
    ]
