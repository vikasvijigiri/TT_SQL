from typing import List


def get_identifier_rules() -> List[str]:
    return [
        # -- Universal quoting & naming -----------------------------------------
        "Double-quote every table and column identifier using the EXACT casing shown in the schema."
        " Unquoted identifiers are folded to uppercase by most engines and will fail silently.",
        "Every identifier MUST exist verbatim in the provided schema. Never abbreviate, pluralise,"
        " or assume a name that is not explicitly listed.",
        "Table function output columns (e.g. VALUE, INDEX, PATH, KEY, SEQ) are uppercase"
        " - do NOT quote them.",
        "Never reference a SELECT-level alias inside WHERE, HAVING, or GROUP BY.",
        "Prefer CTEs over deeply nested subqueries. Name each CTE in snake_case that reflects"
        " its logical purpose (e.g. filtered_orders, ranked_users).",

        # -- DuckDB: use exactly the alias shown in the schema -----------------
        # The executor runs SHOW ALL TABLES and injects the real db_alias into the schema context.
        # The LLM MUST use that alias verbatim - never invent or guess one.
        "DUCKDB ONLY - table qualification rule:"
        " When the schema shows a table in the form <db_alias>.<table_name>, you MUST write SQL"
        " as \"<db_alias>\".\"<table_name>\" (both parts double-quoted)."
        " The db_alias is determined at runtime by the executor from SHOW ALL TABLES;"
        " it appears at the start of every table entry in the schema you receive."
        " NEVER invent an alias, NEVER drop the alias, and NEVER append '_db', '_query_db',"
        " or any other suffix not present in the schema."
        " If you see a unified view like all_<basename> in the schema, prefer it for"
        " cross-entity queries - it already unions all homogeneous tables.",

        # -- DuckDB: error-hint self-correction --------------------------------
        # DuckDB error messages often say: 'Did you mean "correct_alias"."table"?'
        # The self-corrector MUST use that suggestion verbatim on the next attempt.
        "DUCKDB error recovery: if an execution error contains 'Did you mean"
        " \"<alias>\".\"<table>\"?', rewrite the SQL using exactly that alias and table name."
        " Do not guess; use the error message's own suggestion.",

        # -- SQLite / Snowflake: no prefix -------------------------------------
        "SQLITE / SNOWFLAKE: tables are in the default schema - do NOT prefix them with any"
        " logical database name from descriptions or comments."
        " Use table names exactly as shown in the schema, with no qualifier.",
    ]
