import os
import time
import json
from typing import List, Dict, Any, Optional
from src.core.models import ExecutionResult
from src.utils.logger import logger

class Executor:
    def __init__(self, config_path: str = "config/sf_credentials.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        logger.error(f"Snowflake config not found at {self.config_path}")
        return {}

    def execute(self, sql: str, db_name: Optional[str] = None) -> tuple:
        # 1. Determine Engine (Default to Snowflake)
        engine = "snowflake"
        sqlite_path = None
        
        if db_name:
            # Check 1: Direct file in sqlite root: resources/databases/sqlite/DB_name.sqlite
            path1 = os.path.join("resources", "databases", "sqlite", f"{db_name}.sqlite")
            if os.path.exists(path1):
                engine = "sqlite"
                sqlite_path = path1
            
            # Check 2: Recursive search for db_name.sqlite inside resources/databases/sqlite/db_name/
            if not sqlite_path:
                db_dir = os.path.join("resources", "databases", "sqlite", db_name)
                if os.path.exists(db_dir) and os.path.isdir(db_dir):
                    import glob
                    # Search for any file named {db_name}.sqlite recursively in the db_dir
                    matches = glob.glob(os.path.join(db_dir, "**", f"{db_name}.sqlite"), recursive=True)
                    if matches:
                        engine = "sqlite"
                        sqlite_path = matches[0]
                    else:
                        # Fallback: Check for ANY .sqlite file recursively
                        any_matches = glob.glob(os.path.join(db_dir, "**", "*.sqlite"), recursive=True)
                        if any_matches:
                            engine = "sqlite"
                            sqlite_path = any_matches[0]
            
            # Check 3: If db_name is already a path
            if not sqlite_path and db_name.endswith(".sqlite") and os.path.exists(db_name):
                engine = "sqlite"
                sqlite_path = db_name

        if engine == "sqlite":
            return self._execute_sqlite(sql, sqlite_path)
        else:
            return self._execute_snowflake(sql, db_name)

    def _execute_sqlite(self, sql: str, path: str) -> tuple:
        import sqlite3
        logger.info(f"Executing SQL on SQLite ({path}): {sql[:100]}...")
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows, None
        except Exception as e:
            logger.error(f"SQLite execution error: {str(e)}")
            return [], str(e)

    def _execute_snowflake(self, sql: str, db_name: Optional[str] = None) -> tuple:
        logger.info(f"Executing SQL on Snowflake: {sql[:100]}...")
        if not self.config:
            return [], "Snowflake configuration missing"

        # Hardened FQN Rewriting for Snowflake
        if db_name == "IDC":
            # Heuristic: If IDC, we know it needs IDC.IDC_V17.DICOM_ALL
            import re
            # Match DICOM_ALL with optional 1 or 2 part prefixes (e.g. PROJECT.DATASET.DICOM_ALL or DICOM_ALL)
            # and replace with the correct IDC.IDC_V17.DICOM_ALL
            pattern = r"(FROM|JOIN)\s+(?:[a-zA-Z0-9_\"\.]+\.)?\"?DICOM_ALL\"?"
            if re.search(pattern, sql, flags=re.IGNORECASE):
                new_sql = re.sub(pattern, r"\1 IDC.IDC_V17.DICOM_ALL", sql, flags=re.IGNORECASE)
                if new_sql != sql:
                    sql = new_sql
                    logger.info(f"Auto-Rewrote SQL to use FQN: {sql[:100]}...")

        try:
            import snowflake.connector
            conn_params = self.config.copy()
            if db_name:
                conn_params["database"] = db_name
            
            ctx = snowflake.connector.connect(**conn_params)
            cs = ctx.cursor()
            try:
                cs.execute(sql)
                columns = [col[0] for col in cs.description]
                rows = [dict(zip(columns, row)) for row in cs.fetchall()]
                return rows, None
            finally:
                cs.close()
                ctx.close()
        except Exception as e:
            logger.error(f"Snowflake execution error: {str(e)}")
            return [], str(e)
