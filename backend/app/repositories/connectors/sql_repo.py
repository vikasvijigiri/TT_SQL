import os
import sqlite3
import psycopg2
from typing import List, Dict, Any, Tuple, Optional
from app.services.schemas.agent_state import ExecutionResult
from app.repositories.config import settings

class DBRepository:
    """
    Repository layer for database interactions.
    Handles connections and query execution for SQLite and PostgreSQL.
    Dynamically resolves connection parameters from the active project.
    """

    @staticmethod
    def _get_active_connection() -> Dict[str, Any]:
        """
        Resolve the active database connection at runtime.
        Reads the ACTIVE_PROJECT_ID and fetches credentials from ProjectRepository.
        Falls back to static settings if no active project is set.
        """
        active_id = os.environ.get("ACTIVE_PROJECT_ID") or settings.ACTIVE_PROJECT_ID

        if active_id:
            from app.repositories.registry.project_repo import ProjectRepository
            project = ProjectRepository.get_project_by_id(active_id)
            if project and project.get("connection"):
                conn = project["connection"]
                return {
                    "db_type": conn.get("db_type", "postgres"),
                    "schema": conn.get("db_name", "public"),
                    "host": conn.get("host", ""),
                    "port": conn.get("port", "5432"),
                    "database": "postgres",
                    "user": conn.get("user", ""),
                    "password": conn.get("password", ""),
                    "sqlite_path": conn.get("sqlite_path", ""),
                }

        # Fallback to static settings
        return {
            "db_type": settings.DB_TYPE,
            "schema": settings.SCHEMA,
            "host": settings.RDS_HOST,
            "port": settings.RDS_PORT,
            "database": settings.RDS_DATABASE,
            "user": settings.RDS_USER,
            "password": settings.RDS_PASSWORD,
            "sqlite_path": settings.SQLITE_DB_PATH,
        }

    @staticmethod
    def execute_query(query: str, db_type: Optional[str] = None, db_name: Optional[str] = None, db_path: Optional[str] = None) -> ExecutionResult:
        """
        Execute a SQL query and return an ExecutionResult.
        Defaults to the active project settings if parameters are omitted.
        """
        active = DBRepository._get_active_connection()
        _type = db_type or active["db_type"]

        if _type.lower() in ["postgres", "postgresql"]:
            _schema = db_name or active["schema"]
            return DBRepository._execute_postgres(query, _schema, active)
        else:
            _path = db_path or active["sqlite_path"]
            return DBRepository._execute_sqlite(query, _path)

    @staticmethod
    def check_connection(db_type: Optional[str] = None, db_name: Optional[str] = None, db_path: Optional[str] = None) -> bool:
        """
        Verify if the database is accessible, defaulting to the active project context.
        """
        active = DBRepository._get_active_connection()
        _type = db_type or active["db_type"]

        try:
            if _type.lower() in ["postgres", "postgresql"]:
                conn = psycopg2.connect(
                    host=active["host"],
                    database=active["database"],
                    user=active["user"],
                    password=active["password"],
                    port=active["port"],
                    connect_timeout=3
                )
                conn.close()
            else:
                _path = db_path or active["sqlite_path"]
                if not _path or not os.path.exists(_path):
                    return False
                conn = sqlite3.connect(_path)
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
    def _execute_postgres(query: str, schema: str, active: Dict[str, Any] = None) -> ExecutionResult:
        result = ExecutionResult()
        if not active:
            active = DBRepository._get_active_connection()

        conn = None
        try:
            conn = psycopg2.connect(
                host=active["host"],
                database=active["database"],
                user=active["user"],
                password=active["password"],
                port=active["port"],
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
