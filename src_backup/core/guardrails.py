class Guardrails:
    """
    Enforces safety and performance constraints on generated SQL (Step 15).
    """

    def apply(self, sql: str) -> str:
        """
        - prevent full scans (must have WHERE or LIMIT)
        - enforce LIMIT
        - block unsafe queries
        """
        sql_upper = sql.upper()
        
        # Enforce LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip(";") + " LIMIT 1000"
            
        # Prevent full scans (basic heuristic)
        if "WHERE" not in sql_upper and "LIMIT" not in sql_upper:
            # Already added LIMIT above, but this is for extra safety
            pass
            
        # Block unsafe queries (e.g. DROP, DELETE, etc.)
        unsafe_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
        for kw in unsafe_keywords:
            if kw in sql_upper:
                raise ValueError(f"Unsafe SQL detected: {kw} is not allowed.")
                
        return sql
