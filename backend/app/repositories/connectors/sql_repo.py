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
    def _get_active_connection(user_slug: str = None) -> Dict[str, Any]:
        """
        Resolve the active database connection at runtime.
        Priority: User Registry (user_slug) > os.environ > settings.
        """
        active_id = None

        # 1. Check User Registry if slug provided
        if user_slug:
            from app.repositories.registry.user_repo import UserRepository
            user_repo = UserRepository()
            user_state = user_repo.get_state(user_slug)
            active_id = user_state.get("activeProjectId")

        # 2. Fallback to global env only if still no project
        if not active_id:
            active_id = os.environ.get("ACTIVE_PROJECT_ID") or settings.ACTIVE_PROJECT_ID

        if active_id:
            from app.repositories.registry.project_repo import ProjectRepository
            project = ProjectRepository.get_project_by_id(active_id, user_slug=user_slug)
            if project and project.get("connection"):
                conn = project["connection"]
                return {
                    "db_type": conn.get("db_type", "postgres"),
                    "schema": conn.get("db_name", "public"),
                    "host": conn.get("host", ""),
                    "port": conn.get("port", "5432"),
                    "database": conn.get("database", "postgres"),
                    "user": conn.get("user", ""),
                    "password": conn.get("password", ""),
                    "sqlite_path": DBRepository._resolve_sqlite_path(conn.get("sqlite_path", ""), conn.get("db_name", "")),
                    "bq_credentials_path": conn.get("bq_credentials_path", ""),
                    "sf_warehouse": conn.get("sf_warehouse", ""),
                    "sf_role": conn.get("sf_role", ""),
                    "qdrant_collection": conn.get("qdrant_collection", ""),
                    "qdrant_url": conn.get("qdrant_url", ""),
                    "qdrant_api_key": conn.get("qdrant_api_key", ""),
                }

        # If no active project, return empty or throw? 
        # The user said "not from the .env file", so we should return an empty structure
        return {}

    @staticmethod
    def get_collection_name(active_conn: Dict[str, Any] = None, default: str = None) -> str:
        """
        Centralized collection name resolution for RAG/Vector Store operations.
        Uses single source of truth to prevent path mismatches.
        
        Priority:
        1. qdrant_collection (explicit project setting)
        2. schema (db_name from connection)
        3. database (fallback)
        4. default parameter
        5. "default" (final fallback)
        """
        if not active_conn:
            return default or "default"
        
        collection_name = (
            active_conn.get("qdrant_collection") or
            active_conn.get("schema") or
            active_conn.get("database") or
            default or
            "default"
        )
        
        return collection_name

    @staticmethod
    def _resolve_sqlite_path(path: str, schema: str = "") -> str:
        """
        Ensures a SQLite path is absolute. Resolves relative paths or 
        simple filenames against the default analytical database directory.
        """
        if not path:
            if not schema: return ""
            from app.repositories.registry.paths import InstancePaths
            return str(InstancePaths.database(schema))
            
        if os.path.isabs(path):
            return path
            
        from app.repositories.registry.paths import InstancePaths
        # Try resolving the path itself as a DB name (e.g. "chinook.sqlite")
        resolved = str(InstancePaths.database(path))
        if os.path.exists(resolved):
            return resolved
            
        # Fallback: resolve the schema name if provided
        if schema:
            return str(InstancePaths.database(schema))
            
        return path

    @staticmethod
    def execute_query(query: str, db_type: Optional[str] = None, db_name: Optional[str] = None, db_path: Optional[str] = None, user_slug: str = None) -> ExecutionResult:
        """
        Execute a SQL query and return an ExecutionResult.
        Defaults to the active project settings if parameters are omitted.
        """
        active = DBRepository._get_active_connection(user_slug=user_slug)
        if not active:
             return ExecutionResult(error_message="No active project connected. Please select a project first.")

        _type = db_type or active.get("db_type")
        if not _type:
             return ExecutionResult(error_message="Database type not configured for this project.")

        if _type.lower() in ["postgres", "postgresql"]:
            _schema = db_name or active.get("schema", "public")
            return DBRepository._execute_postgres(query, _schema, active)
        elif _type.lower() == "bigquery":
            return DBRepository._execute_bigquery(query, active)
        elif _type.lower() == "snowflake":
            return DBRepository._execute_snowflake(query, active)
        else:
            # Path is already resolved in _get_active_connection, 
            # but if it's passed explicitly here we resolve it too
            _path = db_path or active["sqlite_path"]
            if _path and not os.path.isabs(_path):
                _path = DBRepository._resolve_sqlite_path(_path, db_name or active["schema"])
                
            return DBRepository._execute_sqlite(query, _path)

    @staticmethod
    def check_connection(db_type: Optional[str] = None, db_name: Optional[str] = None, db_path: Optional[str] = None, user_slug: str = None) -> bool:
        """
        Verify if the database is accessible, defaulting to the active project context.
        """
        active = DBRepository._get_active_connection(user_slug=user_slug)
        if not active:
            return False
        _type = db_type or active.get("db_type")
        if not _type:
            return False

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
            elif _type.lower() == "bigquery":
                from google.cloud import bigquery
                from google.oauth2 import service_account
                creds_path = active["bq_credentials_path"]
                if not creds_path or not os.path.exists(creds_path):
                    return False
                credentials = service_account.Credentials.from_service_account_file(creds_path)
                client = bigquery.Client(credentials=credentials, project=active["database"])
                # Just try to list tables in the dataset as a connectivity test
                client.list_tables(f"{active['database']}.{active['schema']}", max_results=1)
            elif _type.lower() == "snowflake":
                import snowflake.connector
                conn = snowflake.connector.connect(
                    user=active["user"],
                    password=active["password"],
                    account=active["host"],
                    warehouse=active["sf_warehouse"],
                    database=active["database"],
                    schema=active["schema"],
                    role=active["sf_role"] if active["sf_role"] else None,
                    login_timeout=5
                )
                conn.execute_string("SELECT 1")
                conn.close()
            else:
                _path = db_path or active["sqlite_path"]
                if _path and not os.path.isabs(_path):
                    _path = DBRepository._resolve_sqlite_path(_path, db_name or active["schema"])
                    
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

    @staticmethod
    def _execute_bigquery(query: str, active: Dict[str, Any]) -> ExecutionResult:
        result = ExecutionResult()
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
            
            creds_path = active["bq_credentials_path"]
            if not creds_path or not os.path.exists(creds_path):
                raise Exception(f"BigQuery credentials file not found at: {creds_path}")
                
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            client = bigquery.Client(credentials=credentials, project=active["database"])
            
            query_job = client.query(query)
            rows = query_job.result()
            
            # Extract columns
            if rows.schema:
                result.columns = [field.name for field in rows.schema]
            
            # Extract data
            result.rows = [list(row) for row in rows]
            result.row_count = len(result.rows)
            
        except Exception as e:
            result.error_message = str(e)
        return result

    @staticmethod
    def _execute_snowflake(query: str, active: Dict[str, Any]) -> ExecutionResult:
        result = ExecutionResult()
        conn = None
        try:
            import snowflake.connector
            conn = snowflake.connector.connect(
                user=active["user"],
                password=active["password"],
                account=active["host"],
                warehouse=active["sf_warehouse"],
                database=active["database"],
                schema=active["schema"],
                role=active["sf_role"] if active["sf_role"] else None
            )
            cursor = conn.cursor()
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
