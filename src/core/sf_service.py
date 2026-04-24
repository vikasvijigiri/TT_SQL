import json
import os
import time
from typing import Any

import snowflake.connector

from .config import get_settings
from .logger import Logger
from .state import ExecutionResult


class SnowflakeService:
    """
    Service for Snowflake interactions.
    Handles connection management and metadata extraction.
    """

    _instance = None
    _conn = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls):
        """Resets the Snowflake connection and instance."""
        if cls._conn:
            try:
                cls._conn.close()
            except:
                pass
        cls._conn = None
        cls._instance = None
        Logger.log("SnowflakeService state reset.", level="DEBUG")

    def get_connection(
        self, database: str = None, schema: str = None, warehouse: str = None
    ):
        if self._conn is None:
            settings = get_settings()
            creds_path = settings.sf_credentials_abs_path

            creds = {}
            if creds_path and os.path.exists(creds_path):
                with open(creds_path) as f:
                    creds = json.load(f)

            # Priority: Credentials file -> Env Vars -> Args
            user = creds.get("user") or os.getenv("SNOWFLAKE_USER")
            password = creds.get("password") or os.getenv("SNOWFLAKE_PASSWORD")
            account = creds.get("account") or os.getenv("SNOWFLAKE_ACCOUNT")

            # Optional connection parameters
            target_database = (
                database or creds.get("database") or os.getenv("SNOWFLAKE_DATABASE")
            )
            target_schema = (
                schema or creds.get("schema") or os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
            )
            target_warehouse = (
                warehouse or creds.get("warehouse") or os.getenv("SNOWFLAKE_WAREHOUSE")
            )
            target_role = (
                creds.get("role") or os.getenv("SNOWFLAKE_ROLE")
            )

            if not all([user, password, account]):
                Logger.log(
                    "[SF] Missing required credentials (user, password, or account).",
                    level="ERROR",
                )
                return None

            try:
                self._conn = snowflake.connector.connect(
                    user=user,
                    password=password,
                    account=account,
                    warehouse=target_warehouse,
                    database=target_database,
                    schema=target_schema,
                    role=target_role,
                )
                Logger.log(f"[SF] Connected to account `{account}` (Role: {target_role}).")
            except Exception as e:
                Logger.log(f"[SF] Connection failed: {e}", level="ERROR")
                return None

        return self._conn

    def get_schema(self, database: str, schema: str | None = None) -> dict[str, Any]:
        """
        Fetch schema for all tables in a Snowflake database/schema using INFORMATION_SCHEMA.
        """
        if not database:
            return {}

        conn = self.get_connection(database=database, schema=schema)
        if not conn:
            return {}

        # Default to DATABASE name as schema (common pattern), then fallback to PUBLIC
        schemas_to_try = []
        if schema:
            schemas_to_try.append(schema)
        
        if database and (not schema or schema.upper() != database.upper()):
            schemas_to_try.append(database)
            
        if "PUBLIC" not in [s.upper() for s in schemas_to_try]:
            schemas_to_try.append("PUBLIC")

        for current_schema in schemas_to_try:
            Logger.log(
                f"[SF] Fetching Batch Schema for `{database}.{current_schema}` via INFORMATION_SCHEMA..."
            )

            query = f"""
            SELECT 
                table_name, 
                column_name, 
                data_type, 
                comment 
            FROM 
                {database}.INFORMATION_SCHEMA.COLUMNS
            WHERE 
                table_schema = '{current_schema.upper()}'
            ORDER BY 
                table_name, ordinal_position
            """

            try:
                cursor = conn.cursor()
                cursor.execute(query)
                results = cursor.fetchall()

                if not results:
                    continue

                schema_info = {}
                for row in results:
                    # row structure: (table_name, column_name, data_type, comment)
                    tname = row[0]
                    # Qualify table name with DB and SCHEMA for unambiguous prompt context
                    qualified_name = f"{database.upper()}.{current_schema.upper()}.{tname.upper()}"
                    if qualified_name not in schema_info:
                        # Fetch a sample row for data profiling (crucial for VARIANT types)
                        sample_data = self._get_sample_row(conn, database, current_schema, tname)
                        schema_info[qualified_name] = {"columns": [], "sample": sample_data}

                    schema_info[qualified_name]["columns"].append(
                        {
                            "column_name": row[1],
                            "type": row[2],
                            "description": row[3] or "",
                            "pk": False,  # Metadata for PKs requires separate query or parsing
                        }
                    )

                Logger.log(
                    f"[SF] Schema Discovery Complete: Found {len(schema_info)} tables in `{database}.{current_schema}`."
                )
                return schema_info
            except Exception as e:
                Logger.log(f"[SF] Failed to fetch Snowflake Schema for `{current_schema}`: {e}", level="ERROR")
        
        return {}

    def execute_query(self, query: str, sampling: bool = False) -> ExecutionResult:
        """Executes a query and returns an ExecutionResult object."""
        start_t = time.time()
        result = ExecutionResult()
        try:
            # Note: We rely on the established connection or defaults
            conn = self.get_connection()
            if not conn:
                raise Exception("Failed to establish Snowflake connection.")

            cursor = conn.cursor()
            cursor.execute(query)

            # Fetch columns
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]

            # Fetch rows
            if sampling:
                rows = cursor.fetchmany(5)
            else:
                rows = cursor.fetchall()

            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)

        except Exception as e:
            result.error_message = str(e)
            Logger.log(f"[SF] Query execution failed: {e}", level="ERROR")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        return result

    def _get_sample_row(self, conn, database, schema, table_name) -> str:
        """Internal helper to sample multiple rows for high-precision profiling."""
        try:
            cursor = conn.cursor()
            # Ensure identifiers are quoted
            fqn = f'"{database.upper()}"."{schema.upper()}"."{table_name.upper()}"'
            # Fetch 3 rows for better pattern recognition
            cursor.execute(f"SELECT * FROM {fqn} LIMIT 3")
            rows = cursor.fetchall()
            if not rows:
                return "NULL_OR_EMPTY"
            
            # Map columns to values for a rich data profile
            cols = [d[0] for d in cursor.description]
            samples = []
            for row in rows:
                samples.append(dict(zip(cols, row)))
            
            return samples
        except Exception as e:
            return f"SAMPLE_ERROR: {str(e)}"
