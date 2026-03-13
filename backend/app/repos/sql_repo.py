import os
import sqlite3
import psycopg2
from typing import List, Dict, Any, Tuple, Optional
from app.models.agent_state import ExecutionResult
from app.models.config import settings

class DBRepository:
    """
    Repository layer for database interactions.
    Handles connections and query execution for SQLite and PostgreSQL.
    """
    
    @staticmethod
    def execute_query(query: str, db_type: str, db_name: str, db_path: Optional[str] = None) -> ExecutionResult:
        """
        Execute a SQL query and return an ExecutionResult.
        """
        if db_type.lower() in ["postgres", "postgresql"]:
            return DBRepository._execute_postgres(query, db_name)
        else:
            return DBRepository._execute_sqlite(query, db_path)

    @staticmethod
    def check_connection(db_type: str, db_name: str, db_path: Optional[str] = None) -> bool:
        """
        Verify if the database is accessible.
        """
        try:
            if db_type.lower() in ["postgres", "postgresql"]:
                host = settings.RDS_HOST
                database = settings.RDS_DATABASE
                user = settings.RDS_USER
                password = settings.RDS_PASSWORD
                port = settings.RDS_PORT
                conn = psycopg2.connect(
                    host=host, database=database, user=user, password=password, port=port,
                    connect_timeout=3
                )
                conn.close()
            else:
                if not db_path or not os.path.exists(db_path):
                    return False
                conn = sqlite3.connect(db_path)
                conn.execute("SELECT 1")
                conn.close()
            return True
        except Exception:
            return False

    @staticmethod
    def _execute_sqlite(query: str, db_path: str) -> ExecutionResult:
        result = ExecutionResult()
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            rows = cursor.fetchall()
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            conn.close()
        except Exception as e:
            result.error_message = str(e)
        return result

    @staticmethod
    def _execute_postgres(query: str, schema: str) -> ExecutionResult:
        result = ExecutionResult()
        host = settings.RDS_HOST
        database = settings.RDS_DATABASE
        user = settings.RDS_USER
        password = settings.RDS_PASSWORD
        port = settings.RDS_PORT
        
        conn = None
        try:
            conn = psycopg2.connect(
                host=host, database=database, user=user, password=password, port=port,
                connect_timeout=10
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            if schema and schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{schema}", public;')

            cursor.execute(query)
            
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            rows = cursor.fetchall()
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
        except Exception as e:
            result.error_message = str(e)
        finally:
            if conn:
                conn.close()
        return result
