from typing import List


def get_casting_rules(dialect: str = "snowflake") -> List[str]:
    """
    Return dialect-specific casting rules injected into the SQL generation prompt.

    The LLM reads these rules and reasons about the correct cast syntax for the
    target database — no hard-coded SQL examples are needed anywhere else.
    """
    d = (dialect or "snowflake").lower().strip()

    # ── SQLite ────────────────────────────────────────────────────────────────
    if d == "sqlite":
        return [
            "SQLite CAST syntax: CAST(expr AS TYPE). Never use ::TYPE shorthand.",
            "SQLite type affinity: INTEGER, REAL, TEXT, BLOB, NUMERIC. "
            "Map BOOLEAN → INTEGER (1/0), DATETIME → TEXT (ISO-8601 strings).",
            "String → number: CAST(col AS REAL), CAST(col AS INTEGER). "
            "NULL-safe: CAST(col AS INTEGER) returns NULL when col is non-numeric text.",
        ]

    # ── DuckDB ────────────────────────────────────────────────────────────────
    if d == "duckdb":
        return [
            "DuckDB supports both CAST(expr AS TYPE) and col::TYPE shorthand — prefer ::TYPE for brevity.",
            "DuckDB types: INTEGER, BIGINT, DOUBLE, VARCHAR, BOOLEAN, DATE, TIMESTAMP, INTERVAL, JSON.",
            "TRY_CAST(expr AS TYPE) returns NULL instead of raising on failure — use when input is untrusted.",
            "JSON extraction: col->'$.key' or json_extract_string(col, '$.key'). "
            "Unpack arrays with UNNEST().",
        ]

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    if d in ("postgresql", "postgres"):
        return [
            "PostgreSQL supports both CAST(expr AS TYPE) and expr::TYPE — prefer ::TYPE for readability.",
            "PostgreSQL types: INTEGER, BIGINT, NUMERIC, REAL, DOUBLE PRECISION, TEXT, VARCHAR, "
            "BOOLEAN, DATE, TIMESTAMP, TIMESTAMPTZ, INTERVAL, JSONB, UUID.",
            "Safe cast: use a CASE expression or suppress exceptions with a function; "
            "PostgreSQL has no TRY_CAST — wrap in a custom function or use NULLIF+CAST pattern.",
            "JSONB extraction: col->'key' (returns jsonb), col->>'key' (returns text). "
            "Cast jsonb to text before further string operations.",
        ]

    # ── MySQL / MariaDB ───────────────────────────────────────────────────────
    if d in ("mysql", "mariadb"):
        return [
            "MySQL CAST syntax: CAST(expr AS TYPE). Never use ::TYPE shorthand.",
            "MySQL CAST target types: CHAR, SIGNED, UNSIGNED, DECIMAL(p,s), FLOAT, DOUBLE, "
            "DATE, DATETIME, TIME, JSON, BINARY.",
            "Integer cast: CAST(col AS SIGNED) for signed, CAST(col AS UNSIGNED) for unsigned. "
            "Do NOT use CAST(col AS INTEGER) — MySQL rejects it.",
            "CONVERT(expr, TYPE) is an equivalent alternative but CAST is preferred for clarity.",
            "JSON path extraction: JSON_EXTRACT(col, '$.key') or the shorthand col->>'$.key' (MariaDB 10.3+).",
        ]

    # ── MS SQL Server ─────────────────────────────────────────────────────────
    if d in ("mssql", "sqlserver"):
        return [
            "SQL Server casting: prefer CAST(expr AS TYPE); CONVERT(TYPE, expr [, style]) is also valid "
            "and required when a format style is needed (e.g. dates).",
            "SQL Server types: INT, BIGINT, DECIMAL(p,s), FLOAT, REAL, NVARCHAR(n), VARCHAR(n), "
            "BIT, DATE, DATETIME, DATETIME2, DATETIMEOFFSET, UNIQUEIDENTIFIER.",
            "Safe cast: TRY_CAST(expr AS TYPE) and TRY_CONVERT(TYPE, expr) return NULL on failure — "
            "always prefer these over CAST when the input may be invalid.",
            "JSON: SQL Server 2016+. Use JSON_VALUE(col, '$.key') for scalars, "
            "JSON_QUERY(col, '$.array') for objects/arrays.",
        ]

    # ── BigQuery ──────────────────────────────────────────────────────────────
    if d == "bigquery":
        return [
            "BigQuery CAST syntax: CAST(expr AS TYPE). No ::TYPE shorthand.",
            "BigQuery types: INT64, FLOAT64, NUMERIC, BIGNUMERIC, BOOL, STRING, BYTES, "
            "DATE, TIME, DATETIME, TIMESTAMP, ARRAY<T>, STRUCT<field TYPE, ...>, JSON.",
            "Safe cast: SAFE_CAST(expr AS TYPE) returns NULL instead of raising — always prefer "
            "SAFE_CAST when the input may not conform to the target type.",
            "JSON access: JSON_VALUE(col, '$.key') for STRING scalars; "
            "JSON_QUERY(col, '$.path') for nested JSON; INT64(JSON_VALUE(...)) to cast JSON values.",
            "Array unnesting: UNNEST(array_col) in FROM clause or CROSS JOIN UNNEST.",
        ]

    # ── Oracle ────────────────────────────────────────────────────────────────
    if d == "oracle":
        return [
            "Oracle casting: CAST(expr AS TYPE) for standard casts. No ::TYPE shorthand.",
            "Oracle conversion functions: TO_NUMBER(col, format), TO_CHAR(col, format), "
            "TO_DATE(col, format), TO_TIMESTAMP(col, format) — use these when format masks are needed.",
            "Oracle types: NUMBER(p,s), VARCHAR2(n), NVARCHAR2(n), CHAR(n), DATE, TIMESTAMP, "
            "CLOB, BLOB, RAW, INTERVAL.",
            "Null-safe conversion: NVL(col, default) to substitute NULLs before casting.",
        ]

    # ── Trino / Presto ────────────────────────────────────────────────────────
    if d in ("trino", "presto"):
        return [
            "Trino CAST syntax: CAST(expr AS TYPE). Also supports TRY_CAST(expr AS TYPE) → NULL on failure.",
            "Trino types: INTEGER, BIGINT, DOUBLE, REAL, DECIMAL(p,s), VARCHAR, BOOLEAN, "
            "DATE, TIME, TIMESTAMP, ARRAY(T), MAP(K,V), ROW(field TYPE, ...).",
            "JSON: json_extract_scalar(col, '$.key') for STRING values; "
            "json_extract(col, '$.key') for JSON nodes.",
        ]

    # ── Redshift ──────────────────────────────────────────────────────────────
    if d == "redshift":
        return [
            "Redshift supports both CAST(expr AS TYPE) and expr::TYPE (PostgreSQL-style).",
            "Redshift types: INTEGER, BIGINT, DECIMAL(p,s), REAL, DOUBLE PRECISION, "
            "VARCHAR(n), CHAR(n), BOOLEAN, DATE, TIMESTAMP, TIMESTAMPTZ, SUPER.",
            "SUPER type (JSON-like): use json_parse() to cast text to SUPER; "
            "access nested fields with dot notation: col.key.",
        ]

    # ── Spark SQL / Databricks ────────────────────────────────────────────────
    if d in ("spark", "databricks", "hive"):
        return [
            "Spark SQL CAST syntax: CAST(expr AS TYPE). No ::TYPE shorthand.",
            "Spark types: INT, BIGINT, FLOAT, DOUBLE, DECIMAL(p,s), STRING, BOOLEAN, "
            "DATE, TIMESTAMP, ARRAY<T>, MAP<K,V>, STRUCT<field:TYPE>.",
            "TRY_CAST(expr AS TYPE) returns NULL on failure — prefer for untrusted data.",
            "Nested access: col.field for structs, col[index] for arrays, col[key] for maps.",
        ]

    # ── Snowflake (default) ───────────────────────────────────────────────────
    return [
        "Snowflake: normalize all casts to ::TYPE shorthand (col::INTEGER, col::FLOAT, col::STRING). "
        "Type aliases: VARCHAR/TEXT → STRING, INT/BIGINT → INTEGER, DOUBLE/DECIMAL → FLOAT, "
        "DATETIME → TIMESTAMP_NTZ. Never use ::VARCHAR.",
        "TRY_CAST(col AS TYPE) returns NULL on failure — use for columns that may contain "
        "unconvertible values.",
        "VARIANT/JSON extraction: col:key::STRING, col:key::INTEGER. "
        "PARSE_JSON(string_col) converts a JSON string to VARIANT.",
    ]
