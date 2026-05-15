import hashlib
import re
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from backend.app.utils.logger import logger

class ExecutionStabilizer:
    def __init__(self, executor):
        self.executor = executor
        self.retry_history = set()
        
    def get_sql_hash(self, sql: str) -> str:
        normalized = " ".join(sql.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def verify_schema_reference(self, sql: str, semantic_context: Any) -> Tuple[bool, str]:
        found_identifiers = re.findall(r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)', sql)
        all_table_names = [t.name.upper() for t in semantic_context.tables]
        table_col_map = {t.name.upper(): [c.name.upper() for c in t.columns] for t in semantic_context.tables}
        for table, col in found_identifiers:
            t_up, c_up = table.upper(), col.upper()
            if t_up in all_table_names:
                if c_up not in table_col_map[t_up]:
                    return False, f"Column '{col}' does not exist in table '{table}'."
        return True, ""

    def quote_fqn(self, fqn: str) -> str:
        if not fqn: return ""
        if fqn.lower() == "dual": return "dual" # NEVER quote pseudo-tables
        parts = fqn.split(".")
        quoted_parts = []
        for p in parts:
            clean_p = p.replace('"', '').replace('`', '')
            quoted_parts.append(f'"{clean_p}"')
        return ".".join(quoted_parts)

    def diagnose_filter_collapse(self, sql: str, instance_id: str) -> str:
        logger.info("[EMPTY RESULT DIAGNOSTIC] Analyzing filter collapse...")
        # For CTE heavy queries, our simple regex replacement might be risky.
        # Check if query is too complex for simple diagnostic
        if sql.strip().upper().startswith("WITH") and "UNION ALL" in sql.upper():
            return "Query uses recursive CTEs; skipping automated filter probing to avoid syntax errors."

        where_match = re.search(r'WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|\s+WINDOW|\s+\)|$)', sql, re.IGNORECASE | re.DOTALL)
        if not where_match: return "No WHERE clause found; result is naturally empty."
        
        full_where = where_match.group(1)
        # Split filters by AND but try to respect parentheses (very basic)
        filters = [f.strip() for f in re.split(r'\s+AND\s+(?![^(]*\))', full_where, flags=re.IGNORECASE)]
        
        base_sql_clean = re.sub(r'ORDER\s+BY\s+.*$', '', sql, flags=re.IGNORECASE | re.DOTALL)
        base_sql_clean = re.sub(r'LIMIT\s+\d+\s*;?$', '', base_sql_clean, flags=re.IGNORECASE | re.DOTALL)
        
        current_where = "1=1"
        for f in filters:
            test_where = f"{current_where} AND {f}"
            # Only replace the FIRST occurrence (usually the main filter)
            probe_sql = sql.replace(full_where, test_where, 1)
            
            # Use LIMIT 1 instead of COUNT(*) to avoid wrapping issues if possible
            success, msg, count = self.executor.execute(probe_sql, f"{instance_id}_diag_step")
            if success:
                try:
                    df = pd.read_csv(f"backend/results/{self.executor.db_name}/{instance_id}_diag_step.csv")
                    if len(df) == 0: return f"Filter '{f}' caused the result set to collapse to 0 rows."
                    current_where = test_where
                except: pass
        return "Collapse may be due to the combination of conditions or join mismatches."

    def get_sample_evidence(self, table_name: str, instance_id: str) -> str:
        logger.info(f"[DATA EVIDENCE] Probing sample rows for {table_name}...")
        quoted_table = self.quote_fqn(table_name)
        probe_sql = f"SELECT * FROM {quoted_table} LIMIT 3"
        success, msg, count = self.executor.execute(probe_sql, f"{instance_id}_evidence")
        if success:
            try:
                df = pd.read_csv(f"backend/results/{self.executor.db_name}/{instance_id}_evidence.csv")
                return df.to_markdown(index=False)
            except: return "No sample rows found."
        return f"Probe failed: {msg}"
