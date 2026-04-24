"""
Shared Utilities for Text-to-SQL Pipeline
Contains formatting and transformation logic used across multiple agents.
"""

import json
from typing import Any


def format_schema_to_str(schema_info: dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a detailed multi-line string with IN-LINE column samples."""
    if not schema_info:
        return ""
    lines = []
    for table, data in schema_info.items():
        # 1. Resolve columns
        if isinstance(data, dict) and "columns" in data:
            cols = data["columns"]
        elif isinstance(data, list):
            cols = data
        else:
            cols = []

        # 2. Extract column-wise samples from table sample
        col_samples = {}
        if isinstance(data, dict) and data.get("sample"):
            try:
                # Assuming sample is a JSON string or list of dicts
                raw_sample = data["sample"]
                sample_data = json.loads(raw_sample) if isinstance(raw_sample, str) else raw_sample
                
                if isinstance(sample_data, list) and len(sample_data) > 0:
                    for row in sample_data:
                        for cname, cval in row.items():
                            # Store in normalized uppercase to ensure matching
                            norm_name = str(cname).strip().upper()
                            if norm_name not in col_samples:
                                col_samples[norm_name] = []
                            # Store unique, non-null values for prompts
                            val_str = str(cval).strip()
                            if val_str and val_str not in col_samples[norm_name]:
                                if len(col_samples[norm_name]) < 3: # Limit to 3 samples for brevity
                                    # Truncate very long values (e.g. huge JSON blobs)
                                    if len(val_str) > 100:
                                        val_str = val_str[:100] + "..."
                                    col_samples[norm_name].append(val_str)
            except Exception:
                pass # Fallback to no samples if parsing fails

        if detailed:
            lines.append(f"Table: {table}")
            if not cols:
                lines.append(" - (No columns found)")
            
            for c in cols:
                if isinstance(c, dict):
                    cname = c.get("column_name") or c.get("name") or "unknown"
                    ctype = c.get("type") or c.get("data_type") or ""
                    desc = c.get("description") or ""
                    
                    # Add in-line samples if available (Case-Insensitive lookup)
                    samples = col_samples.get(cname.upper(), [])
                    sample_str = f" [SAMPLES: {', '.join(samples)}]" if samples else ""
                    
                    lines.append(
                        f" - {cname} {f'({ctype})' if ctype else ''}{sample_str}{f' -- {desc}' if desc else ''}"
                    )
                else:
                    cname = str(c)
                    samples = col_samples.get(cname.upper(), [])
                    sample_str = f" [SAMPLES: {', '.join(samples)}]" if samples else ""
                    lines.append(f" - {cname}{sample_str}")
            
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
    """Formats the raw RAG retrieved columns list into a compact string."""
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

    if hasattr(result, "error_message") and result.error_message:
        return f"Execution Error: {result.error_message}"

    rows = getattr(result, "rows", [])
    cols = getattr(result, "columns", [])

    if not rows:
        return "Query executed successfully but returned 0 rows."

    sample = rows[:5]

    if cols:
        header = " | ".join(cols)
        row_strs = [" | ".join(str(v) for v in row) for row in sample]
        return f"{header}\n" + "-" * len(header) + "\n" + "\n".join(row_strs)
    else:
        return "\n".join([" | ".join(str(v) for v in row) for row in sample])
