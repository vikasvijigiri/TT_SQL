import sqlite3
import os
from .base import DatabaseConnector, QueryResult

class SQLiteConnector(DatabaseConnector):
    """SQLite specific connector implementation."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute(self, query: str) -> QueryResult:
        result = QueryResult()
        try:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"SQLite database not found at: {self.db_path}")
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                result.columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result.rows = [list(row) for row in rows]
                result.row_count = len(rows)
            conn.close()
        except Exception as e:
            result.error_message = str(e)
        return result

    def check_connection(self) -> bool:
        try:
            if not os.path.exists(self.db_path): return False
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except Exception:
            return False
