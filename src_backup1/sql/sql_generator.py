from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from src.utils.logger import logger

@dataclass
class GeneratedSQL:
    sql: str
    dialect: str
    skipped_conditions: List[str]
    tables_used: List[str]
    estimated_complexity: str
    llm_polished: bool

class SQLGenerator:
    """
    Constructs SQL queries deterministically from intent IR with an LLM polish pass.
    """
    
    def __init__(self, llm, dialect: str = "snowflake"):
        self.llm = llm
        self.dialect = dialect

    def generate(self, intent: Dict[str, Any], few_shot_examples: str = "") -> GeneratedSQL:
        """
        Main entry point for SQL generation.
        """
        logger.info(f"Generating {self.dialect} SQL...")
        
        # 1. Build raw SQL deterministically
        raw_sql, skipped, tables = self._build_raw_sql(intent)
        
        # 2. LLM Polish for syntax and aliases
        polished_sql = self._polish_sql(raw_sql, intent, few_shot_examples)
        
        logger.info("=== GENERATED SQL ===\n" + polished_sql)
        
        return GeneratedSQL(
            sql=polished_sql,
            dialect=self.dialect,
            skipped_conditions=skipped,
            tables_used=tables,
            estimated_complexity=intent.get("complexity", "simple"),
            llm_polished=True
        )

    def _build_raw_sql(self, intent: Dict[str, Any]) -> tuple[str, List[str], List[str]]:
        """Constructs SQL string from intent components."""
        select_clause = self._build_select(intent)
        from_clause, tables = self._build_from(intent)
        where_clause, skipped = self._build_where(intent)
        
        sql = f"{select_clause}\n{from_clause}"
        if where_clause:
            sql += f"\nWHERE {where_clause}"
            
        return sql, skipped, tables

    def _build_select(self, intent: Dict[str, Any]) -> str:
        select = intent.get("select", {})
        if select.get("include_all"):
            return "SELECT *"
        
        cols = select.get("columns", [])
        if not cols:
            # Fallback to mapped fields if select is empty
            cols = [f["column"] for f in intent.get("schema_mapping", {}).get("mapped_fields", [])]
            
        if not cols:
            return "SELECT *"
            
        return "SELECT " + ", ".join(cols)

    def _build_from(self, intent: Dict[str, Any]) -> tuple[str, List[str]]:
        source = intent.get("source", {})
        primary = source.get("primary_table")
        if not primary:
            # Try to guess from candidate_tables
            candidates = source.get("candidate_tables", [])
            primary = candidates[0] if candidates else "UNKNOWN_TABLE"
            
        from_str = f"FROM {primary}"
        tables = [primary]
        
        # Add joins if present
        joins = source.get("joins", [])
        for j in joins:
            # j is a dict or JoinStep
            left = j.get("left_table")
            right = j.get("right_table")
            l_col = j.get("left_col")
            r_col = j.get("right_col")
            j_type = j.get("join_type", "LEFT")
            from_str += f"\n{j_type} JOIN {right} ON {left}.{l_col} = {right}.{r_col}"
            tables.append(right)
            
        return from_str, list(set(tables))

    def _build_where(self, intent: Dict[str, Any]) -> tuple[str, List[str]]:
        conditions = []
        skipped = []
        
        # Flatten conditions from filters group
        def walk(node):
            if node.get("type") == "condition":
                # Check if it was resolved
                res_col = node.get("resolved_column")
                res_tab = node.get("resolved_table")
                if res_col and res_tab:
                    op = node.get("operator")
                    val = node.get("value")
                    
                    # Handle value formatting
                    if isinstance(val, str):
                        val_str = f"'{val}'"
                    elif isinstance(val, list):
                        val_str = "(" + ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in val]) + ")"
                    else:
                        val_str = str(val)
                        
                    # Dialect-specific array/json handling
                    if self.dialect == "snowflake" and "Sequence" in res_col: # Heuristic for DICOM JSON
                        cond = f"ARRAY_CONTAINS({val_str}::VARIANT, {res_tab}.{res_col})"
                    elif self.dialect == "bigquery" and "Sequence" in res_col:
                        cond = f"EXISTS(SELECT 1 FROM UNNEST({res_tab}.{res_col}) AS x WHERE x = {val_str})"
                    else:
                        cond = f"{res_tab}.{res_col} {op} {val_str}"
                    conditions.append(cond)
                else:
                    skipped.append(node.get("raw_field", "unknown"))
                    
            if node.get("type") == "group":
                for c in node.get("conditions", []): walk(c)
                
        walk(intent.get("filters", {}))
        
        return " AND ".join(conditions), skipped

    def _polish_sql(self, raw_sql: str, intent: Dict[str, Any], few_shot_examples: str = "") -> str:
        """Calls LLM for syntax polish and aliasing."""
        prompt = f"""
        You are a SQL expert. Given an auto-generated SQL query, fix any syntax issues, add readable aliases, 
        and ensure it is valid {self.dialect} SQL. Do not change the logic or add conditions.
        
        {few_shot_examples}
        
        TARGET SQL TO FIX:
        {raw_sql}
        
        Return ONLY the fixed SQL, no explanation.
        """
        
        messages = [{"role": "user", "content": prompt}]
        try:
            res = self.llm.get_completion(messages, agent_name="SQLGenerator")
            # Extract SQL if LLM returned it in markdown blocks
            import re
            match = re.search(r"```sql\s*(.*?)\s*```", res, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return res.strip()
        except Exception as e:
            logger.warning(f"SQL polish failed: {e}. Returning raw SQL.")
            return raw_sql
