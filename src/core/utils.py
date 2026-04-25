"""
Shared Utilities for Text-to-SQL Pipeline
Contains formatting and transformation logic used across multiple agents.
"""

import json
from pathlib import Path
from typing import Any, Union


def format_schema_to_str(schema_info: dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a detailed multi-line string with IN-LINE column samples."""
    if not schema_info:
        return ""
    lines = []
    for table, data in schema_info.items():
        cols = data.get("columns", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        col_samples = {}
        if isinstance(data, dict) and data.get("sample"):
            try:
                raw_sample = data["sample"]
                sample_data = json.loads(raw_sample) if isinstance(raw_sample, str) else raw_sample
                if isinstance(sample_data, list):
                    for row in sample_data:
                        for cname, cval in row.items():
                            norm_name = str(cname).strip().upper()
                            val_str = str(cval).strip()
                            if val_str and norm_name not in col_samples: col_samples[norm_name] = [val_str]
                            elif val_str and val_str not in col_samples[norm_name] and len(col_samples[norm_name]) < 2:
                                col_samples[norm_name].append(val_str)
            except Exception: pass

        if detailed:
            lines.append(f"Table: {table}")
            for c in cols:
                if isinstance(c, dict):
                    name = c.get("column_name", c.get("name", "unknown"))
                    ctype = c.get("type", "")
                    desc = c.get("description", "").strip()
                    pk = " (pk)" if c.get("pk") else ""
                    samples = col_samples.get(name.upper(), [])
                    smp = f" [e.g. {', '.join(samples)}]" if samples else ""
                    line = f"- {name}"
                    if ctype: line += f" ({ctype})"
                    if desc: line += f" ({desc})"
                    line += f"{pk}{smp}"
                    lines.append(line)
            fks = data.get("foreign_keys", []) if isinstance(data, dict) else []
            for fk in fks:
                lines.append(f"  ({fk['column']}) -> {fk['ref_table']}.{fk['ref_column']}")
            lines.append("") 
        else:
            cnames = [str(c.get("column_name", c.get("name", c))) if isinstance(c, dict) else str(c) for c in cols]
            lines.append(f"{table}({', '.join(cnames)})")
            
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



def load_jsonl(file_path: Union[str, Path]) -> list[dict[str, Any]]:
    """Generic Data Loader for Text2SQL datasets. Handles JSONL parsing and field mapping."""
    tasks = []
    path = Path(file_path)

    if not path.exists():
        print(f"Dataset not found: {path}")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        item = json.loads(line)
                        task = {
                            "instance_id": item.get("instance_id") or item.get("id") or "unknown",
                            "db": item.get("db") or item.get("db_id") or item.get("database"),
                            "question": item.get("question") or item.get("utterance"),
                            "external_knowledge": item.get("external_knowledge") or item.get("knowledge"),
                            "raw_data": item,
                        }
                        tasks.append(task)
                    except json.JSONDecodeError:
                        continue

        return tasks
    except Exception as e:
        print(f"Failed to load dataset {path}: {e}")
        return []

# --- IO HELPERS ---

def write_sql_to_file(instance_id: str, db_name: str, sql: str, model_name: str = "default_model"):
    """Saves the generated SQL to the instance folder."""
    from .paths import InstancePaths
    path = InstancePaths.sql(instance_id, db_name, model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(sql)

def write_csv_to_file(instance_id: str, db_name: str, rows: list[list[Any]], columns: list[str], model_name: str = "default_model"):
    """Saves the query results to a CSV file."""
    import csv
    from .paths import InstancePaths
    path = InstancePaths.csv(instance_id, db_name, model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if columns:
            writer.writerow(columns)
        writer.writerows(rows)

def write_plan_to_file(instance_id: str, db_name: str, plan: list[str], model_name: str = "default_model"):
    """Saves the action plan to the instance folder."""
    from .paths import InstancePaths
    path = InstancePaths.plan(instance_id, db_name, model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Step-by-Step Approach\n\n")
        f.write("\n".join(f"{i+1}. {step}" for i, step in enumerate(plan)))

def write_db_metadata(db_name: str, schema_info: dict[str, Any]):
    """Writes core schema metadata to the common resources folder."""
    from .paths import InstancePaths
    path = InstancePaths.db_metadata(db_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema_info, f, indent=2)

def read_db_metadata(db_name: str) -> dict[str, Any] | None:
    """Reads core schema metadata from the common resources folder."""
    from .paths import InstancePaths
    path = InstancePaths.db_metadata(db_name)
    if path.exists() and path.stat().st_size > 0:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None
