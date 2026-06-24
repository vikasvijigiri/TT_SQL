import typing

import os

import json

import glob

import yaml

import pandas as pd

import threading

from typing import Tuple, List, Dict, Any, Optional

from agent.services.logger import logger

from agent.app.core.config import DATABASES_DIR, CONFIG_DIR, get_active_results_dir

from agent.app.core.connection import parse_connection, ConnectionConfig

from agent.blackboard.dynamic_rules import FailureMemory

from agent.validators.deterministic_validators import DeterministicValidators

import contextlib





def _load_homogeneous_threshold(default: int = 8) -> int:

    """Read homogeneous_threshold from system_params.yaml; fall back to *default*."""

    try:

        params_path = CONFIG_DIR.parent / "config" / "system_params.yaml"

        with open(params_path, "r", encoding="utf-8") as f:

            params = yaml.safe_load(f) or {}

        return int(params.get("schema_engine", {}).get("homogeneous_threshold", default))

    except Exception:

        return default



# Thread-safe global cache for DuckDB homogeneous groups to optimize schema introspection

_DUCKDB_HOMOGENEOUS_GROUPS_CACHE: dict[str, typing.Any] = {}

_DUCKDB_CACHE_LOCK = threading.Lock()



# Thread-safe global cache for DuckDB connections to avoid re-compiling union views per query/thread  # type: ignore

_DUCKDB_CONNECTIONS_CACHE = {}

_DUCKDB_CONN_LOCK = threading.Lock()





def is_sqlite_file(filepath: str) -> bool:

    try:

        if not os.path.exists(filepath) or os.path.isdir(filepath):

            return False

        with open(filepath, "rb") as f:

            header = f.read(16)

            return header.startswith(b"SQLite format 3\x00")

    except Exception:

        return False





