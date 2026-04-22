"""
Shared Utilities for Text-to-SQL Pipeline
Contains formatting and transformation logic used across multiple agents.
"""

from typing import Any


def format_schema_to_str(schema_info: dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a detailed multi-line or compact string."""
    if not schema_info:
        return ""
    lines = []
    for table, data in schema_info.items():
        # Handle potential dictionary structure
        if isinstance(data, dict) and "columns" in data:
            cols = data["columns"]
        elif isinstance(data, list):
            cols = data
        else:
            cols = []

        if detailed:
            lines.append(f"Table: {table}")
            if not cols:
                lines.append(" - (No columns found)")
            for c in cols:
                if isinstance(c, dict):
                    cname = c.get("column_name") or c.get("name") or "unknown"
                    ctype = c.get("type") or c.get("data_type") or ""
                    desc = c.get("description") or ""
                    lines.append(
                        f" - {cname} {f'({ctype})' if ctype else ''}{f' -- {desc}' if desc else ''}"
                    )
                else:
                    lines.append(f" - {str(c)}")
            lines.append("")  # Blank line
        else:
            col_names = []
            for i, c in enumerate(cols):
                if isinstance(c, dict):
                    col_names.append(
                        str(c.get("column_name") or c.get("name") or "unknown")
                    )
                else:
                    col_names.append(str(c))
            lines.append(f"{table}({', '.join(col_names)})")
    return "\n".join(lines).strip()


def format_rag_columns(rag_columns: list[dict[str, Any]]) -> str:
    """Formats the raw RAG retrieved columns list into a compact, prompt-ready string."""
    if not rag_columns:
        return "No RAG columns retrieved."
    # Group by table
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        cname = col.get("column_name", "unknown")
        if tname not in tables:
            tables[tname] = []
        tables[tname].append(cname)

    lines = []
    for tname, cols in tables.items():
        lines.append(f"Table: {tname}")
        lines.append(f"- Columns: {', '.join(cols)}")
        lines.append("")

    return "\n".join(lines).strip()


def format_execution_results(result: Any) -> str:
    """Formats ExecutionResult into a readable table for the critic."""
    if not result:
        return "No execution results available."

    # Check for error in ExecutionResult object
    if hasattr(result, "error_message") and result.error_message:
        return f"Execution Error: {result.error_message}"

    # Handle rows/columns
    rows = getattr(result, "rows", [])
    cols = getattr(result, "columns", [])

    if not rows:
        return "Query executed successfully but returned 0 rows."

    # Sample for display (first 5 rows)
    sample = rows[:5]

    if cols:
        header = " | ".join(cols)
        row_strs = [" | ".join(str(v) for v in row) for row in sample]
        return f"{header}\n" + "-" * len(header) + "\n" + "\n".join(row_strs)
    else:
        return "\n".join([" | ".join(str(v) for v in row) for row in sample])
