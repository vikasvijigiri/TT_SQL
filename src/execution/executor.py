import os
import json
import glob
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional
from src.utils.logger import logger


class DatabaseExecutor:
    def __init__(self, db_name: str, dialect: str = "snowflake",
                 sf_config_path: str = "config/sf_credentials.json"):
        self.dialect = dialect
        self.db_name = db_name.upper()
        self.sf_config = self._load_sf_config(sf_config_path)

    def _load_sf_config(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        logger.error(f"Snowflake config not found at {path}")
        return {}

    def _get_sqlite_path(self) -> Optional[str]:
        """Check if a local SQLite file exists for this db_name."""
        db_lower = self.db_name.lower()

        # Check 1: flat file
        path1 = os.path.join("resources", "databases", "sqlite", f"{db_lower}.sqlite")
        if os.path.exists(path1):
            return path1

        # Check 2: recursive search inside named folder
        db_dir = os.path.join("resources", "databases", "sqlite", db_lower)
        if os.path.isdir(db_dir):
            matches = glob.glob(os.path.join(db_dir, "**", "*.sqlite"), recursive=True)
            if matches:
                return matches[0]

        return None

    def execute(self, sql: str, instance_id: str) -> Tuple[bool, str, int]:
        """Execute SQL and persist results to results/{db_name}/{instance_id}.csv"""
        save_dir = os.path.join("results", self.db_name)
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, f"{instance_id}.csv")

        # Clear stale results immediately
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except Exception as e:
                logger.warning(f"Could not remove stale CSV {csv_path}: {e}")

        # Prefer SQLite if a local file is available
        sqlite_path = self._get_sqlite_path()
        if sqlite_path:
            rows, columns, error = self._execute_sqlite(sql, sqlite_path)
        else:
            rows, columns, error = self._execute_snowflake(sql)

        if error:
            return False, error, 0

        # Persist to CSV
        df = pd.DataFrame(rows)
        if df.empty and columns:
            df = pd.DataFrame(columns=columns)
            
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.success(f"Results saved -> {csv_path} ({len(df)} rows)")

        return True, "Execution successful.", len(df)

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _execute_sqlite(self, sql: str, path: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        import sqlite3
        logger.info(f"Executing on SQLite ({path})")
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql)
            columns = [col[0] for col in cur.description] if cur.description else []
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows, columns, None
        except Exception as e:
            logger.error(f"SQLite error: {e}")
            return [], [], str(e)

    def _execute_snowflake(self, sql: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        if not self.sf_config:
            return [], [], "Snowflake configuration missing (config/sf_credentials.json)"

        logger.info(f"Executing on Snowflake | db={self.db_name}")
        try:
            import snowflake.connector
            conn_params = {**self.sf_config, "database": self.db_name}
            ctx = snowflake.connector.connect(**conn_params)
            cs = ctx.cursor()
            try:
                cs.execute(sql)
                columns = [col[0] for col in cs.description] if cs.description else []
                rows = [dict(zip(columns, row)) for row in cs.fetchall()]
                return rows, columns, None
            finally:
                cs.close()
                ctx.close()
        except Exception as e:
            logger.error(f"Snowflake error: {e}")
            return [], [], str(e)
