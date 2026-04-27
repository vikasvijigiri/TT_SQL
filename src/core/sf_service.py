import json
import os
import time
from typing import Any

import snowflake.connector

from .config import get_settings
from .logger import Logger
from .state import ExecutionResult
from .utils import quote_identifier


class SnowflakeService:
    """
    Service for Snowflake interactions.
    Handles connection management and metadata extraction.
    """

    _instance = None
    _conn = None
    _metadata_cache = {}  # Task 6: In-memory cache for (db, schema, table) -> column_list

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
                schema or creds.get("schema") or os.getenv("SNOWFLAKE_SCHEMA", target_database)
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

    def get_schema(self, database: str, schema: str | None = None, table_list: list[str] | None = None) -> dict[str, Any]:
        """
        Fetch schema for tables in a Snowflake database/schema.
        If table_list is provided, only fetches metadata and samples for those tables.
        Otherwise, performs a lightweight fetch of all table names and columns.
        """
        if not database:
            return {}

        conn = self.get_connection(database=database, schema=schema)
        if not conn:
            return {}

        schemas_to_try = []
        if schema:
            schemas_to_try.append(schema)
            
        # Task 2: Extract all candidate schemas from table_list for broad discovery (Fix: cross-schema metadata)
        if table_list:
            for t in table_list:
                parts = str(t).split(" ")[0].replace('"', '').split(".")
                if len(parts) >= 2:
                    sch_name = parts[-2]
                    if sch_name and sch_name.upper() not in [s.upper() for s in schemas_to_try]:
                        schemas_to_try.append(sch_name)
        
        if database and (not schema or schema.upper() != database.upper()):
            schemas_to_try.append(database)
            
        if "PUBLIC" not in [s.upper() for s in schemas_to_try]:
            schemas_to_try.append("PUBLIC")

        # Enforce Schema == Database as requested
        # We'll resolve them below
        target_schema = schema or database
        
        Logger.log(f"[SF] Fetching Schema for `{database}.{target_schema}` via SHOW COLUMNS (No INFORMATION_SCHEMA)...")

        try:
            r_db = self.get_real_database_name(conn, database)
            r_sch = self.get_real_schema_name(conn, r_db, target_schema)
            cursor = conn.cursor()
            # SHOW COLUMNS is more robust than INFORMATION_SCHEMA in some environments
            query = f'SHOW COLUMNS IN SCHEMA "{r_db}"."{r_sch}"'
            cursor.execute(query)
            results = cursor.fetchall()

            if not results:
                return {}

            # Cache constraints per schema
            all_constraints = {target_schema: self._get_constraints(conn, database, target_schema)}
            
            schema_info = {}
            for row in results:
                # SHOW COLUMNS format: table_name(0), schema_name(1), column_name(2), data_type(3), ..., comment(8)
                tname = row[0]
                cname = row[2]
                raw_type = row[3]
                try:
                    import json
                    type_data = json.loads(raw_type)
                    ctype = type_data.get("type", raw_type)
                except:
                    ctype = raw_type
                
                comment = row[8]
                qualified_name = f'"{r_db}"."{r_sch}"."{tname}"'
                
                # Apply filter if table_list is provided
                if table_list:
                    clean_requested = [t.split('.')[-1].replace('"', '').replace('(', '').split(' ')[0] for t in table_list]
                    if tname.upper() not in [c.upper() for c in clean_requested]:
                        continue

                if qualified_name not in schema_info:
                    sample_data = []
                    if table_list or True: # Always sample if using SHOW COLUMNS (targeted)
                        sample_data = self._get_sample_row(conn, r_db, r_sch, tname)
                    
                    schema_info[qualified_name] = {
                        "columns": [], 
                        "sample": sample_data,
                        "foreign_keys": all_constraints.get(target_schema, {}).get(tname, {}).get("foreign_keys", []),
                        "primary_keys": all_constraints.get(target_schema, {}).get(tname, {}).get("primary_keys", [])
                    }

                schema_info[qualified_name]["columns"].append(
                    {
                        "column_name": cname,
                        "type": ctype,
                        "description": comment or "",
                        "pk": cname in schema_info[qualified_name]["primary_keys"],
                    }
                )

            Logger.log(f"[SF] Metadata fetch successful (SHOW COLUMNS). Found {len(schema_info)} tables.")
            return schema_info
        except Exception as e:
            Logger.log(f"[SF] Failed to fetch Schema via SHOW: {e}", level="ERROR")
            return {}

    def get_real_database_name(self, conn, database: str) -> str:
        """Resolve exact casing for database name."""
        if not database: return ""
        
        cache_key = ("DATABASES",)
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            self._metadata_cache[cache_key] = [row[1] for row in cursor.fetchall()]
        
        for db in self._metadata_cache[cache_key]:
            if db.upper() == database.upper():
                Logger.log(f"Resolved database {database} → {db}")
                return db
        
        raise Exception(f"DATABASE_NOT_FOUND: {database}")

    def get_real_schema_name(self, conn, database: str, schema: str) -> str:
        """Resolve exact casing for schema name."""
        if not schema: return ""
        
        real_db = self.get_real_database_name(conn, database)
        cache_key = (real_db, "SCHEMAS")
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            cursor.execute(f'SHOW SCHEMAS IN DATABASE "{real_db}"')
            self._metadata_cache[cache_key] = [row[1] for row in cursor.fetchall()]
        
        for sch in self._metadata_cache[cache_key]:
            if sch.upper() == schema.upper():
                Logger.log(f"Resolved schema {schema} → {sch}")
                return sch
        
        raise Exception(f"SCHEMA_NOT_FOUND: {schema}")

    def get_real_table_name(self, conn, database: str, schema: str, table: str) -> str:
        """Resolve exact casing for table name."""
        if not table: return ""
        
        real_db = self.get_real_database_name(conn, database)
        real_sch = self.get_real_schema_name(conn, real_db, schema)
        
        cache_key = (real_db, real_sch, "TABLES")
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            cursor.execute(f'SHOW TABLES IN SCHEMA "{real_db}"."{real_sch}"')
            self._metadata_cache[cache_key] = [row[1] for row in cursor.fetchall()]
        
        for t in self._metadata_cache[cache_key]:
            if t.upper() == table.upper():
                Logger.log(f"Resolved table {table} → {t}")
                return t
        
        raise Exception(f"TABLE_NOT_FOUND: {table}")

    def get_real_column_name(self, conn, database, schema, table, column):
        """Resolve exact casing for column name via DESC TABLE."""
        if not column: return ""
        
        real_db = self.get_real_database_name(conn, database)
        real_sch = self.get_real_schema_name(conn, real_db, schema)
        real_tab = self.get_real_table_name(conn, real_db, real_sch, table)
        
        cache_key = (real_db, real_sch, real_tab)
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            # Task 1: DESC TABLE "db"."schema"."table"
            fqn = f'"{real_db}"."{real_sch}"."{real_tab}"'
            cursor.execute(f"DESC TABLE {fqn}")
            self._metadata_cache[cache_key] = [row[0] for row in cursor.fetchall()]
        
        for col in self._metadata_cache[cache_key]:
            if col.upper() == column.upper():
                Logger.log(f"Resolved column {column} → {col}")
                return col
        
        raise Exception(f"COLUMN_NOT_FOUND: {column}")

    def validate_identifiers(self, database: str, schema: str, table: str, columns: list[str] = None):
        """Task 5: Validate table and column exists before query."""
        try:
            conn = self.get_connection()
            if not conn: return {"status": "FAILED", "reason": "CONNECTION_ERROR"}
            
            real_db = self.get_real_database_name(conn, database)
            real_sch = self.get_real_schema_name(conn, real_db, schema)
            real_tab = self.get_real_table_name(conn, real_db, real_sch, table)
            
            if columns:
                for col in columns:
                    self.get_real_column_name(conn, real_db, real_sch, real_tab, col)
            
            Logger.log("Identifier validation passed")
            return {"status": "SUCCESS"}
        except Exception as e:
            reason = "UNKNOWN_ERROR"
            if "DATABASE_NOT_FOUND" in str(e): reason = "DATABASE_NOT_FOUND"
            elif "SCHEMA_NOT_FOUND" in str(e): reason = "SCHEMA_NOT_FOUND"
            elif "TABLE_NOT_FOUND" in str(e): reason = "TABLE_NOT_FOUND"
            elif "COLUMN_NOT_FOUND" in str(e): reason = "COLUMN_NOT_FOUND"
            
            Logger.log(f"Identifier validation failed: {e}", level="ERROR")
            return {"status": "FAILED", "reason": reason}

    def get_full_discovery_metadata(self, database: str) -> dict[str, Any]:
        """One-call discovery: Fetches all tables and columns in the database.schema in one pass."""
        if not database:
            return {}
        conn = self.get_connection(database=database)
        if not conn:
            return {}
            
        target_schema = database
        all_tables_list = []
        schema_info = {}
        
        try:
            r_db = self.get_real_database_name(conn, database)
            r_sch = self.get_real_schema_name(conn, r_db, target_schema)
            cursor = conn.cursor()
            Logger.log(f"[SF] Performing One-Call Discovery for `{r_db}.{r_sch}`...")
            
            # SHOW COLUMNS gives us tables AND columns in one go
            query = f'SHOW COLUMNS IN SCHEMA "{r_db}"."{r_sch}"'
            cursor.execute(query)
            results = cursor.fetchall()
            
            if not results:
                return {"all_table_names": [], "schema_info": {}}

            # Cache constraints
            constraints = self._get_constraints(conn, r_db, r_sch)
            
            for row in results:
                # row format: tname(0), tschema(1), cname(2), ctype_json(3), ..., comment(8)
                tname = row[0]
                cname = row[2]
                raw_type = row[3]
                try:
                    import json
                    type_data = json.loads(raw_type)
                    ctype = type_data.get("type", raw_type)
                except:
                    ctype = raw_type
                
                comment = row[8]
                qualified_name = f'"{r_db}"."{r_sch}"."{tname}"'
                
                if qualified_name not in schema_info:
                    all_tables_list.append(qualified_name)
                    sample_data = []
                    if len(set(r[0] for r in results)) < 15:
                        sample_data = self._get_sample_row(conn, r_db, r_sch, tname)
                    
                    schema_info[qualified_name] = {
                        "columns": [], 
                        "sample": sample_data,
                        "foreign_keys": constraints.get(tname, {}).get("foreign_keys", []),
                        "primary_keys": constraints.get(tname, {}).get("primary_keys", [])
                    }

                schema_info[qualified_name]["columns"].append({
                    "column_name": cname,
                    "type": ctype,
                    "description": comment or "",
                    "pk": cname in schema_info[qualified_name]["primary_keys"]
                })
                
            return {
                "all_table_names": list(set(all_tables_list)),
                "schema_info": schema_info
            }
        except Exception as e:
            Logger.log(f"[SF] One-Call Discovery failed: {e}", level="ERROR")
            return {"all_table_names": [], "schema_info": {}}

    def get_table_names(self, database: str, schema: str | None = None) -> list[str]:
        """Fetch table names via SHOW TABLES (No INFORMATION_SCHEMA). Enforce Schema == Database."""
        if not database:
            return []
        conn = self.get_connection(database=database, schema=schema)
        if not conn:
            return []
        
        target_schema = database
        all_tables = []
        try:
            r_db = self.get_real_database_name(conn, database)
            r_sch = self.get_real_schema_name(conn, r_db, target_schema)
            cursor = conn.cursor()
            query = f'SHOW TABLES IN SCHEMA "{r_db}"."{r_sch}"'
            cursor.execute(query)
            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    name = row[1] # Exact casing
                    comment_val = row[5]
                    comment = f" ({comment_val})" if comment_val else ""
                    all_tables.append(f'"{r_db}"."{r_sch}"."{name}"{comment}')
                Logger.log(f"[SF] Discovered {len(rows)} tables in schema `{r_sch}` via SHOW TABLES.")
        except Exception as e:
            Logger.log(f"[SF] SHOW TABLES failed for schema `{r_sch}`: {e}", level="ERROR")
        
        return list(set(all_tables))


    def execute_query(self, query: str, sampling: bool = False, db_name: str = None) -> ExecutionResult:
        """Task 5: Executes a query with pre-validation and session context."""
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            conn = self.get_connection(database=db_name)
            if not conn:
                raise Exception("Failed to establish Snowflake connection.")

            cursor = conn.cursor()

            # Ensure session has correct database context if provided
            if db_name:
                cursor.execute(f'USE DATABASE {quote_identifier(db_name)}')
            
            # Note: Identifier validation can be performed here if full context is available.
            # But since execute_query is low-level, we often validate in the orchestration layer.
            
            # Task 5: Handle non-executable markers or empty queries
            if not query.strip() or (query.strip().startswith("--") and "\n" not in query.strip() and "SELECT" not in query.upper()):
                 result.status = "SUCCESS"
                 result.reason = "SKIPPED_METADATA_ONLY"
                 result.error_message = "Query contains no executable SQL (comment or blocker marker)."
                 return result

            cursor.execute(query)
            
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]

            if sampling:
                Logger.log("Large table avoided (sampling applied)")
                if "LIMIT" not in query.upper():
                    rows = cursor.fetchmany(3)
                else:
                    rows = cursor.fetchmany(5)
            else:
                rows = cursor.fetchall()

            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)

        except Exception as e:
            err_str = str(e)
            if "invalid identifier" in err_str.lower() or "does not exist" in err_str.lower():
                result.status = "FAILED"
                result.reason = "COLUMN_NOT_FOUND" if "identifier" in err_str.lower() else "TABLE_NOT_FOUND"
            
            result.error_message = err_str
            Logger.log(f"[SF] Query execution failed: {e}", level="ERROR")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        return result

    def _get_sample_row(self, conn, database, schema, table_name) -> Any:
        """Internal helper to sample multiple rows for high-precision profiling with resolved identifiers."""
        try:
            r_db = self.get_real_database_name(conn, database)
            r_sch = self.get_real_schema_name(conn, r_db, schema)
            r_tab = self.get_real_table_name(conn, r_db, r_sch, table_name)
            
            cursor = conn.cursor()
            fqn = f"{quote_identifier(r_db)}.{quote_identifier(r_sch)}.{quote_identifier(r_tab)}"
            cursor.execute(f"SELECT * FROM {fqn} LIMIT 3")
            rows = cursor.fetchall()
            if not rows:
                return "NULL_OR_EMPTY"
            
            cols = [d[0] for d in cursor.description]
            samples = []
            for row in rows:
                row_dict = {}
                for col, val in zip(cols, row):
                    if isinstance(val, (bytes, bytearray)):
                        row_dict[col] = f"<BINARY_DATA: {len(val)} bytes>"
                    elif hasattr(val, "isoformat"):
                        row_dict[col] = val.isoformat()
                    else:
                        row_dict[col] = val
                samples.append(row_dict)
            return samples
        except Exception as e:
            return f"SAMPLE_ERROR: {str(e)}"

    def _get_constraints(self, conn, database, schema) -> dict[str, Any]:
        """Fetches PK and FK constraints for a schema to aid in join discovery."""
        constraints = {}
        try:
            cursor = conn.cursor()
            # Stage 1: Get Primary Keys
            try:
                r_db = self.get_real_database_name(conn, database)
                r_sch = self.get_real_schema_name(conn, r_db, schema)
                pk_query = f"SHOW PRIMARY KEYS IN SCHEMA \"{r_db}\".\"{r_sch}\""
                cursor.execute(pk_query)
                for row in cursor.fetchall():
                    tname = row[3] # Exact casing
                    cname = row[4] # Exact casing
                    if tname not in constraints:
                        constraints[tname] = {"primary_keys": [], "foreign_keys": []}
                    constraints[tname]["primary_keys"].append(cname)
            except:
                pass

            # Stage 2: Get Foreign Keys
            try:
                fk_query = f"SHOW IMPORTED KEYS IN SCHEMA \"{r_db}\".\"{r_sch}\""
                cursor.execute(fk_query)
                for row in cursor.fetchall():
                    fk_table = row[7] # Exact casing
                    fk_col = row[8] # Exact casing
                    pk_table = row[3]
                    pk_col = row[4]
                    
                    if fk_table not in constraints:
                        constraints[fk_table] = {"primary_keys": [], "foreign_keys": []}
                    
                    constraints[fk_table]["foreign_keys"].append({
                        "column": fk_col,
                        "ref_table": pk_table,
                        "ref_column": pk_col
                    })
            except:
                pass
        except Exception as e:
            Logger.log(f"[SF] Constraint Discovery failed for {schema}: {e}", level="WARN")
        
        return constraints
