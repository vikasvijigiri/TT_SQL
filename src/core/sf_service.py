import os
import threading
from typing import Dict, Any, List, Optional
import snowflake.connector
from .logger import Logger

class SnowflakeService:
    """
    Service for interacting with Snowflake.
    Handles metadata extraction and query execution.
    """

    _metadata_cache = {}
    _conn_pool = {}
    _lock = threading.Lock()

    def get_connection(self, database: str = None, schema: str = None):
        """Establish and cache a Snowflake connection."""
        conn_key = f"{database}.{schema}"
        if conn_key not in self._conn_pool:
            try:
                # Use environment variables for connection
                conn = snowflake.connector.connect(
                    user=os.getenv("SNOWFLAKE_USER"),
                    password=os.getenv("SNOWFLAKE_PASSWORD"),
                    account=os.getenv("SNOWFLAKE_ACCOUNT"),
                    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
                    database=database,
                    schema=schema
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
        
        for sch_to_try in schemas_to_try:
            try:
                r_db = self.get_real_database_name(conn, database)
                r_sch = self.get_real_schema_name(conn, r_db, sch_to_try)
                
                Logger.log(f"\n[SF] Attempting schema fetch for {r_db}.{r_sch} ...")
                
                cursor = conn.cursor()
                query = f'SHOW COLUMNS IN SCHEMA "{r_db}"."{r_sch}"'
                cursor.execute(query)
                results = cursor.fetchall()

                if not results:
                    Logger.log(f"[SF] No columns found in {r_db}.{r_sch}")
                    continue

                # Cache constraints per schema
                all_constraints = {sch_to_try: self._get_constraints(conn, database, sch_to_try)}
                
                for row in results:
                    # row[0]=table_name, row[2]=column_name, row[3]=data_type, row[8]=comment
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
                    # Snowflake FQN Protocol: IDC.IDC_V17.DICOM_ALL (unquoted, case-preserved)
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
                            "foreign_keys": all_constraints.get(sch_to_try, {}).get(tname, {}).get("foreign_keys", []),
                            "primary_keys": all_constraints.get(sch_to_try, {}).get(tname, {}).get("primary_keys", [])
                        }

                    schema_info[qualified_name]["columns"].append({
                        "column_name": cname,
                        "type": ctype,
                        "description": comment or "",
                        "pk": cname in schema_info[qualified_name]["primary_keys"],
                    })

                if schema_info:
                    Logger.log(f"[SF] Metadata fetch successful for {r_db}.{r_sch}. Found {len(schema_info)} tables.\n")
                    # We can continue to next schemas or break if we found what we needed
                    # For now, we collect all found tables across schemas
            except Exception as e:
                errors.append(f"{sch_to_try}: {e}")
                continue

        if not schema_info and errors:
            Logger.log(f"[SF] All schema fetch attempts failed: {'; '.join(errors)}", level="ERROR")
            
        return schema_info

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
                # Removed arrow artifact
                Logger.log(f"Resolved database {database} -> {db}", level="DEBUG")
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
                Logger.log(f"Resolved schema {schema} -> {sch}", level="DEBUG")
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
                Logger.log(f"Resolved table {table} -> {t}", level="DEBUG")
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
            fqn = f'"{real_db}"."{real_sch}"."{real_tab}"'
            cursor.execute(f"DESC TABLE {fqn}")
            self._metadata_cache[cache_key] = [row[0] for row in cursor.fetchall()]
        
        for col in self._metadata_cache[cache_key]:
            if col.upper() == column.upper():
                return col
        return column

    def _get_constraints(self, conn, database, schema):
        """Fetches primary and foreign keys for a schema."""
        constraints = {}
        try:
            cursor = conn.cursor()
            # Primary Keys
            cursor.execute(f'SHOW PRIMARY KEYS IN SCHEMA "{database}"."{schema}"')
            for row in cursor.fetchall():
                tname = row[4]
                cname = row[3]
                if tname not in constraints: constraints[tname] = {"primary_keys": [], "foreign_keys": []}
                constraints[tname]["primary_keys"].append(cname)
            
            # Foreign Keys
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
        """Fetches a sample row for a table."""
        try:
            cursor = conn.cursor()
            # Unquoted table name in query as per protocol for Table/Schema/DB
            # Actually, to be safe in the SELECT query itself, we should use quotes if the identifier is mixed case
            # But the requirement is UNQUOTED in the log/metadata. 
            # In Snowflake, unquoted usually defaults to upper. 
            # To fetch data for a case-sensitive table, we MUST use quotes in the SQL.
            query = f'SELECT * FROM "{database}"."{schema}"."{table}" LIMIT 1'
            cursor.execute(query)
            col_names = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            if row:
                return [dict(zip(col_names, row))]
        except: pass
        return []

    def execute_query(self, query: str, database: str = None):
        """Executes a SQL query and returns results."""
        from core.agent_base import ExecutionResult
        
        conn = self.get_connection(database=database)
        if not conn:
            return ExecutionResult(status="ERROR", error_message="Failed to connect to Snowflake")
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            
            rows = [dict(zip(col_names, row)) for row in results]
            return ExecutionResult(
                status="SUCCESS",
                rows=rows,
                row_count=len(rows),
                columns=col_names
            )
        except Exception as e:
            return ExecutionResult(status="ERROR", error_message=str(e))
