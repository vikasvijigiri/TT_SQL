import os
import threading
import json
from typing import Dict, Any, List, Optional
import snowflake.connector
from .logger import Logger
from .config import get_settings

class SnowflakeService:
    """
    Service for interacting with Snowflake.
    Handles metadata extraction and query execution.
    Hardened for production with credential file support and ASCII logging.
    """

    _metadata_cache = {}
    _conn_pool = {}
    _lock = threading.Lock()

    @classmethod
    def reset(cls):
        """Resets the connection pool and cache."""
        with cls._lock:
            for conn in cls._conn_pool.values():
                try: conn.close()
                except: pass
            cls._conn_pool = {}
            cls._metadata_cache = {}

    def _load_credentials(self):
        """Load credentials from env vars with fallback to sf_credentials.json."""
        creds = {
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
            "role": os.getenv("SNOWFLAKE_ROLE")
        }
        
        settings = get_settings()
        creds_path = settings.sf_credentials_abs_path
        
        if not all([creds["user"], creds["password"], creds["account"]]) and creds_path and os.path.exists(creds_path):
            try:
                with open(creds_path, 'r') as f:
                    file_creds = json.load(f)
                    for k, v in file_creds.items():
                        if not creds.get(k):
                            creds[k] = v
            except Exception as e:
                Logger.log(f"[SF] Failed to load credentials from file: {e}", level="WARN")
        
        return creds

    def get_connection(self, database: str = None, schema: str = None):
        """Establish and cache a Snowflake connection."""
        db_val = str(database) if database else None
        sch_val = str(schema) if schema else None
        
        conn_key = f"{db_val}.{sch_val}"
        with self._lock:
            if conn_key not in self._conn_pool:
                try:
                    creds = self._load_credentials()
                    if not creds.get("account"):
                        Logger.log("[SF] Missing Snowflake account credential.", level="ERROR")
                        return None
                        
                    conn = snowflake.connector.connect(
                        user=creds.get("user"),
                        password=creds.get("password"),
                        account=creds.get("account"),
                        warehouse=creds.get("warehouse"),
                        role=creds.get("role"),
                        database=db_val,
                        schema=sch_val
                    )
                    self._conn_pool[conn_key] = conn
                except Exception as e:
                    Logger.log(f"[SF] Connection failed: {e}", level="ERROR")
                    return None
            return self._conn_pool[conn_key]

    def fetch_schema(self, database: str, schema: str = None, table_list: list = None) -> Dict[str, Any]:
        """
        Extracts Snowflake schema metadata.
        Iterates through candidate schemas if the primary one is missing.
        """
        if not database:
            return {}

        conn = self.get_connection(database=database, schema=schema)
        if not conn:
            return {}

        schemas_to_try = []
        if schema:
            schemas_to_try.append(schema)
            
        # Extract candidate schemas from table_list
        if table_list:
            for t in table_list:
                parts = str(t).split(" ")[0].replace('"', '').split(".")
                if len(parts) >= 2:
                    sch_name = parts[-2]
                    if sch_name and sch_name.upper() not in [s.upper() for s in schemas_to_try]:
                        schemas_to_try.append(sch_name)
        
        if database and (not schema or schema.upper() != database.upper()):
            if database.upper() not in [s.upper() for s in schemas_to_try]:
                schemas_to_try.append(database)
            
        if "PUBLIC" not in [s.upper() for s in schemas_to_try]:
            schemas_to_try.append("PUBLIC")

        schema_info = {}
        errors = []
        
        # 1. Try initial candidates
        for sch_to_try in schemas_to_try:
            try:
                r_db = self.get_real_database_name(conn, database)
                r_sch = self.get_real_schema_name(conn, r_db, sch_to_try)
                
                res = self._fetch_schema_for_real_names(conn, r_db, r_sch, table_list)
                if res:
                    schema_info.update(res)
                    # If we found at least one table from table_list, we can stop
                    if table_list:
                        found_tables = [t.split('.')[-1].upper() for t in schema_info.keys()]
                        requested_tables = [t.split('.')[-1].replace('"', '').upper() for t in table_list]
                        if any(t in found_tables for t in requested_tables):
                            break
            except Exception as e:
                errors.append(f"{sch_to_try}: {e}")

        # 2. If nothing found, try ALL schemas in the database (except internal)
        if not schema_info:
            Logger.log(f"[SF] No tables found in primary candidates. Fetching all schemas in {database}...")
            try:
                r_db = self.get_real_database_name(conn, database)
                cursor = conn.cursor()
                cursor.execute(f'SHOW SCHEMAS IN DATABASE "{r_db}"')
                all_schemas = [row[1] for row in cursor.fetchall() if row[1].upper() not in ["INFORMATION_SCHEMA"]]
                
                for r_sch in all_schemas:
                    if r_sch.upper() in [s.upper() for s in schemas_to_try]: continue
                    res = self._fetch_schema_for_real_names(conn, r_db, r_sch, table_list)
                    if res:
                        schema_info.update(res)
                        if table_list: break
            except Exception as e:
                Logger.log(f"[SF] Global schema search failed: {e}", level="ERROR")

        if not schema_info and errors:
            Logger.log(f"[SF] All schema fetch attempts failed: {'; '.join(errors)}", level="ERROR")
            
        return schema_info

    def _fetch_schema_for_real_names(self, conn, r_db, r_sch, table_list):
        """Helper to fetch columns for resolved names."""
        Logger.log(f"\n[SF] Attempting schema fetch for {r_db}.{r_sch} ...")
        
        cursor = conn.cursor()
        query = f'SHOW COLUMNS IN SCHEMA "{r_db}"."{r_sch}"'
        try:
            cursor.execute(query)
            results = cursor.fetchall()
        except Exception as e:
            if "does not exist" in str(e): return {}
            raise e

        if not results:
            Logger.log(f"[SF] No columns found in {r_db}.{r_sch}")
            return {}

        schema_info = {}
        all_constraints = {r_sch: self._get_constraints(conn, r_db, r_sch)}
        
        for row in results:
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
            qualified_name = f"{r_db}.{r_sch}.{tname}"
            
            if table_list:
                clean_requested = [t.split('.')[-1].replace('"', '').replace('(', '').split(' ')[0] for t in table_list]
                if tname.upper() not in [c.upper() for c in clean_requested]:
                    continue

            if qualified_name not in schema_info:
                sample_data = self._get_sample_row(conn, r_db, r_sch, tname)
                schema_info[qualified_name] = {
                    "columns": [], 
                    "sample": sample_data,
                    "foreign_keys": all_constraints.get(r_sch, {}).get(tname, {}).get("foreign_keys", []),
                    "primary_keys": all_constraints.get(r_sch, {}).get(tname, {}).get("primary_keys", [])
                }

            schema_info[qualified_name]["columns"].append({
                "column_name": cname,
                "type": ctype,
                "description": comment or "",
                "pk": cname in schema_info[qualified_name]["primary_keys"],
            })

        if schema_info:
            Logger.log(f"[SF] Metadata fetch successful for {r_db}.{r_sch}. Found {len(schema_info)} tables.\n")
        return schema_info

    def get_real_database_name(self, conn, database: str) -> str:
        if not database: return ""
        cache_key = ("DATABASES",)
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            self._metadata_cache[cache_key] = [row[1] for row in cursor.fetchall()]
        for db in self._metadata_cache[cache_key]:
            if db.upper() == database.upper(): return db
        raise Exception(f"DATABASE_NOT_FOUND: {database}")

    def get_real_schema_name(self, conn, database: str, schema: str) -> str:
        if not schema: return ""
        real_db = self.get_real_database_name(conn, database)
        cache_key = (real_db, "SCHEMAS")
        if cache_key not in self._metadata_cache:
            cursor = conn.cursor()
            cursor.execute(f'SHOW SCHEMAS IN DATABASE "{real_db}"')
            self._metadata_cache[cache_key] = [row[1] for row in cursor.fetchall()]
        for sch in self._metadata_cache[cache_key]:
            if sch.upper() == schema.upper(): return sch
        raise Exception(f"SCHEMA_NOT_FOUND: {schema}")

    def _get_constraints(self, conn, database, schema):
        constraints = {}
        try:
            cursor = conn.cursor()
            cursor.execute(f'SHOW PRIMARY KEYS IN SCHEMA "{database}"."{schema}"')
            for row in cursor.fetchall():
                tname = row[4]
                cname = row[3]
                if tname not in constraints: constraints[tname] = {"primary_keys": [], "foreign_keys": []}
                constraints[tname]["primary_keys"].append(cname)
            cursor.execute(f'SHOW IMPORTED KEYS IN SCHEMA "{database}"."{schema}"')
            for row in cursor.fetchall():
                tname = row[8]
                cname = row[7]
                ref_t = row[2]
                ref_c = row[1]
                if tname not in constraints: constraints[tname] = {"primary_keys": [], "foreign_keys": []}
                constraints[tname]["foreign_keys"].append({
                    "column": cname,
                    "ref_table": ref_t,
                    "ref_column": ref_c
                })
        except: pass
        return constraints

    def _get_sample_row(self, conn, database, schema, table):
        try:
            cursor = conn.cursor()
            query = f'SELECT * FROM "{database}"."{schema}"."{table}" LIMIT 1'
            cursor.execute(query)
            col_names = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                return [dict(zip(col_names, row))]
        except: pass
        return []

    def execute_query(self, query: str, database: str = None):
        from core.state import ExecutionResult
        conn = self.get_connection(database=database)
        if not conn: return ExecutionResult(status="ERROR", error_message="Failed to connect to Snowflake")
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            rows = [list(row) for row in results]
            return ExecutionResult(status="SUCCESS", rows=rows, row_count=len(rows), columns=col_names)
        except Exception as e: return ExecutionResult(status="ERROR", error_message=str(e))
