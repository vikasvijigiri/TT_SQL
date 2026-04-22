import os
import sqlite3
import psycopg2
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.agent_state import ExecutionResult
from app.core.settings import settings

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
            from app.repositories.user_repo import UserRepository
            user_repo = UserRepository()
            user_state = user_repo.get_state(user_slug)
            active_id = user_state.get("activeProjectId")

        # 2. Fallback to global settings only if still no project
        if not active_id:
            active_id = settings.ACTIVE_PROJECT_ID

        if active_id:
            from app.repositories.project_repo import ProjectRepository
            project = ProjectRepository.get_project_by_id(active_id, user_slug=user_slug)
            if project and project.get("connection"):
                conn = project["connection"]
                return {
                    "db_type": conn.get("db_type"),  # NO DEFAULT HERE, enforce project config
                    "schema": conn.get("db_name", "public"),
                    "host": conn.get("host", ""),
                    "port": conn.get("port", "5432"),
                    "database": conn.get("database", ""),
                    "user": conn.get("user", ""),
                    "password": conn.get("password", ""),
                    "sqlite_path": DBRepository._resolve_sqlite_path(conn.get("sqlite_path", ""), conn.get("db_name", "")),
                    "db_root": conn.get("db_root") or (conn.get("sqlite_path") if conn.get("db_type") == "bulk_sqlite" else ""),
                    "bq_credentials_path": conn.get("bq_credentials_path", ""),
                    "sf_warehouse": conn.get("sf_warehouse", ""),
                    "sf_role": conn.get("sf_role", ""),
                    "qdrant_collection": conn.get("qdrant_collection", ""),
                    "qdrant_url": conn.get("qdrant_url", ""),
                    "qdrant_api_key": conn.get("qdrant_api_key", ""),
                }

        # If no active project, return empty structure to force explicit configuration
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
            from app.repositories.paths import InstancePaths
            return str(InstancePaths.database(schema))
            
        if os.path.isabs(path):
            if os.path.isdir(path) and schema:
                # If it's a directory, try appending the schema name
                for ext in [".sqlite", ".db", ""]:
                    test_path = os.path.join(path, f"{schema}{ext}")
                    if os.path.exists(test_path):
                        return test_path
            return path
            
        from app.repositories.paths import InstancePaths
        # Try resolving the path itself as a DB name (e.g. "chinook.sqlite")
        resolved = str(InstancePaths.database(path))
        if os.path.exists(resolved):
            return resolved
            
        # Fallback: resolve the schema name if provided
        if schema:
            return str(InstancePaths.database(schema))
            
        return path

    @staticmethod
    def _get_db_connection(active: Dict[str, Any], db_type: str):
        """Unified database connection factory to eliminate code duplication."""
        _type = db_type.lower()
        if _type in ["postgres", "postgresql"]:
            return psycopg2.connect(
                host=active.get("host", ""),
                database=active.get("database", ""),
                user=active.get("user", ""),
                password=active.get("password", ""),
                port=active.get("port", "5432"),
                connect_timeout=10
            )
        elif _type == "bigquery":
            from google.cloud import bigquery
            from google.oauth2 import service_account
            creds_path = active.get("bq_credentials_path")
            if not creds_path or not os.path.exists(creds_path):
                raise Exception(f"BigQuery credentials file not found at: {creds_path}")
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            return bigquery.Client(credentials=credentials, project=active.get("database"))
        elif _type == "snowflake":
            import snowflake.connector
            return snowflake.connector.connect(
                user=active.get("user"),
                password=active.get("password"),
                account=active.get("host"),
                warehouse=active.get("sf_warehouse"),
                database=active.get("database"),
                schema=active.get("schema"),
                role=active.get("sf_role") if active.get("sf_role") else None,
                login_timeout=10
            )
        elif _type == "sqlite":
            import sqlite3
            _path = DBRepository._resolve_sqlite_path(
                active.get("sqlite_path", ""), 
                active.get("db_name", "")
            )
            return sqlite3.connect(_path)
        else:
            raise Exception(f"Unsupported database type: {db_type}")

    @staticmethod
    def execute_query(query: str, db_type: Optional[str] = None, db_name: Optional[str] = None, db_path: Optional[str] = None, user_slug: str = None) -> ExecutionResult:
        """
        Execute a SQL query using the unified repository layer.
        Defaults to active project settings if parameters are omitted.
        """
        active = DBRepository._get_active_connection(user_slug=user_slug)
        
        # Priority: explicit params > active project
        _type = (db_type or active.get("db_type", "")).lower()
        if not _type:
             return ExecutionResult(error_message="No database type configured and no active project found.")

        # Resolve schema/database name override
        _schema = db_name or active.get("schema", "public")

        if _type in ["postgres", "postgresql"]:
            return DBRepository._execute_postgres(query, _schema, active)
        elif _type == "bigquery":
            return DBRepository._execute_bigquery(query, active)
        elif _type == "snowflake":
            return DBRepository._execute_snowflake(query, active)
        else:
            # SQLite path resolution
            _path = db_path or active.get("sqlite_path")
            if not _path or not os.path.isabs(_path):
                 _path = DBRepository._resolve_sqlite_path(_path, _schema)
            return DBRepository._execute_sqlite(query, _path)

    @staticmethod
    def check_connection(db_type: str, user_slug: str = None, active_conn: Dict[str, Any] = None) -> bool:
        """Verifies if a database connection can be established."""
        try:
            active = active_conn or DBRepository._get_active_connection(user_slug=user_slug)
            _type = db_type.lower()
            
            if not active:
                return False
        
            if _type == "bulk_sqlite":
                # For bulk SQLite, we just verify the root directory exists
                db_root = active.get("db_root")
                return db_root is not None and os.path.exists(db_root)
                
            conn = DBRepository._get_db_connection(active, _type)
            if _type == "bigquery":
                # BQ connection is a client, test with a small metadata call
                conn.list_tables(f"{active['database']}.{active['schema']}", max_results=1)
            elif _type == "snowflake":
                conn.execute_string("SELECT 1")
                conn.close()
            elif _type == "sqlite":
                conn.execute("SELECT 1")
                conn.close()
            else:
                conn.close()
            return True
        except Exception as e:
            print(f"Connection check failed for {db_type}: {e}")
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
            print(f"--- DEBUG: BQ CREDS PATH: {creds_path} ---")
            print(f"--- DEBUG: DB name is {active['database']} ---")
            print(f"--- DEBUG: DB schema is {active['schema']} ---")
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
