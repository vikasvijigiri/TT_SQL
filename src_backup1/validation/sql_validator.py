import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import sqlglot
from src.utils.logger import logger

@dataclass
class ValidationResult:
    final_sql: str
    is_valid: bool
    row_count_estimate: int
    retries_used: int
    fixes_applied: List[str]
    warnings: List[str]
    execution_time_ms: float
    rows: List[Dict[str, Any]] = field(default_factory=list)

class SQLValidator:
    """
    Implements an execution feedback loop for SQL validation and auto-correction.
    """
    
    def __init__(self, db_connector, db_name: Optional[str] = None, max_retries: int = 3):
        self.db = db_connector
        self.db_name = db_name
        self.max_retries = max_retries

    def validate_and_execute(self, generated_sql: Any, intent: Dict[str, Any]) -> ValidationResult:
        """
        Validates and executes the SQL once. Errors are returned for the Critic to handle.
        """
        current_sql = generated_sql.sql
        dialect = getattr(generated_sql, 'dialect', 'snowflake')
        fixes = []
        warnings = []
        start_time = time.time()
        
        logger.info("Validating SQL syntax and structure...")
        
        # 1. Syntax Check
        syntax_error = self._check_syntax(current_sql, dialect)
        if syntax_error:
            return ValidationResult(
                final_sql=current_sql,
                is_valid=False,
                row_count_estimate=0,
                retries_used=0,
                fixes_applied=[],
                warnings=[f"Syntax Error: {syntax_error}"],
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        # 2. Dry Run
        db_error = self._dry_run(current_sql, dialect)
        if db_error:
            return ValidationResult(
                final_sql=current_sql,
                is_valid=False,
                row_count_estimate=0,
                retries_used=0,
                fixes_applied=[],
                warnings=[f"DB Error: {db_error}"],
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        # 3. Execution & Data Analysis
        count, rows, exec_error = self._get_rows_and_count(current_sql)
        if exec_error:
            return ValidationResult(
                final_sql=current_sql,
                is_valid=False,
                row_count_estimate=0,
                retries_used=0,
                fixes_applied=[],
                warnings=[f"Execution Error: {exec_error}"],
                execution_time_ms=(time.time() - start_time) * 1000
            )

        if count == 0:
            warnings.append("Query returned zero results.")
            
        execution_time = (time.time() - start_time) * 1000
        return ValidationResult(
            final_sql=current_sql,
            is_valid=True,
            row_count_estimate=count,
            retries_used=0,
            fixes_applied=fixes,
            warnings=warnings,
            execution_time_ms=execution_time,
            rows=rows
        )

    def _check_syntax(self, sql: str, dialect: str) -> Optional[str]:
        try:
            sqlglot.transpile(sql, read=dialect, write=dialect)
            return None
        except Exception as e:
            return str(e)


    def _dry_run(self, sql: str, dialect: str) -> Optional[str]:
        sql_clean = sql.strip().rstrip(";")
        try:
            if dialect == "snowflake":
                self.db.execute(f"EXPLAIN {sql_clean}", db_name=self.db_name)
            else:
                self.db.execute(f"SELECT * FROM ({sql_clean}) AS sub LIMIT 0", db_name=self.db_name)
            return None
        except Exception as e:
            return str(e)

    def _diagnose_empty(self, sql: str, intent: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Checks if removing the lowest-confidence filter returns results."""
        mapped = intent.get("schema_mapping", {}).get("mapped_fields", [])
        if not mapped: return None, None
        
        # Sort by confidence
        sorted_fields = sorted(mapped, key=lambda x: x.get("confidence", 0.0))
        lowest = sorted_fields[0]
        col_to_remove = lowest["column"].split(".")[-1]
        
        # Simple string replacement (heuristic) to remove the condition from WHERE clause
        import re
        # Try to find the condition: AND col = 'val' or WHERE col = 'val'
        relaxed_sql = re.sub(rf"AND\s+.*{col_to_remove}\s*=\s*'.*?'", "", sql, flags=re.IGNORECASE)
        if relaxed_sql == sql:
            relaxed_sql = re.sub(rf"WHERE\s+.*{col_to_remove}\s*=\s*'.*?'", "WHERE 1=1", sql, flags=re.IGNORECASE)
            
        if self._get_row_count(relaxed_sql) > 0:
            return relaxed_sql, lowest["input"]
        return None, None

    def _get_rows_and_count(self, sql: str) -> Tuple[int, List[Dict[str, Any]], Optional[str]]:
        sql_clean = sql.strip().rstrip(";")
        # Executor.execute returns (rows, error)
        rows, error = self.db.execute(sql_clean, db_name=self.db_name)
        return len(rows), rows, error

    def _get_row_count(self, sql: str) -> int:
        count, _, _ = self._get_rows_and_count(sql)
        return count

    def _fix_column_deterministic(self, sql: str, error: str, intent: Dict[str, Any]) -> str:
        """Looks up the closest column match using rapidfuzz (no LLM)."""
        from rapidfuzz import process, fuzz
        
        # Extract column name from error if possible (e.g., "invalid identifier 'MOLDALITY'")
        import re
        match = re.search(r"'(.*?)'", error)
        if not match: return sql
        
        bad_col = match.group(1)
        # Get all schema columns
        mapped = intent.get("schema_mapping", {}).get("mapped_fields", [])
        all_cols = [f["column"].split(".")[-1] for f in mapped]
        
        if not all_cols: return sql
        
        best_match, score, _ = process.extractOne(bad_col, all_cols, scorer=fuzz.WRatio)
        if score > 80:
            return sql.replace(bad_col, best_match)
        return sql


    def _check_schema_contract(self, sql: str, intent: Dict[str, Any]) -> Optional[str]:
        """Verifies that all requested SELECT columns exist in the result set."""
        try:
            # Use sqlglot to find projections
            parsed = sqlglot.parse_one(sql)
            projections = [e.alias_or_name for e in parsed.find_all(sqlglot.exp.Alias)]
            if not projections:
                projections = [e.alias_or_name for e in parsed.find_all(sqlglot.exp.Column)]
            
            target_cols = intent.get("select", {}).get("columns", [])
            for col in target_cols:
                col_name = col.split(".")[-1]
                if col_name not in projections and "*" not in projections:
                    return f"Required column {col_name} missing from SELECT clause."
            return None
        except Exception as e:
            return f"Contract check failed: {e}"
