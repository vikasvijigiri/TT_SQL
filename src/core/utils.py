"""
Shared Utilities for Text-to-SQL Pipeline
Contains formatting and transformation logic used across multiple agents.
"""

import re
import json
from pathlib import Path
from typing import Any, Union
from core.logger import Logger


def format_schema_to_str(schema_info: dict[str, Any], detailed: bool = True, max_samples: int = 1, sample_rows: bool = False, mode: str = "default") -> str:
    """Formats schema dict into a token-optimized string with capped samples and trimmed metadata."""
    if not schema_info:
        return ""
    
    # Task 13: Handle sample_rows toggle
    if sample_rows and max_samples == 0:
        max_samples = 1
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
                            norm_name = str(cname).strip()
                            val_str = str(cval).strip()[:50] # Task 13: Truncate long samples to save tokens
                            if not val_str: continue
                            if norm_name not in col_samples: col_samples[norm_name] = [val_str]
                            elif len(col_samples[norm_name]) < max_samples:
                                if val_str not in col_samples[norm_name]: 
                                    col_samples[norm_name].append(val_str)
            except Exception: pass

        if mode == "compressed":
            lines.append(f"Table: {table}")
            for c in cols:
                if isinstance(c, dict):
                    name = c.get("column_name", c.get("name", "unknown"))
                    ctype = c.get("type", "TEXT")
                    v_keys = c.get("variant_keys", [])
                    
                    line = f" - {name} {ctype}"
                    if v_keys:
                        k_list = list(v_keys.keys()) if isinstance(v_keys, dict) else list(v_keys)
                        key_str = ", ".join(str(k) for k in k_list)
                        line += f" (keys: {key_str})"
                    lines.append(line)
            lines.append("")
        elif detailed:
            lines.append(f"Table: {table}")
            for c in cols:
                if isinstance(c, dict):
                    name = c.get("column_name", c.get("name", "unknown"))
                    ctype = c.get("type", "").split("(")[0] # e.g. VARCHAR(256) -> VARCHAR
                    desc = c.get("description", "").split(".")[0].strip()[:40] # Task 13: Tighten descriptions
                    pk = "*" if c.get("pk") else ""
                    samples = col_samples.get(name, [])
                    smp = f" e.g. {samples[0]}" if samples else ""
                    
                    line = f"- {pk}{name} {ctype}"
                    
                    # Task X: Include Variant Keys in summary
                    v_keys = c.get("variant_keys", [])
                    
                    is_variant = "VARIANT" in ctype.upper()
                    if is_variant:
                         k_list = list(v_keys.keys()) if isinstance(v_keys, dict) else list(v_keys)
                         key_str = ", ".join(str(k) for k in k_list)
                         line += f" (keys: {key_str})"

                    if desc: line += f" | {desc}"
                    if smp and not is_variant: 
                        line += smp
                    lines.append(line)
                    
                    # Present variants correctly under their corresponding column
                    if v_keys and not is_variant: # Keep sub-bullets ONLY for non-explicit-VARIANT types (e.g. OBJECT) if they exist
                        k_list = list(v_keys.keys()) if isinstance(v_keys, dict) else list(v_keys)
                        for k in k_list:
                            lines.append(f"    - {name}.{k}")
            # Only include FKs if manageable
            fks = data.get("foreign_keys", []) if isinstance(data, dict) else []
            if len(fks) < 10:
                for fk in fks:
                    lines.append(f"  ({fk['column']}) -> {fk['ref_table']}")
            lines.append("") 
        else:
            # Minimal view: Just a comma-separated list of columns for full DB context
            cnames = [str(c.get("column_name", c.get("name", c))) if isinstance(c, dict) else str(c) for c in cols]
            lines.append(f"{table}({','.join(cnames)})")
            
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

