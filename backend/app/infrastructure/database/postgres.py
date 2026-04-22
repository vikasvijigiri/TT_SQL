import psycopg2
from typing import Dict, Any
from .base import DatabaseConnector, QueryResult

class PostgresConnector(DatabaseConnector):
    """PostgreSQL specific connector implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = {
            "host": config.get("host"),
            "database": config.get("database"),
            "user": config.get("user"),
            "password": config.get("password"),
            "port": config.get("port", "5432"),
            "connect_timeout": 10
        }
        self.schema = config.get("schema", "public")

    def execute(self, query: str) -> QueryResult:
        result = QueryResult()
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            conn.autocommit = True
            cursor = conn.cursor()
            
            if self.schema and self.schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{self.schema}", public;')

            cursor.execute(query)
            
            if cursor.description:
                result.columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result.rows = [list(row) for row in rows]
                result.row_count = len(rows)
        except Exception as e:
            result.error_message = str(e)
        finally:
            if conn: conn.close()
        return result

    def check_connection(self) -> bool:
        try:
            conn = psycopg2.connect(**self.config)
            conn.close()
            return True
        except Exception:
            return False