class DatabaseExecutor:

    @property

    def _conn(self):

        if not hasattr(self, "_local"):

            self._local = threading.local()

        if not hasattr(self._local, "conn"):

            self._local.conn = None

        return self._local.conn



    @_conn.setter

    def _conn(self, val):

        if not hasattr(self, "_local"):

            self._local = threading.local()

        self._local.conn = val



    @property

    def _conn_type(self):

        if not hasattr(self, "_local"):

            self._local = threading.local()

        if not hasattr(self._local, "conn_type"):

            self._local.conn_type = None

        return self._local.conn_type



    @_conn_type.setter

    def _conn_type(self, val):

        if not hasattr(self, "_local"):

            self._local = threading.local()

        self._local.conn_type = val



    def __init__(

        self,

        db_name: str = "",

        dialect: str = "snowflake",

        sf_config_path: str | None = None,

        explicit_db_path: str | None = None,

        connection_string: str | None = None,

    ):

        self._local = threading.local()

        if sf_config_path is None:

            sf_config_path = str(CONFIG_DIR / "sf_credentials.json")



        # If a full connection URI is provided, derive dialect + db_name from it

        self._conn_cfg: Optional[ConnectionConfig] = None

        if connection_string:

            self._conn_cfg = parse_connection(connection_string)

            dialect = self._conn_cfg.dialect

            db_name = self._conn_cfg.db_name or db_name



        self.dialect = dialect

        self.db_name = (db_name or "UNKNOWN").upper()

        self.sf_config = self._load_sf_config(sf_config_path)

        self._conn = None

        self._conn_type = None

        # Optional: explicit path to a DB file (used by DAB multi-DB datasets)

        self.explicit_db_path: Optional[str] = explicit_db_path or (

            self._conn_cfg.path if self._conn_cfg else None

        )



    def _load_sf_config(self, path: str) -> Dict[str, Any]:

        if os.path.exists(path):

            with open(path, "r") as f:

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

            from agent.app.core.config import DAB_REPO as _DAB_REPO



            dab_env = str(_DAB_REPO / ".env")

            if os.path.exists(dab_env):

                load_dotenv(dab_env)



            if os.getenv("PG_HOST") or os.getenv("PG_PORT") or os.getenv("PG_USER"):

                pg_cfg = {

                    "host": os.getenv("PG_HOST", "127.0.0.1"),

                    "port": int(os.getenv("PG_PORT", 5432)),

                    "user": os.getenv("PG_USER", "postgres"),

                    "password": os.getenv("PG_PASSWORD", "dabpass"),

                    "dbname": os.getenv("PG_DB")

                    or os.getenv("PG_DATABASE")

                    or self.db_name.lower(),

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

        used instead -- callers must check _needs_sqlalchemy() in that case.

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

                # Generic dialects (MySQL, MSSQL, BigQuery, Oracle, ') --

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



    def execute(self, sql: str, instance_id: str, timeout: int | None = None) -> Tuple[bool, str, int]:

        """Execute SQL (handles multi-statements) and persist results."""

        save_dir = os.path.join(str(get_active_results_dir()), self.db_name)

        os.makedirs(save_dir, exist_ok=True)

        csv_path = os.path.join(save_dir, f"{instance_id}.csv")



        # Multi-statement support

        statements = [s.strip() for s in sql.split(";") if s.strip()]

        if not statements:

            return False, "No SQL statements provided.", 0



        last_rows, last_cols, _last_error = [], [], None



        # ---- Backend selection ----

        sqlite_path, duckdb_path, pg_conn_str = self._resolve_paths()



        for stmt in statements:

            # Deterministic Execution Safety Validation

            val_result = DeterministicValidators.validate_execution_safety(stmt)

            if not val_result.is_valid:

                FailureMemory.record_failure(

                    failure_type="Validation Rejection (Execution Safety)",

                    root_cause=val_result.rejection_reason or "Unknown",

                    impact="Dangerous execution blocked.",

                    prevention_rule=f"Refactor SQL to avoid: {val_result.rejection_reason}"

                )

                return False, f"Execution Safety Validation Failed: {val_result.rejection_reason}", 0



            if sqlite_path:

                preflight_error = self._preflight_sqlite_statement(stmt)

                if preflight_error:

                    logger.error(f"SQLite preflight failed: {preflight_error}")

                    return False, preflight_error, 0

            if sqlite_path:

                rows, columns, error = self._execute_sqlite(stmt, sqlite_path, timeout=timeout)

            elif duckdb_path:

                rows, columns, error = self._execute_duckdb(stmt, duckdb_path, timeout=timeout)

            elif pg_conn_str:

                rows, columns, error = self._execute_postgres(stmt, pg_conn_str)

            elif self._needs_sqlalchemy():

                rows, columns, error = self._execute_via_sqlalchemy(  # type: ignore

                    stmt, self._conn_cfg.raw_uri

                )

            elif (self.dialect or "").lower() == "snowflake":

                rows, columns, error = self._execute_snowflake(stmt)

            else:

                # No execution backend resolved for this dialect. Return a clear error

                # instead of silently falling back to a vendor-specific executor.

                _d = self.dialect or "unknown"

                error = (

                    f"No execution backend resolved for dialect '{_d}'. "

                    f"Provide a connection string, a local db file path, or configure the appropriate backend."

                )

                rows, columns = [], []



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

                preview_df[col] = preview_df[col].apply(

                    lambda x: (

                        "" if (x is None or (not isinstance(x, (list, dict, set, tuple)) and pd.isna(x)))

                        else (

                            str(x).replace("\n", " ").replace("\r", " ")[:100] + "..."

                            if len(str(x)) > 100

                            else str(x).replace("\n", " ").replace("\r", " ")

                        )

                    )

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

            nested_windows = [

                candidate

                for candidate in window_node.find_all(exp.Window)

                if candidate is not window_node

            ]

            if nested_windows:

                return (

                    "SQLite preflight rejected nested window expressions. "

                    "Rewrite the query so each window function is computed in its own CTE or subquery, "

                    "then referenced by the outer query."

                )



        return None



    def explain_validate(self, sql: str) -> Optional[Dict]:

        """

        Run ``EXPLAIN QUERY PLAN`` on SQLite (dialect-guarded) and return a

        structured plan dict with any performance warnings.



        Returns ``None`` for non-SQLite dialects.  Never raises.



        The caller can use ``warnings`` to detect full-table scans on large

        tables, which is a signal that a JOIN condition may be missing or that

        an index would help.



        Shape::



            {

                "plan": [{"id": 1, "parent": 0, "detail": "SCAN TABLE player"}],

                "warnings": ["Full scan: player - consider adding an index or filter"],

                "success": True,

            }

        """

        sqlite_path, _, _ = self._resolve_paths()

        if not sqlite_path:

            return None  # only supported for SQLite



        try:

            import sqlite3



            conn = sqlite3.connect(sqlite_path, timeout=5)

            cursor = conn.cursor()

            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")

            rows = cursor.fetchall()

            conn.close()

        except Exception as exc:

            return {"plan": [], "warnings": [], "success": False, "error": str(exc)[:300]}



        plan = [

            {"id": r[0], "parent": r[1], "detail": r[3] if len(r) > 3 else str(r)}

            for r in rows

        ]

        warnings: List[str] = []

        for entry in plan:

            detail = entry.get("detail", "")

            # A bare SCAN TABLE without USING INDEX on a JOIN is often expensive

            if "SCAN TABLE" in detail and "USING INDEX" not in detail and "USING ROWID" not in detail:

                table_name = detail.replace("SCAN TABLE", "").split()[0] if "SCAN TABLE" in detail else "?"

                warnings.append(

                    f"Full scan: {table_name} - consider adding an index or a WHERE/JOIN filter"

                )



        return {"plan": plan, "warnings": warnings, "success": True}



    def execute_direct(self, sql: str, timeout: int | None = None) -> Tuple[bool, str, List[Dict[str, Any]]]:

        """Executes a query directly and returns the raw rows without persisting to CSV."""

        sql = sql.strip().rstrip(";")

        sqlite_path, duckdb_path, pg_conn_str = self._resolve_paths()



        if sqlite_path:

            rows, columns, error = self._execute_sqlite(sql, sqlite_path, timeout=timeout)

        elif duckdb_path:

            rows, columns, error = self._execute_duckdb(sql, duckdb_path, timeout=timeout)

        elif pg_conn_str:

            rows, columns, error = self._execute_postgres(sql, pg_conn_str)

        elif self._needs_sqlalchemy():

            rows, columns, error = self._execute_via_sqlalchemy(  # type: ignore

                sql, self._conn_cfg.raw_uri

            )

        elif (self.dialect or "").lower() == "snowflake":

            rows, _columns, error = self._execute_snowflake(sql)

        else:

            _d = self.dialect or "unknown"

            error = (

                f"No execution backend resolved for dialect '{_d}'. "

                f"Provide a connection string, a local db file path, or configure the appropriate backend."

            )

            rows = []

        if error:

            return False, error, []

        return True, "Success", rows



    def _seed_sqlite_indexes(self, conn, cur):

        """

        Seed indexes on key join columns dynamically based on SQLite schema constraints

        and shared column names across tables. Completely avoids hardcoded string patterns.

        """

        try:

            # 1. Get list of all databases (main + attached)

            cur.execute("PRAGMA database_list;")

            dbs = [r[1] for r in cur.fetchall() if r[1] not in ("temp",)]



            all_dbs_tables = []

            col_counts = {}  # col_name.lower() -> count of tables containing it

            table_cols_map = {}  # (db, table) -> list of column names



            # 2. Collect column names across all tables in all databases

            for db_alias in dbs:

                prefix = f'"{db_alias}".' if db_alias != "main" else ""

                try:

                    cur.execute(f"SELECT name FROM {prefix}sqlite_master WHERE type='table';")

                    tables = [r[0] for r in cur.fetchall() if r[0] not in ("sqlite_sequence", "sqlite_stat1")]

                except Exception:

                    continue



                for t_name in tables:

                    try:

                        cur.execute(f"PRAGMA {prefix}table_info(\"{t_name}\");")

                        cols_info = cur.fetchall()

                    except Exception:

                        continue

                    

                    columns = []

                    for col in cols_info:

                        try:

                            cname = col["name"]

                        except (IndexError, KeyError, TypeError):

                            cname = col[1] if len(col) > 1 else None

                        if cname:

                            columns.append(cname)

                            col_lower = cname.lower()

                            col_counts[col_lower] = col_counts.get(col_lower, 0) + 1

                    

                    table_cols_map[(db_alias, t_name)] = columns

                    all_dbs_tables.append((db_alias, t_name))



            # 3. Create indexes on columns that are either:

            #    a) Explicit foreign keys

            #    b) Shared column names across 2 or more tables (candidate join keys)

            for db_alias, t_name in all_dbs_tables:

                prefix = f'"{db_alias}".' if db_alias != "main" else ""

                

                # Fetch constraints for this table

                fk_cols = set()

                try:

                    cur.execute(f"PRAGMA {prefix}foreign_key_list(\"{t_name}\");")

                    fks = cur.fetchall()

                    for fk in fks:

                        try:

                            fk_from = fk["from"]

                        except (IndexError, KeyError, TypeError):

                            fk_from = fk[3] if len(fk) > 3 else None

                        if fk_from:

                            fk_cols.add(fk_from.lower())

                except Exception:

                    pass



                # Get existing index columns to avoid duplicates

                indexed_cols = set()

                try:

                    cur.execute(f"PRAGMA {prefix}index_list(\"{t_name}\");")

                    existing_indexes = cur.fetchall()

                    for idx in existing_indexes:

                        try:

                            idx_name = idx["name"]

                        except (IndexError, KeyError, TypeError):

                            idx_name = idx[1] if len(idx) > 1 else None

                        

                        if idx_name:

                            try:

                                cur.execute(f"PRAGMA {prefix}index_info(\"{idx_name}\");")

                                for idx_col in cur.fetchall():

                                    try:

                                        cname = idx_col["name"]

                                    except (IndexError, KeyError, TypeError):

                                        cname = idx_col[2] if len(idx_col) > 2 else None

                                    if cname:

                                        indexed_cols.add(cname.lower())

                            except Exception:

                                pass

                except Exception:

                    pass



                columns = table_cols_map.get((db_alias, t_name), [])

                for col in columns:

                    col_lower = col.lower()

                    

                    # Decide if this column needs an index

                    is_fk = col_lower in fk_cols

                    is_shared = col_counts.get(col_lower, 0) >= 2

                    

                    if (is_fk or is_shared) and col_lower not in indexed_cols:

                        idx_name = f"idx_dyn_{t_name}_{col_lower}"

                        idx_name = idx_name[:60]

                        try:

                            create_sql = f"CREATE INDEX IF NOT EXISTS {prefix}\"{idx_name}\" ON \"{t_name}\" (\"{col}\");"

                            cur.execute(create_sql)

                            logger.info(f"[IndexSeeding] Created dynamic index on {db_alias}.{t_name}.{col}")

                        except Exception as ie:

                            logger.debug(f"[IndexSeeding] Could not create index on {db_alias}.{t_name}.{col}: {ie}")

            conn.commit()

        except Exception as e:

            import traceback

            logger.warning(f"[IndexSeeding] SQLite dynamic index seeding failed: {e}\n{traceback.format_exc()}")



    def _execute_sqlite(

        self, sql: str, path: str, timeout: int | None = None

    ) -> Tuple[List[Dict], List[str], Optional[str]]:

        import sqlite3

        import glob

        import time



        logger.info(f"Executing on SQLite ({path})")

        try:

            if self._conn is None or self._conn_type != "sqlite":

                self.close()  # type: ignore

                self._conn = sqlite3.connect(path)  # type: ignore

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

  # type: ignore

                self._conn.create_function("REGEXP", 2, regexp)  # type: ignore

                self._conn.create_function(

                    "regexp_extract",

                    2,

                    lambda item, pattern: regexp_extract(item, pattern, 0),

                )  # type: ignore

                self._conn.create_function("regexp_extract", 3, regexp_extract)

  # type: ignore

                self._conn.row_factory = sqlite3.Row  # type: ignore

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

                        # Use IF NOT EXISTS to survive re-attaches across sessions

                        # (DuckDB persists ATTACH to catalog on disk).

                        cur.execute(

                            f"ATTACH '{sqlite_file}' AS \"{alias}\";"

                        )

                        attached_db_names.append((alias, sqlite_file))

                    except Exception as e:

                        logger.warning(

                            f"Failed to auto-attach SQLite DB {sqlite_file}: {e}"

                        )



                # Create temporary views for tables in attached databases

                for alias, _filepath in attached_db_names:

                    try:

                        cur.execute(

                            f"SELECT name FROM {alias}.sqlite_master WHERE type='table';"

                        )

                        table_names = [

                            r[0]

                            for r in cur.fetchall()

                            if r[0] not in ("sqlite_sequence", "sqlite_stat1")

                        ]

                        for t_name in table_names:

                            cur.execute(

                                f'CREATE TEMP VIEW "{t_name}" AS SELECT * FROM "{alias}"."{t_name}";'

                            )

                            logger.info(

                                f"Auto-created temporary view for SQLite table: {t_name}"

                            )

                    except Exception as e:

                        logger.warning(

                            f"Failed to create views for attached SQLite DB {alias}: {e}"

                        )

                cur.close()



                # Seed SQLite indexes on key columns

                try:

                    self._seed_sqlite_indexes(self._conn, self._conn.cursor())

                except Exception as _se:

                    logger.debug(f"[IndexSeeding] SQLite index seeding setup failed: {_se}")



            # Execute statement

            conn = self._conn

            timeout_seconds = timeout if timeout is not None else 120

            start_time = time.time()



            def progress_handler():

                if time.time() - start_time > timeout_seconds:

                    return 1

                return 0

  # type: ignore

            conn.set_progress_handler(progress_handler, 1000)  # type: ignore

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



    def _execute_duckdb(

        self, sql: str, path: str, timeout: int | None = None

    ) -> Tuple[List[Dict], List[str], Optional[str]]:

        """Execute SQL against a DuckDB file."""

        logger.info(f"Executing on DuckDB ({path})")

        try:

            import duckdb

            import glob



            if self._conn is None or self._conn_type != "duckdb":

                self.close()



                thread_id = threading.get_ident()

                cache_key = (thread_id, path)



                with _DUCKDB_CONN_LOCK:

                    if cache_key in _DUCKDB_CONNECTIONS_CACHE:

                        conn = _DUCKDB_CONNECTIONS_CACHE[cache_key]

                    else:

                        conn = duckdb.connect(path, read_only=True)

                        with contextlib.suppress(Exception):

                            conn.execute("SET memory_limit = '500MB';")



                        db_dir = os.path.dirname(path)

                        current_abs_path = os.path.abspath(path)



                        # -- Attach sibling SQLite files ----------------------------------

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

                            alias = (

                                os.path.splitext(os.path.basename(sqlite_file))[0]

                                + "_db"

                            )

                            try:

                                if not sqlite_ext_loaded:

                                    conn.execute("INSTALL sqlite;")

                                    conn.execute("LOAD sqlite;")

                                    sqlite_ext_loaded = True

                                sqlite_file_fs = sqlite_file.replace("\\", "/")

                                conn.execute(

                                    f"ATTACH IF NOT EXISTS '{sqlite_file_fs}' AS \"{alias}\" (TYPE sqlite);"

                                )

                                attached_sqlite_names.append((alias, sqlite_file))

                            except Exception as e:

                                logger.warning(

                                    f"Failed to auto-attach SQLite DB {os.path.basename(sqlite_file)}: {e}"

                                )



                        # -- Attach sibling DuckDB files -----------------------------------

                        duckdb_files = []

                        for ext in ("*.duckdb", "*.ddb"):

                            duckdb_files.extend(glob.glob(os.path.join(db_dir, ext)))

                        duckdb_files = list(set(duckdb_files))



                        attached_duckdb_names = []

                        for ddb_file in duckdb_files:

                            if os.path.abspath(ddb_file) == current_abs_path:

                                continue

                            alias = (

                                os.path.splitext(os.path.basename(ddb_file))[0] + "_db"

                            )

                            try:

                                ddb_file_fs = ddb_file.replace("\\", "/")

                                conn.execute(

                                    f"ATTACH IF NOT EXISTS '{ddb_file_fs}' AS \"{alias}\" (READ_ONLY);"

                                )

                                attached_duckdb_names.append((alias, ddb_file))

                            except Exception as e:

                                logger.warning(

                                    f"Failed to auto-attach DuckDB file {os.path.basename(ddb_file)}: {e}"

                                )



                        # -- Create temp views for all attached databases ------------------

                        all_attached = attached_sqlite_names + attached_duckdb_names

                        attached_view_names: set = set()

                        if all_attached:

                            try:

                                all_tables = conn.execute("SHOW ALL TABLES;").fetchall()

                                attached_aliases = {alias for alias, _ in all_attached}

                                for row in all_tables:

                                    db_alias = row[0]

                                    if db_alias not in attached_aliases:

                                        continue

                                    t_name = row[2]

                                    try:

                                        conn.execute(

                                            f'CREATE OR REPLACE TEMPORARY TABLE "{t_name}" AS '

                                            f'SELECT * FROM "{db_alias}"."{t_name}";'

                                        )

                                        attached_view_names.add(t_name)

                                        logger.info(

                                            f"Auto-created temp table '{t_name}' from attached DB '{db_alias}'"

                                        )

                                    except Exception as ve:

                                        logger.warning(

                                            f"Failed to create table for '{t_name}' from '{db_alias}': {ve}"

                                        )

                            except Exception as e:

                                logger.warning(

                                    f"Failed to enumerate attached tables: {e}"

                                )



                        # -- Auto-create unified TEMP VIEWs for homogeneous table groups ------

                        HOMOGENEOUS_THRESHOLD = _load_homogeneous_threshold()

                        try:

                            db_basename = os.path.splitext(os.path.basename(path))[0]



                            with _DUCKDB_CACHE_LOCK:

                                sorted_groups = _DUCKDB_HOMOGENEOUS_GROUPS_CACHE.get(

                                    path

                                )



                            if sorted_groups is None:

                                cursor = conn.execute("SHOW TABLES;")

                                all_table_names = [

                                    r[0]

                                    for r in cursor.fetchall()

                                    if r[0] not in attached_view_names

                                ]

                                schema_groups: dict = {}

                                for t_name in all_table_names:

                                    try:

                                        cols = conn.execute(

                                            f"PRAGMA table_info('{t_name}');"

                                        ).fetchall()

                                        sig = "|".join(

                                            sorted(c[1].lower() for c in cols)

                                        )

                                        schema_groups.setdefault(sig, []).append(t_name)

                                    except Exception:

                                        pass

                                sorted_groups = sorted(

                                    [

                                        g

                                        for g in schema_groups.values()

                                        if len(g) >= HOMOGENEOUS_THRESHOLD

                                    ],

                                    key=len,

                                    reverse=True,

                                )

                                with _DUCKDB_CACHE_LOCK:

                                    _DUCKDB_HOMOGENEOUS_GROUPS_CACHE[path] = (

                                        sorted_groups

                                    )



                            for idx, group in enumerate(sorted_groups):

                                unified_view = (

                                    f"all_{db_basename}"

                                    if idx == 0

                                    else f"all_{db_basename}_{idx + 1}"

                                )

                                try:

                                    union_parts = [

                                        f"SELECT '{t}' AS _entity_name, * FROM \"{t}\""

                                        for t in group

                                    ]

                                    union_sql = " UNION ALL ".join(union_parts)

                                    conn.execute(

                                        f'CREATE OR REPLACE TEMPORARY VIEW "{unified_view}" AS {union_sql};'

                                    )

                                    logger.info(

                                        f"Auto-created unified view '{unified_view}' for {len(group)} homogeneous tables"

                                    )

                                except Exception as ve:

                                    logger.warning(

                                        f"Failed to create unified view '{unified_view}': {ve}"

                                    )

                        except Exception as e:

                            logger.warning(f"Homogeneous table detection failed: {e}")



                        _DUCKDB_CONNECTIONS_CACHE[cache_key] = conn



                self._conn = conn  # type: ignore

                self._conn_type = "duckdb"



            conn = self._conn  # type: ignore



            # -- Execute with automatic 'Did you mean X.Y?' recovery ----------

            # DuckDB Catalog Errors often include a suggestion of the correct

            # alias.table form. We parse it and retry ONCE - no hardcoding.

            import duckdb as _ddb



            def _run(query: str):

                rel = conn.execute(query)

                cols = [desc[0] for desc in rel.description] if rel.description else []

                rws  = [dict(zip(cols, row, strict=False)) for row in rel.fetchall()]

                return rws, cols



            # Hard 60-second timeout for DuckDB execution.

            # DuckDB's Python API blocks the calling thread with no built-in timeout.

            # We run the query in a daemon thread; on expiry we call conn.interrupt()

            # which signals DuckDB's C++ engine to abort the running query, allowing

            # the thread to unblock and terminate cleanly.

            _DUCKDB_EXEC_TIMEOUT = timeout if timeout is not None else 60

            _result_holder: list = [None]

            _error_holder:  list = [None]



            def _run_in_thread():

                try:

                    _result_holder[0] = _run(sql)

                except Exception as _te:

                    _error_holder[0] = str(_te)



            _exec_thread = threading.Thread(target=_run_in_thread, daemon=True)

            _exec_thread.start()

            _exec_thread.join(timeout=_DUCKDB_EXEC_TIMEOUT)



            if _exec_thread.is_alive():

                with contextlib.suppress(Exception):

                    conn.interrupt()  # ask DuckDB to abort the running query

                _exec_thread.join(5)  # brief grace period for clean unblock

                logger.error(f"DuckDB query timeout after {_DUCKDB_EXEC_TIMEOUT}s - query cancelled")

                return [], [], f"DuckDB query timeout after {_DUCKDB_EXEC_TIMEOUT}s - query was cancelled. Simplify the SQL (avoid recursive CTEs, reduce joins)."



            if _error_holder[0]:

                err_str = _error_holder[0]

                logger.error(f"DuckDB error: {err_str}")

                return [], [], err_str



            rows, columns = _result_holder[0]



            try:

                pass  # placeholder so the except below still catches ImportError/Exception

            except (_ddb.CatalogException, _ddb.BinderException, Exception) as _exec_err:

                err_str = str(_exec_err)

                logger.error(f"DuckDB error: {_exec_err}")

                return [], [], err_str



            with contextlib.suppress(Exception):  # type: ignore

                conn.execute("PRAGMA shrink();")



            return rows, columns, None

        except ImportError:

            return [], [], "duckdb package not installed. Run: pip install duckdb"

        except Exception as e:

            logger.error(f"DuckDB error: {e}")

            return [], [], str(e)



    def _execute_postgres(

        self, sql: str, conn_str: str

    ) -> Tuple[List[Dict], List[str], Optional[str]]:

        """Execute SQL against a PostgreSQL database."""

        logger.info("Executing on PostgreSQL")

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

            return (

                [],

                [],

                "psycopg2 package not installed. Run: pip install psycopg2-binary",

            )

        except Exception as e:

            logger.error(f"PostgreSQL error: {e}")

            return [], [], str(e)



    def _execute_snowflake(

        self, sql: str

    ) -> Tuple[List[Dict], List[str], Optional[str]]:

        if not self.sf_config:

            return (

                [],

                [],

                "Snowflake configuration missing (config/sf_credentials.json)",

            )



        logger.info(f"Executing on Snowflake | db={self.db_name}")

        try:

            import snowflake.connector



            if self._conn is None:

                conn_params = {**self.sf_config, "database": self.db_name}  # type: ignore

                self._conn = snowflake.connector.connect(**conn_params)

  # type: ignore

            cs = self._conn.cursor()

            try:

                # Set session timeout to 300s (5 minutes) for heavy spatial/analytical queries

                cs.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 300")

                cs.execute(sql)

                columns = [col[0] for col in cs.description] if cs.description else []

                rows = [dict(zip(columns, row, strict=False)) for row in cs.fetchall()]

                return rows, columns, None

            finally:

                cs.close()

        except Exception as e:

            logger.error(f"Snowflake error: {e}")

            if self._conn:

                with contextlib.suppress(BaseException):

                    self._conn.close()

                self._conn = None

            return [], [], str(e)



    def _execute_via_sqlalchemy(

        self, sql: str, uri: str

    ) -> Tuple[List[Dict], List[str], Optional[str]]:

        """

        Generic execution backend for any SQLAlchemy-supported database.



        This covers MySQL, MariaDB, MSSQL, BigQuery, Oracle, Trino, Redshift,

        Spark, and any future DBMS -- no code changes required, just install

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

                    rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

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

            if self._conn_type == "duckdb":

                # Do not close cached shared DuckDB connections

                pass

            else:

                try:

                    self._conn.close()

                except Exception as e:

                    logger.warning(f"Error closing connection: {e}")

            self._conn = None

            self._conn_type = None



    def __del__(self):

        self.close()