def write_sql_to_file(instance_id: str, db_name: str, sql: str, model_name: str = "default_model", dialect: str = None):
    """Saves the generated SQL to the instance folder with pretty formatting."""
    from .paths import InstancePaths
    import sqlglot
    
    # Map dialect for sqlglot
    sg_dialect = dialect
    if sg_dialect == "postgresql": sg_dialect = "postgres"
    
    try:
        # Pretty print using sqlglot
        parsed = sqlglot.parse_one(sql, read=sg_dialect)
        # Use pretty=True to ensure line-by-line storage
        pretty_sql = parsed.sql(dialect=sg_dialect, pretty=True)
    except Exception:
        # Fallback to original if sqlglot fails
        pretty_sql = sql
        
    path = InstancePaths.sql(instance_id, db_name, model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(pretty_sql)

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
    import datetime
    
    def default_serializer(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return str(obj)

    path = InstancePaths.db_metadata(db_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema_info, f, indent=2, default=default_serializer)

def quote_identifier(name: str) -> str:
    """
    Safely quote an identifier.
    - Escape internal quotes (")
    - Wrap with double quotes
    - Handle already-quoted input
    """
    if not name:
        return ""
    
    # Handle already-quoted input
    if name.startswith('"') and name.endswith('"'):
        # Just in case there are escaped quotes inside, we clean them up or leave as is?
        # Usually we assume it's already safe if it's quoted.
        return name
        
    # Escape internal double quotes
    safe_name = name.replace('"', '""')
    return f'"{safe_name}"'


def read_db_metadata(db_name: str, dialect: str = "snowflake") -> dict[str, Any] | None:
    """Reads core schema metadata from the common resources folder or the per-table JSON files."""
    from .paths import InstancePaths
    
    # 1. Try internal cache first
    path = InstancePaths.db_metadata(db_name)
    if path.exists() and path.stat().st_size > 0:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
            
    # 2. Try per-table metadata directory
    meta_dir = InstancePaths.database_metadata_dir(db_name, dialect)
    if meta_dir.exists():
        return load_per_table_metadata(meta_dir)
        
    return None

def load_per_table_metadata(meta_dir: Path) -> dict[str, Any]:
    """Loads metadata from per-table JSON files in a directory."""
    schema_info = {}
    for json_file in meta_dir.glob("*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
                table_fullname = data.get("table_fullname") or data.get("table_name")
                if not table_fullname: continue
                
                cols = []
                names = data.get("column_names", [])
                types = data.get("column_types", [])
                descs = data.get("description", [])
                
                for i in range(len(names)):
                    cols.append({
                        "column_name": names[i],
                        "type": types[i] if i < len(types) else "TEXT",
                        "description": descs[i] if i < len(descs) else "",
                        "pk": False # Metadata usually doesn't specify PK
                    })
                
                schema_info[table_fullname] = {
                    "columns": cols,
                    "sample": data.get("sample_rows", []),
                    "foreign_keys": [], # Need to infer or find elsewhere
                    "primary_keys": []
                }
        except Exception as e:
            Logger.log(f"Error loading metadata from {json_file}: {e}", level="WARN")
            
    return schema_info




def modularize_ai_response(response: dict[str, Any]) -> str:
    """
    Simplified modularizer that returns raw JSON dump to adhere to Task 6 (REMOVING free-text outputs).
    """
    if not response or not isinstance(response, dict):
        return str(response)
    
    return f"```json\n{json.dumps(response, indent=2)}\n```"



def normalize_sql(sql: str) -> str:
    """
    Normalizes a SQL query for structural comparison.
    - Removes comments
    - Collapses whitespace
    - Lowercases
    """
    import re
    if not sql:
        return ""
    # Remove comments
    sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    # Collapse whitespace
    sql = " ".join(sql.lower().split())
    # Remove trailing semicolon
    sql = sql.rstrip(";")
    return sql


def has_meaningful_delta(sql_a: str, sql_b: str) -> bool:
    """Returns True if there is a structural difference between two SQL queries."""
    if not sql_a or not sql_b:
        return True
    return normalize_sql(sql_a) != normalize_sql(sql_b)


def check_for_row_explosion_risk(sql: str) -> dict:
    """Heuristic to detect potential row explosion (LATERAL FLATTEN or Cartesian joins)."""
    risks = []
    sql_upper = sql.upper()

    flatten_count = sql_upper.count("LATERAL FLATTEN")
    if flatten_count > 1:
        risks.append(f"Multiple LATERAL FLATTEN detected ({flatten_count}). Risk of row explosion.")
    elif flatten_count == 1 and "DISTINCT" not in sql_upper:
        risks.append("LATERAL FLATTEN used without DISTINCT. High risk of duplicated base rows.")

    if "JOIN" in sql_upper and "ON" not in sql_upper and "USING" not in sql_upper:
        # Check if it's in the FROM list
        from_part = sql_upper.split("FROM")[-1].split("WHERE")[0]
        if "," in from_part:
            risks.append("Implicit cross join detected. Potential Cartesian product.")

    return {"risk_found": len(risks) > 0, "warnings": risks}


def detect_learning_type(error_msg: str, feedback: str = "") -> str:
    """Categorizes the error type based on execution results or critic feedback."""
    err = (str(error_msg) + " " + str(feedback)).lower()
    
    if "Strategy Violation" in feedback or "ignored the strategy" in feedback:
        return "strategy_violation"
    if "Strategy Invalid" in feedback or "Incorrect Strategy" in feedback or "planner_error" in err:
        return "planner_error"
    if "Schema Mismatch" in feedback or "schema_mismatch" in err:
        return "schema_mismatch"
    if "Variant Misuse" in feedback or "FLATTEN" in feedback:
        return "variant_misuse"
    if "Wrong table" in feedback or "concept" in feedback:
        return "wrong_table_usage"
    if "Missing" in feedback and ("table" in feedback or "column" in feedback):
        return "schema_error"
    if "duplication" in err or "flatten" in err or "explosion" in err:
        return "duplication_risk"
    if "aggregation" in err or "count(" in err:
        if "scalar" in err or "valid" in err:
            return "aggregation_valid_scalar"
        if "object" in err or "invalid" in err:
            return "aggregation_object_error"
        return "logical_error"
    if "invalid identifier" in err or "column" in err or "table" in err:
        return "schema_error"
    if "syntax" in err or "unexpected" in err or "compilation" in err:
        return "syntax_error"
    
    return "unknown"


def generate_fallback_feedback(error_msg: str) -> str:
    """Generates heuristic feedback when the Critic fails to provide a valid audit."""
    err = str(error_msg).lower()
    
    if "invalid identifier" in err:
        return "FALLBACK DIAGNOSIS: Identifier mismatch or quoting issue. Verify exact column name and case-sensitivity from the PROVIDED SCHEMA. Snowflake requires double-quotes for case-sensitive identifiers."
    if "group by" in err:
        return "FALLBACK DIAGNOSIS: Aggregation mismatch. Ensure that every column in the SELECT clause that is not part of an aggregate function is listed in the GROUP BY clause."
    if "ambiguous" in err:
        return "FALLBACK DIAGNOSIS: Ambiguous column reference. Multiple tables in your join have the same column name. You MUST prefix it with a table alias (e.g., T1.COLUMN)."
    if "syntax" in err or "compilation" in err:
        return "FALLBACK DIAGNOSIS: SQL Syntax or Dialect Error. Review keyword usage and quoting style for your specific database dialect."
    
    return "FALLBACK DIAGNOSIS: Execution failed. Re-evaluate your join paths, filter conditions, and column identifiers."


def detect_lateral_flatten_issue(sql: str) -> bool:
    """Returns True if the SQL contains the comma-join anti-pattern for LATERAL FLATTEN."""
    sql_upper = sql.upper()
    # Matches patterns like FROM table, LATERAL FLATTEN(...)
    return ", LATERAL FLATTEN" in sql_upper


def detect_missing_distinct(sql: str) -> bool:
    """Returns True if the SQL performs COUNT(*) on a flattened result without DISTINCT."""
    sql_upper = sql.upper()
    if "LATERAL FLATTEN" in sql_upper:
        # Task 3: Prefer COUNT(DISTINCT scalar_id) over COUNT(*)
        if "COUNT(*)" in sql_upper:
            # Check if any COUNT(DISTINCT scalar) exists - if so, maybe it's fine,
            # but if ONLY COUNT(*) exists, it's missing distinct.
            if "COUNT(DISTINCT" not in sql_upper:
                return True
            
            # If COUNT(DISTINCT ...) exists, check if it targets an object
            # (Heuristic: if there's a colon or value reference in the DISTINCT)
            if ":" in sql_upper or "VALUE" in sql_upper:
                # If the DISTINCT itself is on an object, it's still missing a *safe* distinct
                return True
    return False


def map_feedback_to_actions(suggestions: list[str]) -> list[str]:
    """Maps natural language suggestions to internal verification keys."""
    actions = []
    for s in suggestions:
        s_low = s.lower()
        if "flatten" in s_low or "lateral" in s_low:
            actions.append("FIX_LATERAL_JOIN_SYNTAX")
        if "distinct" in s_low or "duplication" in s_low:
            actions.append("ENFORCE_DISTINCT_AGGREGATION")
        if "quote" in s_low or "identifier" in s_low:
            actions.append("FIX_IDENTIFIER_QUOTING")
        if "group by" in s_low:
            actions.append("FIX_GROUP_BY_SYMMETRY")
    return list(set(actions))


def verify_fix_application(sql: str, actions: list[str]) -> list[str]:
    """Audits the SQL against required actions. Returns list of failure messages."""
    failures = []
    sql_upper = sql.upper()
    
    for action in actions:
        if action == "FIX_LATERAL_JOIN_SYNTAX":
            if detect_lateral_flatten_issue(sql):
                failures.append("Action 'FIX_LATERAL_JOIN_SYNTAX' failed: SQL still contains comma-prefixed LATERAL FLATTEN. Use 'CROSS JOIN LATERAL FLATTEN' instead.")
        
        if action == "ENFORCE_DISTINCT_AGGREGATION":
            if detect_missing_distinct(sql):
                failures.append("Action 'ENFORCE_DISTINCT_AGGREGATION' failed: SQL uses COUNT(*) on flattened data. Use COUNT(DISTINCT <primary_key>) to prevent row explosion.")
        
        if action == "FIX_IDENTIFIER_QUOTING":
            if '"' not in sql:
                failures.append("Action 'FIX_IDENTIFIER_QUOTING' failed: SQL lacks quoted identifiers. For case-sensitive dialects, always use double-quotes.")

        if action == "FIX_GROUP_BY_SYMMETRY":
            if "GROUP BY" not in sql_upper and ("COUNT(" in sql_upper or "SUM(" in sql_upper):
                 failures.append("Action 'FIX_GROUP_BY_SYMMETRY' failed: SQL performs aggregation but lacks a GROUP BY clause.")

    return failures


def extract_tables_from_strategy(strategy: Any, relevant_tables: list[str]) -> list[str]:
    """Cross-references strategy text and concept mapping with known relevant tables."""
    if not strategy:
        return []
    
    strategy_text = ""
    mapping = []
    
    if isinstance(strategy, dict):
        primary_strat = strategy.get("primary", "")
        strategy_text = " ".join(primary_strat) if isinstance(primary_strat, list) else str(primary_strat)
        mapping = strategy.get("concept_mapping", [])
    else:
        strategy_text = str(strategy)

    text_clean = strategy_text.replace("`", "").replace('"', "").replace("'", "")
    
    found = []
    # 1. Look in strategy steps
    for table in (relevant_tables or []):
        if re.search(rf"\b{re.escape(table)}\b", text_clean, re.IGNORECASE):
            found.append(table)
    
    # 2. Look in concept mapping
    for item in mapping:
        m = str(item.get("mapped_to", ""))
        for table in (relevant_tables or []):
            if table.upper() in m.upper() and table not in found:
                found.append(table)
                
    return found


def verify_strategy_compliance(sql: str, required_tables: list[str]) -> list[str]:
    """Returns a list of failure messages if any strategy-mandated tables are missing from the SQL."""
    if not required_tables:
        return []
        
    sql_clean = sql.replace('"', '')
    failures = []
    for table in required_tables:
        t_clean = table.replace('"', '')
        if t_clean not in sql_clean:
            # Fallback to case-insensitive check only if strict match fails
            if t_clean.upper() not in sql_clean.upper():
                failures.append(f"Strategy Violation: Required table '{table}' is missing. You MUST use the mandated data sources.")
    return failures


def detect_unsafe_variant_usage(sql: str) -> list[str]:
    """Checks for speculative field access on colon-syntax (e.g. value:\"field\")."""
    import re
    # Matches patterns like :\"field\" or :field
    matches = re.findall(r':"(\w+)"|:(\w+)', sql)
    fields = [m[0] or m[1] for m in matches]
    
    warnings = []
    # Heuristic: If we see very generic or likely-hallucinated fields, flag them.
    # In a production system, we would check these against a dynamic field-discovery cache.
    suspicious = ["metadata", "info", "details", "raw_data"]
    for f in fields:
        if f.lower() in suspicious:
            warnings.append(f"Unsafe VARIANT assumption: Column access ':{f}' detected without verified schema presence.")
    
    return warnings


def normalize_identifier(name: str) -> str:
    """Normalizes an identifier by taking the last part after the dot and stripping quotes/case."""
    if not name: return ""
    # Take last part, e.g., PATENTS.PATENTS.PUBLICATIONS -> PUBLICATIONS
    part = name.split(".")[-1]
    # Remove quotes and whitespace
    return part.replace('"', '').replace('`', '').strip()

def validate_strategy(strategy: dict, schema_info: dict) -> dict:
    """
    Validates the QueryPlanner strategy against the actual schema reality.
    Returns { "is_valid": bool, "warnings": list, "confidence_adjustment": str }
    """
    if not strategy or not isinstance(strategy, dict):
        return {"is_valid": True, "warnings": []}

    warnings = []
    mapping = strategy.get("concept_mapping", [])
    conf = strategy.get("confidence", "high").lower()
    
    # Pre-normalize schema tables
    norm_schema_tables = {normalize_identifier(t): t for t in schema_info.keys()}
    
    for item in mapping:
        concept = item.get("concept")
        mapped_to = item.get("mapped_to", "")
        source_type = item.get("source_type")
        
        if not mapped_to or source_type == "assumption":
            continue
            
        # Parse table.column or table.variant.field
        parts = [p.strip() for p in mapped_to.split(".")]
        
        # Heuristic: If it looks like a function or doesn't have a table part, skip table validation
        if len(parts) < 2 or "(" in parts[0]:
            continue
            
        # Find which part is the table and which is the column
        matched_table = None
        raw_table_name = ""
        for part in reversed(parts[:-1]):
            norm = normalize_identifier(part)
            if norm in norm_schema_tables:
                matched_table = norm_schema_tables[norm]
                raw_table_name = part
                break
                
        if matched_table:
            idx = parts.index(raw_table_name)
            raw_col_name = parts[idx + 1] if idx + 1 < len(parts) else parts[-1]
        else:
            raw_table_name = parts[-2]
            matched_table = norm_schema_tables.get(normalize_identifier(raw_table_name))
            raw_col_name = parts[-1]
        
        # 1. Does table exist? 
        if not matched_table:
            # Task 6: Truly not in schema check
            warnings.append(f"Strategy Mismatch: Concept '{concept}' refers to unknown table '{raw_table_name}'. Verify schema.")
            continue
            
        # 2. Does concept exist in table?
        table_data = schema_info.get(matched_table, {})
        cols = {normalize_identifier(c.get("column_name", c.get("name", ""))): c for c in table_data.get("columns", [])}
        
        norm_col_name = normalize_identifier(raw_col_name)

        if norm_col_name not in cols:
            # Check for VARIANT column that might contain it
            has_variant = any("VARIANT" in str(c.get("type", "")).upper() for c in table_data.get("columns", []))
            if not has_variant:
                # Task 6: Truly not in schema check
                warnings.append(f"Strategy Mismatch: Table '{raw_table_name}' does NOT contain column '{raw_col_name}' for concept '{concept}'.")

    # Task 6: Relaxed Reject criteria
    # Only reject if table truly missing or column truly missing in non-variant table
    is_valid = len([w for w in warnings if "Mismatch" in w]) == 0
    
    # Task 11: Logging mismatch avoided (handled in tool_registry usually, but can be done here)
    if not is_valid:
        Logger.log("Strategy validation failed")
    else:
        Logger.log("Strategy validated successfully")

    adj = conf
    if not is_valid:
        adj = "low"
    elif warnings:
        adj = "medium"

    return {
        "is_valid": is_valid,
        "warnings": warnings,
        "confidence_adjustment": adj
    }

def verify_builder_planner_alignment(strategy: dict, schema_info: dict) -> bool:
    """Task 8: Checks if planner concept_mapping tables and columns exist in schema."""
    validation = validate_strategy(strategy, schema_info)
    if not validation["is_valid"]:
        Logger.log(f"Builder-Planner alignment failure: {validation['warnings']}", level="WARN")
        return False
    return True


def normalize_sql_identifiers(sql: str) -> str:
    """
    Task 6: Enforce aliasing for quoted identifiers to ensure consistency.
    DEPRECATED: Disabled to ensure strict case-preservation as per user request.
    """
    return sql


def fix_duplicate_as_alias(sql: str) -> str:
    """
    Task 5: Auto-repair duplicate AS alias patterns.
    Example: '"patent_id" AS patent_id AS patent_id' → '"patent_id" AS patent_id'
    Handles both quoted (double/backtick) and unquoted source identifiers.
    Iterates until no duplicate AS remains (handles chained duplicates).
    """
    import re
    # Matches: <anything> AS <word> AS <word>  — keeps only the first AS alias
    pattern = r'((?:"[^"]+"|`[^`]+`|\w+)\s+AS\s+\w+)\s+AS\s+\w+'
    prev = None
    while prev != sql:
        prev = sql
        sql = re.sub(pattern, r'\1', sql, flags=re.IGNORECASE)
    return sql


def log_pipeline_event(event_type: str, detail: str, state=None) -> None:
    """
    Task 13: Structured root-cause logging for all pipeline hardening events.
    Recognized event types are logged at ERROR or WARN level.
    Sets state.pipeline_failure_reason on first occurrence of a terminal event.
    All logic is generic — no DB/table/column names hardcoded.
    """
    TERMINAL_EVENTS = {
        "COLUMN_NOT_FOUND",
        "SCHEMA_INSUFFICIENT",
        "REPEATED_FAILURE",
        "MAX_ITERATIONS_REACHED",
        "PIPELINE_GATE_BLOCKED",
    }
    WARN_EVENTS = {
        "CONCEPT_TABLE_MISMATCH",
        "SYNTAX_AUTO_FIXED",
        "SYNTAX_REJECTED",
        "CONFIDENCE_BLOCK",
        "CRITIC_FIX_APPLIED",
    }
    VALID_EVENTS = TERMINAL_EVENTS | WARN_EVENTS
    tag = event_type if event_type in VALID_EVENTS else "PIPELINE_EVENT"
    level = "ERROR" if tag in TERMINAL_EVENTS else "WARN"
    Logger.log(f"[{tag}] {detail}", level=level)
    # Record first terminal failure reason on state (never overwrite)
    if state is not None and tag in TERMINAL_EVENTS:
        if getattr(state, "pipeline_failure_reason", None) is None:
            state.pipeline_failure_reason = f"{tag}: {detail[:200]}"


def extract_concepts_from_missing_columns(
    missing_cols: list,
    strategies: dict,
    schema_info: dict = None,
) -> list:
    """
    Task 1: Maps missing SQL column names back to their concept labels
    using the planner's concept_mapping.
    Generic — no hardcoded column or table names.
    Falls back to synthetic 'column:<name>' labels when no match is found.
    """
    if not missing_cols:
        return []

    # Navigate the nested strategies structure robustly
    concept_mapping = []
    if isinstance(strategies, dict):
        concept_mapping = strategies.get(
            "concept_mapping",
            strategies.get("strategies", {}).get("concept_mapping", []),
        )
        if not concept_mapping and isinstance(strategies.get("strategies"), dict):
            concept_mapping = strategies["strategies"].get("concept_mapping", [])

    missing_upper = {c.strip().strip('"').strip("`").upper() for c in missing_cols}
    found_concepts = []
    for entry in concept_mapping:
        mapped_to = entry.get("mapped_to", "")
        # The final dot-segment is typically the column name
        mapped_col = mapped_to.split(".")[-1].strip('"').strip("`").upper()
        if mapped_col in missing_upper:
            concept = entry.get("concept", "")
            if concept and concept not in found_concepts:
                found_concepts.append(concept)

    # Fallback: use synthetic label so caller always gets something actionable
    if not found_concepts:
        found_concepts = [f"column:{c}" for c in missing_cols]

    return found_concepts


def discover_variant_sources(schema_info: dict, concept_hint: str) -> list:
    """
    Task 2: Scans schema_info for VARIANT/OBJECT/ARRAY columns that semantically
    overlap with the given concept_hint.
    Returns list of {table, variant_column, confidence} sorted by confidence desc.
    Generic — no hardcoded table or column names.
    Uses both exact token overlap and substring matching to handle plural/singular differences.
    """
    if not schema_info or not concept_hint:
        return []

    # Tokenise the concept hint for word-overlap scoring (skip short stop-words)
    concept_lower = concept_hint.lower().replace("_", " ").replace("-", " ")
    concept_words = set(w for w in concept_lower.split() if len(w) > 2)

    sources = []
    for table, data in schema_info.items():
        if not isinstance(data, dict):
            continue
        for col in data.get("columns", []):
            if not isinstance(col, dict):
                continue
            col_type = str(col.get("type", "")).upper()
            if not any(t in col_type for t in ["VARIANT", "OBJECT", "ARRAY", "JSON"]):
                continue
            col_name = col.get("column_name", col.get("name", "")).lower()
            col_desc = col.get("description", "").lower()
            token_pool = set((col_name + " " + col_desc).replace("_", " ").split())

            # Exact token overlap
            overlap = concept_words & token_pool
            # Substring match: handles plural/singular (e.g. "citations" contains "citation")
            if not overlap:
                for cw in concept_words:
                    for tp in token_pool:
                        if cw in tp or tp in cw:
                            overlap.add(cw)
                            break

            if overlap:
                sources.append({
                    "table": table,
                    "variant_column": col.get("column_name", col.get("name", "")),
                    "confidence": round(len(overlap) / max(len(concept_words), 1), 2),
                })

    return sorted(sources, key=lambda x: x["confidence"], reverse=True)


def validate_json_response(response: Any, required_keys: list[str], allowed_values: dict[str, list[Any]] = None) -> dict:
    """
    Task 1: Strictly validates a JSON response against required keys and allowed enum values.
    Returns: {"status": "SUCCESS"} or {"status": "INVALID_JSON", "reason": "..."}
    """
    if not isinstance(response, dict):
        return {"status": "INVALID_JSON", "reason": "parse_error: Response is not a JSON object"}
    
    missing_keys = [k for k in required_keys if k not in response]
    if missing_keys:
        return {"status": "INVALID_JSON", "reason": f"missing_keys: {missing_keys}"}
    
    # Reject unexpected fields
    extra_fields = [k for k in response.keys() if k not in required_keys]
    if extra_fields:
        return {"status": "INVALID_JSON", "reason": f"unexpected_fields: {extra_fields}"}

    if allowed_values:
        for key, valid_list in allowed_values.items():
            if key in response:
                val = response[key]
                if isinstance(val, str):
                    val = val.lower().strip()
                if val not in valid_list:
                    return {"status": "INVALID_JSON", "reason": f"invalid_enum: {key}={val} must be in {valid_list}"}
                    
    return {"status": "SUCCESS"}


def normalize_confidence(value: Any) -> str:
    """
    Task 9: Normalizes confidence level (N/A, unknown -> low).
    Strictly returns one of: {high, medium, low}.
    """
    if not value or not isinstance(value, str):
        return "low"
    
    val = str(value).lower().strip()
    if val in ("high", "medium", "low"):
        return val
    
    return "low"

