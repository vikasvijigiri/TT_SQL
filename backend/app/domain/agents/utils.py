import re
from typing import Dict, Any, List

def sanitize_string(text: str) -> str:
    """Removes newlines, extra whitespace, and problematic characters."""
    if not text: return ""
    text = re.sub(r'\s+', ' ', text)
    return text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-').strip()

def format_schema_to_str(schema_info: Dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a prompt-ready string."""
    if not schema_info: return ""
    lines = []
    for table, data in schema_info.items():
        cols = data.get("columns", []) if isinstance(data, dict) else data
        if detailed:
            lines.append(f"Table: {table}")
            for c in cols:
                if isinstance(c, dict):
                    name = c.get("column_name") or c.get("name", "unknown")
                    ctype = c.get("type", "")
                    desc = sanitize_string(c.get("description", ""))
                    lines.append(f" - {name} {f'({ctype})' if ctype else ''}{f' -- {desc}' if desc else ''}")
            lines.append("")
        else:
            names = [str(c.get("column_name", "unknown") if isinstance(c, dict) else c) for c in cols]
            lines.append(f"{table}({', '.join(names)})")
    return "\n".join(lines).strip()

def format_rag_columns(rag_columns: list, db_type: str = "postgres") -> str:
    """Formats retrieved RAG columns into a detailed prompt string."""
    if not rag_columns: return ""
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        tables.setdefault(tname, []).append(col)

    lines = []
    is_postgres = db_type.lower() in ["postgres", "postgresql"]
    for tname, cols in tables.items():
        lines.append(f"Table: {tname}")
        for c in cols:
            name = c.get("column_name", "unknown")
            ctype = c.get("type", "unknown")
            desc = sanitize_string(c.get("description", ""))
            samples = c.get("sample_values") or ""
            
            if is_postgres and "varying" in ctype.lower() and any(k in name.lower() for k in ["date", "time", "dt"]):
                ctype += " !! WARNING: Stored as STRING. Use TO_DATE() for comparisons !!"
            
            line = f" - {name} ({ctype}){f' -- {desc}' if desc else ''}{f' [Samples: {samples}]' if samples else ''}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()
