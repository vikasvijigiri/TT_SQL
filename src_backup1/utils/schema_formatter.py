import json
from typing import Any, Dict

def format_schema_to_str(schema_with_samples: Dict[str, Any], mode: str = "compressed", max_samples: int = 3) -> str:
    """
    Formats the schema into a string for LLM context.
    """
    lines = []
    
    # schema_with_samples is Dict[table_name, {columns: List[Dict], sample_values: List[Dict]}]
    # But wait, SchemaGraphBuilder.schema_with_samples might have a different format.
    # Let's use the format expected by the agents.
    
    for table_name, data in schema_with_samples.items():
        # Get FQN parts from metadata if available
        # data might have 'database' and 'schema' keys
        db = data.get("database", "").replace('"', '')
        sch = data.get("schema", "").replace('"', '')
        
        if db and sch:
            fqn_table = f"{db.upper()}.{sch.upper()}.{table_name.upper()}"
        else:
            fqn_table = table_name.upper()
            
        lines.append(f"{fqn_table}:")
        cols = data.get("columns", [])
        samples = data.get("sample_values", []) # List of Dicts
        
        # Map samples to columns
        col_samples = {}
        for row in samples[:max_samples]:
            for col, val in row.items():
                if col not in col_samples: col_samples[col] = []
                if str(val) not in col_samples[col]: col_samples[col].append(str(val))
        
        for col in cols:
            cname = col.get("name") or col.get("column_name")
            ctype = col.get("type") or col.get("dtype", "TEXT")
            cdesc = col.get("description", "")
            
            smp_list = col_samples.get(cname, [])
            smp_str = f" (e.g. {', '.join(smp_list)})" if smp_list else ""
            
            if mode == "compressed":
                lines.append(f" - {cname} ({ctype}){smp_str}")
            elif mode == "full":
                lines.append(f" - {cname} ({ctype}): {cdesc}{smp_str}")
            elif mode == "with_samples":
                lines.append(f" - {cname} ({ctype}): {cdesc}{smp_str}")
        
        if mode == "with_samples" and samples:
            lines.append("  Sample Rows:")
            for row in samples[:max_samples]:
                lines.append(f"    {json.dumps(row)}")
        lines.append("")
        
    return "\n".join(lines).strip()
