"""
sqlglot-based SQL AST pre-validator.

Validates SQL syntax and extracts all table/column references BEFORE the
query is sent to the database.  This has two concrete pipeline benefits:

1. **Saves a DB round-trip on every syntax error.**  Instead of executing
   broken SQL (which returns a generic database error like "syntax error
   near 'GROUP'"), we catch it here and hand the corrector a precise,
   actionable message such as "Syntax error at column 42: Expected ')' but
   found 'GROUP'".

2. **Better corrector guidance.**  sqlglot identifies the exact token and
   position of the error.  The corrector can fix it in one pass instead of
   iterating blindly.

Dialect mapping
---------------
Internal dialect strings (sqlite, postgresql, snowflake, ...) are mapped to
sqlglot dialect identifiers before parsing so dialect-specific syntax (e.g.
Snowflake QUALIFY, BigQuery STRUCT) is accepted correctly.

Failure handling
----------------
sqlglot may reject valid SQL for dialects it knows less well, or for highly
unusual syntax.  All parse failures are caught and returned as
``valid=False`` with an ``errors`` list - the caller decides whether to
treat this as a hard block or a warning.  The pipeline uses it as a
soft block: if sqlglot rejects the SQL AND there is no existing
``error_context`` from an earlier check, the syntax error is surfaced to
the corrector.

Usage::

    from core.validators.sql_validator import validate

    result = validate("SELECT * FORM team", dialect="sqlite")
    # result.valid == False
    # result.errors == ["Syntax error at col 10: ..."]
    # result.error_summary == "Syntax error at col 10: ..."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import sqlglot
import sqlglot.errors
import sqlglot.expressions as exp


# -- Dialect mapping -----------------------------------------------------------

_DIALECT_MAP: dict[str, str] = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "postgres": "postgres",
    "mysql": "mysql",
    "mariadb": "mysql",
    "sqlserver": "tsql",
    "mssql": "tsql",
    "tsql": "tsql",
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "redshift": "redshift",
    "duckdb": "duckdb",
    "databricks": "databricks",
    "clickhouse": "clickhouse",
    "spark": "spark",
    "hive": "hive",
    "presto": "presto",
    "trino": "trino",
}


def _to_sqlglot_dialect(dialect: str) -> str:
    return _DIALECT_MAP.get((dialect or "sqlite").lower().strip(), "sqlite")


# -- Result dataclass ----------------------------------------------------------

@dataclass(frozen=True)
class SQLValidationResult:
    """
    Immutable result from a single AST validation pass.

    Attributes
    ----------
    valid:
        True when sqlglot parsed the SQL without errors.
    dialect:
        The sqlglot dialect string used for parsing.
    tables_referenced:
        Sorted list of table names found in the parse tree.
        Useful for cross-checking against allowed schema tables.
    columns_referenced:
        Sorted list of non-wildcard column names found in the parse tree.
    errors:
        List of error descriptions; empty when ``valid=True``.
    """

    valid: bool
    dialect: str
    tables_referenced: list[str] = field(default_factory=list)
    columns_referenced: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def error_summary(self) -> Optional[str]:
        """Single-string concatenation of all errors, or None if valid."""
        return "; ".join(self.errors) if self.errors else None


# -- Validator ----------------------------------------------------------------

def validate(sql: str, dialect: str = "sqlite") -> SQLValidationResult:
    """
    Parse *sql* with sqlglot and return a ``SQLValidationResult``.

    Parameters
    ----------
    sql:
        Raw SQL string to validate.
    dialect:
        Internal dialect name (sqlite, postgresql, snowflake, ...).
        Mapped to the nearest sqlglot dialect automatically.

    Returns
    -------
    SQLValidationResult
        ``valid=True`` when the SQL parsed cleanly; ``valid=False`` with
        ``errors`` populated otherwise.

    Notes
    -----
    - All exceptions are caught; this function never raises.
    - Parse tree extraction (tables, columns) runs only on valid SQL.
    """
    if not sql or not sql.strip():
        return SQLValidationResult(
            valid=False,
            dialect=dialect,
            errors=["SQL is empty or whitespace-only"],
        )

    sg_dialect = _to_sqlglot_dialect(dialect)
    errors: list[str] = []
    tables: set[str] = set()
    columns: set[str] = set()

    try:
        expression = sqlglot.parse_one(
            sql,
            dialect=sg_dialect,
            error_level=sqlglot.errors.ErrorLevel.RAISE,
        )
    except sqlglot.errors.ParseError as exc:
        for err in exc.errors:
            col = err.get("col", "?")
            line = err.get("line", "?")
            desc = err.get("description") or str(exc)
            errors.append(f"Syntax error at line {line} col {col}: {desc}")
        return SQLValidationResult(
            valid=False,
            dialect=sg_dialect,
            errors=errors,
        )
    except Exception as exc:
        # Defensive: if sqlglot itself crashes (edge-case), report but don't block
        return SQLValidationResult(
            valid=False,
            dialect=sg_dialect,
            errors=[f"AST parser internal error: {str(exc)[:300]}"],
        )

    # -- Extract schema references from the parse tree ---------------------
    # Collect CTE-defined aliases so we can exclude them from table checks
    cte_names: set[str] = set()
    for cte in expression.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    for table in expression.find_all(exp.Table):
        if table.name and table.name.lower() not in cte_names:
            tables.add(table.name.lower())

    # Only collect qualified column references (table.column) where the table is a physical table or alias
    # to avoid flagging CTE-defined aliases or subquery columns as hallucinated
    physical_table_aliases: set[str] = set()
    for table in expression.find_all(exp.Table):
        if table.name and table.name.lower() not in cte_names:
            physical_table_aliases.add(table.name.lower())
            if table.alias:
                physical_table_aliases.add(table.alias.lower())

    for col in expression.find_all(exp.Column):
        if col.name and col.name != "*" and col.table:
            if col.table.lower() in physical_table_aliases:
                columns.add(col.name.lower())

    return SQLValidationResult(
        valid=True,
        dialect=sg_dialect,
        tables_referenced=sorted(tables),
        columns_referenced=sorted(columns),
        errors=[],
    )


# -- Schema-aware identifier cross-check --------------------------------------

@dataclass(frozen=True)
class IdentifierCheckResult:
    """
    Result of cross-checking extracted SQL identifiers against a known schema.

    Attributes
    ----------
    hallucinated_tables:
        Tables present in the SQL but absent from the provided schema.
    hallucinated_columns:
        Columns present in the SQL but absent from any schema table's column
        list.  Only populated when *schema_columns* is provided.
    is_clean:
        True when no hallucinated identifiers were found.
    summary:
        Human-readable error string, or None if clean.
    """

    hallucinated_tables: List[str]
    hallucinated_columns: List[str]

    @property
    def is_clean(self) -> bool:
        return not self.hallucinated_tables and not self.hallucinated_columns

    @property
    def summary(self) -> Optional[str]:
        parts: List[str] = []
        if self.hallucinated_tables:
            parts.append(f"Unknown tables: {', '.join(self.hallucinated_tables)}")
        if self.hallucinated_columns:
            parts.append(f"Unknown columns: {', '.join(self.hallucinated_columns)}")
        return "; ".join(parts) if parts else None


def validate_against_schema(
    parse_result: SQLValidationResult,
    known_tables: Set[str],
    schema_columns: Optional[Dict[str, List[str]]] = None,
) -> IdentifierCheckResult:
    """
    Cross-check identifiers extracted by :func:`validate` against a known schema.

    Parameters
    ----------
    parse_result:
        The result of a previous :func:`validate` call.  If the SQL was
        invalid (``valid=False``), returns an empty clean result because
        there is nothing to cross-check.
    known_tables:
        Set of lowercase table names that exist in the target database schema.
    schema_columns:
        Optional mapping of ``table_name -> [column_name, ...]`` (all
        lowercase).  When provided, column names extracted from the SQL are
        checked against every table's column list.  A column is only flagged
        as hallucinated if it does not appear in *any* of the schema tables.

    Returns
    -------
    IdentifierCheckResult
        Never raises.
    """
    if not parse_result.valid:
        return IdentifierCheckResult(hallucinated_tables=[], hallucinated_columns=[])

    norm_known = {t.lower() for t in known_tables}

    # Check tables
    hallucinated_tables = [
        t for t in parse_result.tables_referenced
        if t.lower() not in norm_known
    ]

    # Check columns (optional)
    hallucinated_columns: List[str] = []
    if schema_columns:
        all_known_cols: Set[str] = set()
        for cols in schema_columns.values():
            all_known_cols.update(c.lower() for c in cols)
        hallucinated_columns = [
            c for c in parse_result.columns_referenced
            if c.lower() not in all_known_cols
        ]

    return IdentifierCheckResult(
        hallucinated_tables=hallucinated_tables,
        hallucinated_columns=hallucinated_columns,
    )
