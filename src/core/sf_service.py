import json
import os
from typing import Any

import snowflake.connector

from .config import get_settings
from .logger import Logger


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
                )
                Logger.log(f"[SF] Connected to account `{account}`.")
            except Exception as e:
                Logger.log(f"[SF] Connection failed: {e}", level="ERROR")
                return None

        return self._conn

    def get_schema(self, database: str, schema: str = "PUBLIC") -> dict[str, Any]:
        """
        Fetch schema for all tables in a Snowflake database/schema using INFORMATION_SCHEMA.
        """
        conn = self.get_connection(database=database, schema=schema)
        if not conn:
            return {}

        Logger.log(
            f"[SF] Fetching Batch Schema for `{database}.{schema}` via INFORMATION_SCHEMA..."
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
            table_schema = '{schema.upper()}'
        ORDER BY 
            table_name, ordinal_position
        """

        try:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()

            schema_info = {}
            for row in results:
                # row structure: (table_name, column_name, data_type, comment)
                tname = row[0]
                if tname not in schema_info:
                    schema_info[tname] = {"columns": []}

                schema_info[tname]["columns"].append(
                    {
                        "column_name": row[1],
                        "type": row[2],
                        "description": row[3] or "",
                        "pk": False,  # Metadata for PKs requires separate query or parsing
                    }
                )

            Logger.log(
                f"[SF] Schema Discovery Complete: Found {len(schema_info)} tables in `{database}.{schema}`."
            )
            return schema_info
        except Exception as e:
            Logger.log(f"[SF] Failed to fetch Snowflake Schema: {e}", level="ERROR")
            return {}
