from src.core.models import ExecutionResult
from src.utils.logger import logger

class Validator:
    def validate(self, rows: list, error: str) -> bool:
        if error:
            logger.error(f"Validation failed: {error}")
            return False
        
        if not rows:
            logger.info("Validation: Empty result set.")
            return True
            
        return True

class Guardrails:
    def check_plan(self, sql: str) -> bool:
        sql_upper = sql.upper()
        
        # 1. Prevent full table scans (must have WHERE or LIMIT)
        if "WHERE" not in sql_upper and "LIMIT" not in sql_upper:
            logger.error("Guardrail: Query missing WHERE or LIMIT.")
            return False
            
        # 2. Check for unsafe keywords
        unsafe = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE"]
        if any(u in sql_upper for u in unsafe):
            logger.error("Guardrail: Unsafe keyword detected.")
            return False
            
        return True
