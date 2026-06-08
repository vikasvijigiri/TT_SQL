import os
import json
import glob
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional
from backend.app.utils.logger import logger
from backend.app.core.config import DATABASES_DIR, CONFIG_DIR, RESULTS_DIR, get_db_path
from backend.app.core.connection import parse_connection, ConnectionConfig

def is_sqlite_file(filepath: str) -> bool:
    try:
        if not os.path.exists(filepath) or os.path.isdir(filepath):
            return False
        with open(filepath, 'rb') as f:
            header = f.read(16)
            return header.startswith(b'SQLite format 3\x00')
    except Exception:
        return False


class DatabaseExecutor:
    def __init__(self, db_name: str = "", dialect: str = "snowflake",
                 sf_config_path: str = None,
                 explicit_db_path: str = None,
                 connection_string: str = None):
        if sf_config_path is None:
            sf_config_path = str(CONFIG_DIR / "sf_credentials.json")

        # If a full connection URI is provided, derive dialect + db_name from it
        self._conn_cfg: Optional[ConnectionConfig] = None
        if connection_string:
            self._conn_cfg = parse_connection(connection_string)
            dialect  = self._conn_cfg.dialect
            db_name  = self._conn_cfg.db_name or db_name

        self.dialect = dialect
        self.db_name = (db_name or "UNKNOWN").upper()
        self.sf_config = self._load_sf_config(sf_config_path)
        self._conn = None
        self._conn_type = None
        # Optional: explicit path to a DB file (used by DAB multi-DB datasets)
        self.explicit_db_path: Optional[str] = (
            explicit_db_path or (self._conn_cfg.path if self._conn_cfg else None)
        )

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

    def _get_duckdb_path(self) -> Optional[str]:
        """Check if a local DuckDB file exists for this db_name."""
        if self.explicit_db_path and self.explicit_db_path.endswith(".duckdb"):
            if os.path.exists(self.explicit_db_path):
                return self.explicit_db_path
        db_lower = self.db_name.lower()

        # Check 1: flat file
        path1 = os.path.join(str(DATABASES_DIR), "duckdb", f"{db_lower}.duckdb")
        if os.path.exists(path1):
            return path1

        # Check 2: recursive search inside named folder
        db_dir = os.path.join(str(DATABASES_DIR), "duckdb", db_lower)
        if os.path.isdir(db_dir):
            matches = glob.glob(os.path.join(db_dir, "**", "*.duckdb"), recursive=True)
            if matches:
                return matches[0]

        return None

    def _get_postgres_conn_str(self) -> Optional[str]:
        """Return a PostgreSQL connection string if configured."""
        # Check sf_config for postgres credentials
        pg_cfg = self.sf_config.get("postgres", {})
        if not pg_cfg:
            # Fallback to environment variables
            from dotenv import load_dotenv
            load_dotenv()
            # Also try loading from DataAgentBench/.env if it exists
            from backend.app.core.config import DAB_REPO as _DAB_REPO
            dab_env = str(_DAB_REPO / ".env")
            if os.path.exists(dab_env):
                load_dotenv(dab_env)
            
            if os.getenv("PG_HOST") or os.getenv("PG_PORT") or os.getenv("PG_USER"):
                pg_cfg = {
                    "host": os.getenv("PG_HOST", "127.0.0.1"),
                    "port": int(os.getenv("PG_PORT", 5432)),
                    "user": os.getenv("PG_USER", "postgres"),
                    "password": os.getenv("PG_PASSWORD", "dabpass"),
                    "dbname": os.getenv("PG_DB") or os.getenv("PG_DATABASE") or self.db_name.lower()
                }

        if pg_cfg:
            host = pg_cfg.get("host", "localhost")
            port = pg_cfg.get("port", 5432)
            user = pg_cfg.get("user", "postgres")
            password = pg_cfg.get("password", "postgres")
            dbname = pg_cfg.get("dbname", self.db_name.lower())
            return f"host={host} port={port} user={user} password={password} dbname={dbname}"
        return None

    def _resolve_paths(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Resolve database execution path: (sqlite_path, duckdb_path, pg_conn_str).

        Returns (None, None, None) when the generic SQLAlchemy backend should be
        used instead — callers must check _needs_sqlalchemy() in that case.
        """
        dialect_lower = (self.dialect or "").lower()
        sqlite_path = None
        duckdb_path = None
        pg_conn_str = None

        if self.explicit_db_path and os.path.exists(self.explicit_db_path):
            ep = self.explicit_db_path
            if dialect_lower == "duckdb":
                duckdb_path = ep
            elif dialect_lower == "sqlite":
                sqlite_path = ep
            elif dialect_lower in ("postgres", "postgresql"):
                pg_conn_str = self._get_postgres_conn_str()
            else:
                if ep.endswith(".duckdb"):
                    duckdb_path = ep
                elif ep.endswith(".sqlite") or ep.endswith(".db"):
                    sqlite_path = ep
        else:
            if dialect_lower == "duckdb":
                duckdb_path = self._get_duckdb_path()
            elif dialect_lower in ("postgres", "postgresql"):
                pg_conn_str = self._get_postgres_conn_str()
            elif dialect_lower == "sqlite":
                sqlite_path = self._get_sqlite_path()
            elif self._conn_cfg and self._conn_cfg.needs_sqlalchemy:
                # Generic dialects (MySQL, MSSQL, BigQuery, Oracle, …) —
                # callers detect this via _needs_sqlalchemy() and use
                # _execute_via_sqlalchemy() instead.
                pass
            else:
                # Auto-detect fallback: prefer SQLite, then DuckDB
                sqlite_path = self._get_sqlite_path()
                if not sqlite_path:
                    duckdb_path = self._get_duckdb_path()

        return sqlite_path, duckdb_path, pg_conn_str

    def _needs_sqlalchemy(self) -> bool:
        """True when neither a native backend nor a local file was resolved."""
        return bool(self._conn_cfg and self._conn_cfg.needs_sqlalchemy)

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

        # ---- Backend selection ----
        sqlite_path, duckdb_path, pg_conn_str = self._resolve_paths()

        for stmt in statements:
            if sqlite_path:
                preflight_error = self._preflight_sqlite_statement(stmt)
                if preflight_error:
                    logger.error(f"SQLite preflight failed: {preflight_error}")
                    return False, preflight_error, 0
            if sqlite_path:
                rows, columns, error = self._execute_sqlite(stmt, sqlite_path)
            elif duckdb_path:
                rows, columns, error = self._execute_duckdb(stmt, duckdb_path)
            elif pg_conn_str:
                rows, columns, error = self._execute_postgres(stmt, pg_conn_str)
            elif self._needs_sqlalchemy():
                rows, columns, error = self._execute_via_sqlalchemy(stmt, self._conn_cfg.raw_uri)
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
            preview_df = df.head(5).copy()
            for col in preview_df.columns:
                if preview_df[col].dtype == object:
                    preview_df[col] = preview_df[col].apply(
                        lambda x: str(x)[:100] + "..." if isinstance(x, str) and len(x) > 100 else x
                    )
            logger.info(f"\n{preview_df.to_markdown(index=False)}")
        else:
            logger.warning("### Final Result: [EMPTY SET]")

        return True, "Execution successful.", len(df)

    def _preflight_sqlite_statement(self, sql: str) -> Optional[str]:
        """
        Catch common SQLite parse/structure issues before execution.

        This is intentionally generic: it rejects malformed SQL syntax and
        nested window expressions that SQLite cannot execute reliably.
        """
        try:
            import sqlglot
            from sqlglot import exp

            parsed = sqlglot.parse_one(sql, read="sqlite")
        except Exception as e:
            return f"SQLite preflight parse error: {e}"

        for window_node in parsed.find_all(exp.Window):
            nested_windows = [candidate for candidate in window_node.find_all(exp.Window) if candidate is not window_node]
            if nested_windows:
                return (
                    "SQLite preflight rejected nested window expressions. "
                    "Rewrite the query so each window function is computed in its own CTE or subquery, "
                    "then referenced by the outer query."
                )

        return None

    def execute_direct(self, sql: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Executes a query directly and returns the raw rows without persisting to CSV."""
        sqlite_path, duckdb_path, pg_conn_str = self._resolve_paths()

        if sqlite_path:
            rows, columns, error = self._execute_sqlite(sql, sqlite_path)
        elif duckdb_path:
            rows, columns, error = self._execute_duckdb(sql, duckdb_path)
        elif pg_conn_str:
            rows, columns, error = self._execute_postgres(sql, pg_conn_str)
        elif self._needs_sqlalchemy():
            rows, columns, error = self._execute_via_sqlalchemy(sql, self._conn_cfg.raw_uri)
        else:
            rows, columns, error = self._execute_snowflake(sql)
        if error:
            return False, error, []
        return True, "Success", rows

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _execute_sqlite(self, sql: str, path: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        import sqlite3
        import glob
        import time
        logger.info(f"Executing on SQLite ({path})")
        try:
            if self._conn is None or self._conn_type != "sqlite":
                self.close()
                self._conn = sqlite3.connect(path)
                self._conn_type = "sqlite"
                
                # Setup custom functions
                import re
                
                def regexp(expr, item):
                    if not expr or not item:
                        return False
                    try:
                        return re.search(expr, str(item)) is not None
                    except Exception:
                        return False
                        
                def regexp_extract(item, pattern, group=0):
                    if not item or not pattern:
                        return None
                    try:
                        m = re.search(pattern, str(item))
                        if m:
                            return m.group(group)
                    except Exception:
                        pass
                    return None

                self._conn.create_function("REGEXP", 2, regexp)
                self._conn.create_function("regexp_extract", 2, lambda item, pattern: regexp_extract(item, pattern, 0))
                self._conn.create_function("regexp_extract", 3, regexp_extract)
                
                self._conn.row_factory = sqlite3.Row
                cur = self._conn.cursor()
                
                # Auto-attach other SQLite databases in the same directory
                db_dir = os.path.dirname(path)
                sqlite_files = []
                for ext in ("*.sqlite", "*.db", "*.sqlite3"):
                    sqlite_files.extend(glob.glob(os.path.join(db_dir, ext)))
                sqlite_files = list(set(sqlite_files))
                
                current_abs_path = os.path.abspath(path)
                attached_db_names = []
                for sqlite_file in sqlite_files:
                    if os.path.abspath(sqlite_file) == current_abs_path:
                        continue
                    if not is_sqlite_file(sqlite_file):
                        continue
                    alias = os.path.splitext(os.path.basename(sqlite_file))[0] + "_db"
                    try:
                        cur.execute(f"ATTACH DATABASE '{sqlite_file}' AS \"{alias}\";")
                        attached_db_names.append((alias, sqlite_file))
                    except Exception as e:
                        logger.warning(f"Failed to auto-attach SQLite DB {sqlite_file}: {e}")
                        
                # Create temporary views for tables in attached databases
                for alias, filepath in attached_db_names:
                    try:
                        cur.execute(f"SELECT name FROM {alias}.sqlite_master WHERE type='table';")
                        table_names = [r[0] for r in cur.fetchall() if r[0] not in ("sqlite_sequence", "sqlite_stat1")]
                        for t_name in table_names:
                            cur.execute(f"CREATE TEMP VIEW \"{t_name}\" AS SELECT * FROM \"{alias}\".\"{t_name}\";")
                            logger.info(f"Auto-created temporary view for SQLite table: {t_name}")
                    except Exception as e:
                        logger.warning(f"Failed to create views for attached SQLite DB {alias}: {e}")
                    cur.close()

            # Execute statement
            conn = self._conn
            timeout_seconds = 120
            start_time = time.time()

            def progress_handler():
                if time.time() - start_time > timeout_seconds:
                    return 1
                return 0

            conn.set_progress_handler(progress_handler, 10000)
            cur = conn.cursor()
            cur.execute(sql)
            columns = [col[0] for col in cur.description] if cur.description else []
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows, columns, None
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e).lower():
                logger.error(f"SQLite timeout after {timeout_seconds}s")
                return [], [], f"SQLite execution timeout after {timeout_seconds}s"
            logger.error(f"SQLite error: {e}")
            return [], [], str(e)
        except Exception as e:
            logger.error(f"SQLite error: {e}")
            return [], [], str(e)

    def _execute_duckdb(self, sql: str, path: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        """Execute SQL against a DuckDB file."""
        logger.info(f"Executing on DuckDB ({path})")
        try:
            import duckdb
            import glob

            if self._conn is None or self._conn_type != "duckdb":
                self.close()
                conn = duckdb.connect(path, read_only=True)

                db_dir = os.path.dirname(path)
                current_abs_path = os.path.abspath(path)

                # ── Attach sibling SQLite files ──────────────────────────────────
                sqlite_files = []
                for ext in ("*.sqlite", "*.db", "*.sqlite3"):
                    sqlite_files.extend(glob.glob(os.path.join(db_dir, ext)))
                sqlite_files = list(set(sqlite_files))

                attached_sqlite_names = []
                sqlite_ext_loaded = False
                for sqlite_file in sqlite_files:
                    if os.path.abspath(sqlite_file) == current_abs_path:
                        continue
                    if not is_sqlite_file(sqlite_file):
                        continue
                    alias = os.path.splitext(os.path.basename(sqlite_file))[0] + "_db"
                    try:
                        if not sqlite_ext_loaded:
                            conn.execute("INSTALL sqlite;")
                            conn.execute("LOAD sqlite;")
                            sqlite_ext_loaded = True
                        sqlite_file_fs = sqlite_file.replace("\\", "/")
                        conn.execute(f"ATTACH '{sqlite_file_fs}' AS \"{alias}\" (TYPE sqlite);")
                        attached_sqlite_names.append((alias, sqlite_file))
                    except Exception as e:
                        logger.warning(f"Failed to auto-attach SQLite DB {os.path.basename(sqlite_file)}: {e}")

                # ── Attach sibling DuckDB files ───────────────────────────────────
                duckdb_files = []
                for ext in ("*.duckdb", "*.ddb"):
                    duckdb_files.extend(glob.glob(os.path.join(db_dir, ext)))
                duckdb_files = list(set(duckdb_files))

                attached_duckdb_names = []
                for ddb_file in duckdb_files:
                    if os.path.abspath(ddb_file) == current_abs_path:
                        continue
                    alias = os.path.splitext(os.path.basename(ddb_file))[0] + "_db"
                    try:
                        ddb_file_fs = ddb_file.replace("\\", "/")
                        conn.execute(f"ATTACH '{ddb_file_fs}' AS \"{alias}\" (READ_ONLY);")
                        attached_duckdb_names.append((alias, ddb_file))
                    except Exception as e:
                        logger.warning(f"Failed to auto-attach DuckDB file {os.path.basename(ddb_file)}: {e}")

                # ── Create temp views for all attached databases ──────────────────
                all_attached = attached_sqlite_names + attached_duckdb_names
                attached_view_names: set = set()
                if all_attached:
                    try:
                        all_tables = conn.execute("SHOW ALL TABLES;").fetchall()
                        # Map: database_name -> list of table names
                        attached_aliases = {alias for alias, _ in all_attached}
                        for row in all_tables:
                            db_alias = row[0]
                            if db_alias not in attached_aliases:
                                continue
                            t_name = row[2]
                            try:
                                conn.execute(
                                    f"CREATE OR REPLACE TEMPORARY VIEW \"{t_name}\" AS "
                                    f"SELECT * FROM \"{db_alias}\".\"{t_name}\";"
                                )
                                attached_view_names.add(t_name)
                                logger.info(f"Auto-created temp view '{t_name}' from attached DB '{db_alias}'")
                            except Exception as ve:
                                logger.warning(f"Failed to create view for '{t_name}' from '{db_alias}': {ve}")
                    except Exception as e:
                        logger.warning(f"Failed to enumerate attached tables: {e}")

                # ── Auto-create unified TEMP VIEWs for homogeneous table groups ──────
                HOMOGENEOUS_THRESHOLD = 8
                try:
                    cursor = conn.execute("SHOW TABLES;")
                    all_table_names = [r[0] for r in cursor.fetchall() if r[0] not in attached_view_names]
                    schema_groups: dict = {}
                    table_col_sigs: dict = {}
                    for t_name in all_table_names:
                        try:
                            cols = conn.execute(f"PRAGMA table_info('{t_name}');").fetchall()
                            sig = "|".join(sorted(c[1].lower() for c in cols))
                            schema_groups.setdefault(sig, []).append(t_name)
                            table_col_sigs[t_name] = (sig, cols)
                        except Exception:
                            pass
                    db_basename = os.path.splitext(os.path.basename(path))[0]
                    sorted_groups = sorted(
                        [g for g in schema_groups.values() if len(g) >= HOMOGENEOUS_THRESHOLD],
                        key=len,
                        reverse=True
                    )
                    for idx, group in enumerate(sorted_groups):
                        unified_view = f"all_{db_basename}" if idx == 0 else f"all_{db_basename}_{idx + 1}"
                        try:
                            union_parts = [
                                f"SELECT '{t}' AS _entity_name, * FROM \"{t}\""
                                for t in group
                            ]
                            union_sql = " UNION ALL ".join(union_parts)
                            conn.execute(f"CREATE OR REPLACE TEMPORARY VIEW \"{unified_view}\" AS {union_sql};")
                            logger.info(f"Auto-created unified view '{unified_view}' for {len(group)} homogeneous tables")
                        except Exception as ve:
                            logger.warning(f"Failed to create unified view '{unified_view}': {ve}")
                except Exception as e:
                    logger.warning(f"Homogeneous table detection failed: {e}")

                self._conn = conn
                self._conn_type = "duckdb"

            conn = self._conn
            rel = conn.execute(sql)
            columns = [desc[0] for desc in rel.description] if rel.description else []
            rows = [dict(zip(columns, row)) for row in rel.fetchall()]
            return rows, columns, None
        except ImportError:
            return [], [], "duckdb package not installed. Run: pip install duckdb"
        except Exception as e:
            logger.error(f"DuckDB error: {e}")
            return [], [], str(e)

    def _execute_postgres(self, sql: str, conn_str: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        """Execute SQL against a PostgreSQL database."""
        logger.info(f"Executing on PostgreSQL")
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(conn_str)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
            return rows, columns, None
        except ImportError:
            return [], [], "psycopg2 package not installed. Run: pip install psycopg2-binary"
        except Exception as e:
            logger.error(f"PostgreSQL error: {e}")
            return [], [], str(e)

    def _execute_snowflake(self, sql: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        if not self.sf_config:
            return [], [], "Snowflake configuration missing (config/sf_credentials.json)"

        logger.info(f"Executing on Snowflake | db={self.db_name}")
        try:
            import snowflake.connector
            if self._conn is None:
                conn_params = {**self.sf_config, "database": self.db_name}
                self._conn = snowflake.connector.connect(**conn_params)
            
            cs = self._conn.cursor()
            try:
                # Set session timeout to 300s (5 minutes) for heavy spatial/analytical queries
                cs.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 300")
                cs.execute(sql)
                columns = [col[0] for col in cs.description] if cs.description else []
                rows = [dict(zip(columns, row)) for row in cs.fetchall()]
                return rows, columns, None
            finally:
                cs.close()
        except Exception as e:
            logger.error(f"Snowflake error: {e}")
            if self._conn:
                try: self._conn.close()
                except: pass
                self._conn = None
            return [], [], str(e)

    def _execute_via_sqlalchemy(self, sql: str, uri: str) -> Tuple[List[Dict], List[str], Optional[str]]:
        """
        Generic execution backend for any SQLAlchemy-supported database.

        This covers MySQL, MariaDB, MSSQL, BigQuery, Oracle, Trino, Redshift,
        Spark, and any future DBMS — no code changes required, just install
        the appropriate SQLAlchemy dialect driver.

        The caller must have the relevant driver installed, e.g.:
          mysql:      pip install mysql-connector-python
          mssql:      pip install pyodbc
          bigquery:   pip install sqlalchemy-bigquery
          oracle:     pip install cx_Oracle  or  oracledb
          trino:      pip install trino[sqlalchemy]
        """
        logger.info(f"Executing on {self.dialect.upper()} via SQLAlchemy")
        try:
            from sqlalchemy import create_engine, text
        except ImportError:
            return [], [], "sqlalchemy not installed. Run: pip install sqlalchemy"

        try:
            engine = create_engine(uri, pool_pre_ping=True)
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                if result.returns_rows:
                    columns = list(result.keys())
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
                else:
                    columns, rows = [], []
            engine.dispose()
            return rows, columns, None
        except Exception as e:
            logger.error(f"SQLAlchemy ({self.dialect}) error: {e}")
            return [], [], str(e)

    def close(self):
        """Close persistent connection if open."""
        if hasattr(self, "_conn") and self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            self._conn = None
            self._conn_type = None

    def __del__(self):
        self.close()
