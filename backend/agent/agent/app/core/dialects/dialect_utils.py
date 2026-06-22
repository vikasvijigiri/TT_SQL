"""
dialect_utils.py
----------------
Database-agnostic dialect helpers.

All dialect-specific constants live here so the rest of the pipeline
never hardcodes vendor names.  New dialects are added to the maps below
without touching any other file.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Identifier quote character per dialect.
# MSSQL uses bracket quoting ([col]); callers that need the closing bracket
# should call get_close_quote() separately.
# ---------------------------------------------------------------------------
_QUOTE_CHAR: dict[str, str] = {
    # ANSI / neutral
    "ansi": '"',
    "unknown": '"',
    # Open-source / file-based
    "sqlite": '"',
    "duckdb": '"',
    # Cloud / server
    "postgres": '"',
    "postgresql": '"',
    "redshift": '"',
    "snowflake": '"',
    "bigquery": "`",
    "trino": '"',
    "presto": '"',
    # On-prem / enterprise
    "mysql": "`",
    "mariadb": "`",
    "mssql": "[",
    "sqlserver": "[",
    "oracle": '"',
    "saphana": '"',
    "ibmdb2": '"',
    # Analytics / big-data
    "hive": "`",
    "spark": "`",
    "databricks": "`",
    "clickhouse": "`",
    # Document
    "mongo": '"',
    "mongodb": '"',
}

_CLOSE_QUOTE_CHAR: dict[str, str] = {
    "mssql": "]",
    "sqlserver": "]",
}


def get_quote_char(dialect: Optional[str]) -> str:
    """Return the opening identifier-quote character for *dialect*.

    Falls back to double-quote (ANSI standard) for unrecognised dialects
    so the pipeline never crashes on a new or misspelled dialect name.
    """
    return _QUOTE_CHAR.get((dialect or "ansi").lower().strip(), '"')


def get_close_quote_char(dialect: Optional[str]) -> str:
    """Return the closing identifier-quote character for *dialect*.

    For most dialects this equals the opening quote; MSSQL is the exception.
    """
    key = (dialect or "ansi").lower().strip()
    return _CLOSE_QUOTE_CHAR.get(key, get_quote_char(dialect))


def quote_identifier(name: str, dialect: Optional[str]) -> str:
    """Wrap *name* in the correct identifier quotes for *dialect*."""
    open_q = get_quote_char(dialect)
    close_q = get_close_quote_char(dialect)
    return f"{open_q}{name}{close_q}"


def get_schema_introspection_sql(dialect: Optional[str], table_name: str, schema_name: Optional[str] = None) -> str:
    """Return a dialect-appropriate SQL string to list columns for *table_name*.

    This is the single source of truth for dialect-specific introspection SQL.
    Add new dialects here; the rest of the pipeline calls this function.
    """
    d = (dialect or "ansi").lower().strip()
    q = get_quote_char(d)
    cq = get_close_quote_char(d)

    if d in ("sqlite", "duckdb"):
        if d == "duckdb" and schema_name and "." in table_name:
            return f"SELECT 0 AS cid, column_name AS name FROM (DESCRIBE {table_name})"
        return f"PRAGMA table_info({q}{table_name}{cq})"

    if d in ("postgres", "postgresql", "redshift"):
        schema_filter = f"AND table_schema = '{schema_name}'" if schema_name else ""
        return (
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table_name}' {schema_filter} ORDER BY ordinal_position"
        )

    if d in ("mysql", "mariadb"):
        schema_filter = f"AND table_schema = '{schema_name}'" if schema_name else ""
        return (
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table_name}' {schema_filter} ORDER BY ordinal_position"
        )

    if d in ("mssql", "sqlserver"):
        schema_clause = f"AND TABLE_SCHEMA = '{schema_name}'" if schema_name else ""
        return (
            f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_NAME = '{table_name}' {schema_clause} ORDER BY ORDINAL_POSITION"
        )

    if d == "oracle":
        return f"SELECT column_name FROM all_tab_columns WHERE table_name = UPPER('{table_name}') ORDER BY column_id"

    if d == "snowflake":
        return (
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = UPPER('{table_name}') ORDER BY ordinal_position"
        )

    if d == "bigquery":
        return (
            f"SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = '{table_name}' ORDER BY ordinal_position"
        )

    if d in ("hive", "spark", "databricks"):
        return f"DESCRIBE {q}{table_name}{cq}"

    if d in ("trino", "presto"):
        return f"DESCRIBE {q}{table_name}{cq}"

    if d == "clickhouse":
        return f"DESCRIBE TABLE {q}{table_name}{cq}"

    # ANSI / unknown — best-effort information_schema query
    return (
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name = '{table_name}' ORDER BY ordinal_position"
    )
