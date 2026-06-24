from typing import List


def get_window_rules(dialect: str = "snowflake") -> List[str]:
    d = (dialect or "snowflake").lower().strip()

    rules = [
        "Every window function requires explicit OVER(). Always specify PARTITION BY and/or ORDER BY as required by intent.",
        "Specify frame for row-range functions: Running total: ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW. Omit frame only for ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG, LEAD.",
        "ROW_NUMBER: unique, no ties. RANK: ties with gaps. DENSE_RANK: ties without gaps. Use ROW_NUMBER for deduplication.",
        "LAG/LEAD require ORDER BY inside OVER. Always specify offset and default value. LAG/LEAD without ORDER BY is non-deterministic.",
        # Generic architectural principle - applies to every dialect
        "Ranked aggregation requires two query levels: (1) compute all aggregates (GROUP BY, HAVING, "
        "computed metrics) fully in a CTE or subquery; (2) apply ROW_NUMBER/RANK/DENSE_RANK in the "
        "outer SELECT on top of that result. Never reference an aggregate expression (AVG, SUM, COUNT, "
        "MIN, MAX) directly inside OVER() in the same SELECT that also contains GROUP BY - the engine "
        "cannot resolve the aggregate at window-function parse time.",
    ]

    # QUALIFY is only supported in DuckDB, Snowflake, BigQuery, Databricks
    if d in ("duckdb", "snowflake", "bigquery", "databricks", "spark"):
        rules.append(
            "Use QUALIFY to filter window results without a subquery wrapper: "
            "QUALIFY ROW_NUMBER() OVER(...) = 1"
        )
    else:
        # SQLite, PostgreSQL, MySQL, MSSQL, Trino, Redshift, Oracle - no QUALIFY
        rules.append(
            "QUALIFY is not supported in this dialect. To filter on a window result, wrap the "
            "window query in a subquery or CTE and filter on the rank column in the outer query: "
            "SELECT * FROM (SELECT ..., ROW_NUMBER() OVER(...) AS rn FROM ...) sub WHERE rn = 1"
        )

    return rules
