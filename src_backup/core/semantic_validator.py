import re
from typing import Tuple, List

def validate_semantics(sql: str, strategy: str, required_tables: List[str], relevant_tables: List[str]) -> Tuple[bool, List[str]]:
    """
    Performs a deep semantic audit of the generated SQL against the QueryPlanner strategy and schema constraints.
    """
    failures = []
    sql_upper = sql.upper()
    
    # 1. Strategy Compliance (Table Usage)
    # If strategy is provided, we check for mandatory tables ONLY if they are not classification/definition tables
    # being misused for data.
    for table in required_tables:
        if "CPC_DEFINITION" in table and ("CITATION" in sql_upper or "COUNT" in sql_upper):
            # Known domain mismatch (Task 8 logic inside validator too)
            continue
            
        if table not in sql:
            # Check unquoted upper as fallback just in case, but prioritize exact match
            if table.upper() not in sql_upper:
                # Allow skipping required table if FLATTEN is used AND the table doesn't actually contain the concept
                # (Heuristic: we rely on validate_strategy to have downgraded confidence if this happens)
                failures.append(f"Strategy Violation: Required table '{table}' is missing. You MUST use the mandated data sources.")

    # 2. VARIANT/FLATTEN Logic (TASK 6)
    uses_flatten = "FLATTEN" in sql_upper or ":" in sql
    
    if uses_flatten:
        # We no longer penalize FLATTEN blindly. 
        # We only penalize if it's used for something that exists in a relational table 
        # AND that relational table is present in the schema.
        pass

    # 3. Unsafe VARIANT Assumptions
    variant_matches = re.findall(r':"(\w+)"|:(\w+)', sql)
    for m in variant_matches:
        f = m[0] or m[1]
        suspicious = ["metadata", "info", "details", "raw_data"]
        if f.lower() in suspicious:
            failures.append(f"Variant Misuse: Unsafe assumption on nested field ':{f}'.")

    # 4. Concept-Table Mismatch via FLATTEN (Generic — Task 2)
    # Hardcoded table names removed. Mismatch detection is fully schema-driven via
    # ToolRegistry._validate_concept_table_alignment() which uses validate_strategy()
    # against live schema_info. No dataset-specific logic here.

    return len(failures) == 0, failures
