from typing import List


def get_window_rules() -> List[str]:
    return [
        "Every window function requires explicit OVER(). Always specify PARTITION BY and/or ORDER BY as required by intent.",
        "Specify frame for row-range functions: Running total: ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW. Omit frame only for ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG, LEAD.",
        "ROW_NUMBER: unique, no ties. RANK: ties with gaps. DENSE_RANK: ties without gaps. Use ROW_NUMBER for deduplication.",
        "LAG/LEAD require ORDER BY inside OVER. Always specify offset and default value. LAG/LEAD without ORDER BY is non-deterministic.",
        "Use QUALIFY to filter window results without a subquery wrapper: QUALIFY ROW_NUMBER() OVER(...) = 1",
    ]
