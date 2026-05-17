import os
import json
import glob
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional
from backend.app.utils.logger import logger
from backend.app.core.config import DATABASES_DIR, CONFIG_DIR, RESULTS_DIR, get_db_path

class DatabaseExecutor:
    def __init__(self, db_name: str, dialect: str = "snowflake",
                 sf_config_path: str = None):
        if sf_config_path is None:
            sf_config_path = str(CONFIG_DIR / "sf_credentials.json")
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
        path1 = os.path.join(str(DATABASES_DIR), "sqlite", f"{db_lower}.sqlite")
        if os.path.exists(path1):
            return path1

        # Check 2: recursive search inside named folder
        db_dir = os.path.join(str(DATABASES_DIR), "sqlite", db_lower)
        if os.path.isdir(db_dir):
            matches = glob.glob(os.path.join(db_dir, "**", "*.sqlite"), recursive=True)
            if matches:
                return matches[0]

        return None

    def execute(self, sql: str, instance_id: str) -> Tuple[bool, str, int]:
        """Execute SQL (handles multi-statements) and persist results."""
        save_dir = os.path.join(str(RESULTS_DIR), self.db_name)
        os.makedirs(save_dir, exist_ok=True)
        csv_path = os.path.join(save_dir, f"{instance_id}.csv")

        # Clear stale results
        if os.path.exists(csv_path):
            try: os.remove(csv_path)
            except: pass

        # Multi-statement support
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        if not statements:
            return False, "No SQL statements provided.", 0

        last_rows, last_cols, last_error = [], [], None
        
        # Prefer SQLite if available
        sqlite_path = self._get_sqlite_path()
        
        for stmt in statements:
            if sqlite_path:
                rows, columns, error = self._execute_sqlite(stmt, sqlite_path)
            else:
                rows, columns, error = self._execute_snowflake(stmt)
            
            if error:
                return False, error, 0
            
            last_rows, last_cols = rows, columns

        # Persist final statement results
        df = pd.DataFrame(last_rows)
        if df.empty and last_cols:
            df = pd.DataFrame(columns=last_cols)
            
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.success(f"Results saved -> {csv_path} ({len(df)} rows)")

        # Log final result preview (top 5 rows)
        if not df.empty:
            logger.info("### Final Result Preview (Top 5 Rows):")
            logger.info(f"\n{df.head(5).to_markdown(index=False)}")
        else:
            logger.warning("### Final Result: [EMPTY SET]")

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
                # Set session timeout to 300s (5 minutes) for heavy spatial/analytical queries
                cs.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 300")
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
