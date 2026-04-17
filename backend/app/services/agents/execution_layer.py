import os
from typing import Optional, Dict, Any
import sqlite3
import psycopg2
import time
import threading
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState, ExecutionResult
from app.services.utils.logger import Logger
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.persistence.file_coordinator import FileCoordinator
from app.repositories.config import settings
from app.repositories.registry.paths import InstancePaths

class SQLiteExecutorAgent(BaseAgent):
    """
    SQLiteExecutorAgent executes SQL queries against a local SQLite database.
    It handles result caching, error reporting, and background CSV persistence.
    """
    def __init__(self, db_path: Optional[str] = None, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="SQLiteExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)
        self.db_path = db_path
        
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Retrieves the physical schema for a specific table in the SQLite database.
        
        Args:
            table_name (str): Name of the table to inspect.
            
        Returns:
            Dict[str, Any]: Column metadata or an empty dict if the table is not found.
        """
        if not self.db_path: return {}
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows: return {}
            
            columns = []
            for r in rows:
                columns.append({
                    "name": r[1],
                    "type": r[2],
                    "pk": bool(r[5])
                })
            return {"columns": columns}
        except sqlite3.Error as e:
            Logger.log(f"SQLite Schema Inspection Error for {table_name}: {str(e)}", level="DEBUG")
            return {}

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query:
            self.log(state, "No query provided for execution.")
            return state

        query = state.chosen_query
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            conn = sqlite3.connect(state.db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            rows = cursor.fetchmany(5) if getattr(state, "sampling_enabled", False) else cursor.fetchall()
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            conn.close()
            
        except sqlite3.Error as e:
            error_msg = str(e)
            result.error_message = error_msg
            state.error_message = error_msg
            self.log(state, f"SQLite Execution Failure: {error_msg}", level="ERROR")
            if error_msg not in state.execution_error_history:
                state.execution_error_history.append(f"SQL Error: {error_msg}")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Execution completed in {result.execution_time_ms:.2f}ms. Returned {result.row_count} records.")
        
        threading.Thread(target=self._bg_persist_results, args=(state, result), daemon=True).start()
        return state

    # --- Private Methods ---

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            if result.error_message:
                self.file_coordinator.write_csv(state.instance_id, [["failed", result.error_message]], ["status", "error"], state.model_name)
            else:
                self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        except Exception as e:
            Logger.log(f"Background result persistence failed: {str(e)}", level="DEBUG")

class ResultValidatorAgent(BaseAgent):
    """
    Validates execution results.
    """
    def __init__(self):
        super().__init__(name="ResultValidator")

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        res = state.execution_result
        if not res:
            return state
            
        if res.error_message:
            # Here we might trigger error refinement
            self.log(state, "Result invalid due to execution error.")
        elif res.row_count == 0:
            self.log(state, "Warning: Query returned 0 rows.")
        else:
            self.log(state, "Result looks valid (non-empty).")
            
        return state


class PostgresExecutorAgent(BaseAgent):
    """
    PostgresExecutorAgent executes SQL queries against an Amazon RDS PostgreSQL instance.
    It supports global connection pooling to minimize handshake overhead (R1).
    """
    # Global connection pool (shared across all instances in the process)
    _SHARED_CONN = None
    _CONN_LOCK = threading.Lock()

    @classmethod
    def reset_connection_pool(cls):
        """Close and clear the shared connection when the active project changes."""
        with cls._CONN_LOCK:
            if cls._SHARED_CONN and not cls._SHARED_CONN.closed:
                try:
                    cls._SHARED_CONN.close()
                except Exception:
                    pass
            cls._SHARED_CONN = None

    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="PostgresExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)

    def get_table_schema(self, table_name: str, schema_name: str = "public") -> Dict[str, Any]:
        """
        Retrieves real-time schema metadata for an RDS table.
        
        Args:
            table_name (str): Name of the table.
            schema_name (str): The schema/search_path for the table.
            
        Returns:
            Dict[str, Any]: Dictionary containing column names and types.
        """
        schema = schema_name.strip().replace('"', '')
        conn = None
        try:
            conn = psycopg2.connect(
                host=settings.RDS_HOST,
                database=settings.RDS_DATABASE,
                user=settings.RDS_USER,
                password=settings.RDS_PASSWORD,
                port=settings.RDS_PORT,
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = '{schema}' AND table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            rows = cursor.fetchall()
            conn.close()
            
            if not rows: return {}
            
            columns = []
            for r in rows:
                columns.append({
                    "name": r[0],
                    "type": r[1],
                    "pk": False
                })
            return {"columns": columns}
        except Exception as e:
            Logger.log(f"Postgres Schema Inspection Error for {table_name}: {str(e)}", level="DEBUG")
            if conn: conn.close()
            return {}

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query:
            self.log(state, "No valid query provided for RDS execution.")
            return state

        query = state.chosen_query
        schema = (state.db_name if hasattr(state, "db_name") and state.db_name else "public").strip().replace('"', '')
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            with PostgresExecutorAgent._CONN_LOCK:
                if PostgresExecutorAgent._SHARED_CONN and not PostgresExecutorAgent._SHARED_CONN.closed:
                    conn = PostgresExecutorAgent._SHARED_CONN
                else:
                    conn = psycopg2.connect(host=settings.RDS_HOST, database=settings.RDS_DATABASE, user=settings.RDS_USER, password=settings.RDS_PASSWORD, port=settings.RDS_PORT, connect_timeout=10)
                    conn.autocommit = True
                    PostgresExecutorAgent._SHARED_CONN = conn
            
            cursor = conn.cursor()
            if schema and schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{schema}", public;')
            
            cursor.execute(query)
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            rows = cursor.fetchmany(5) if getattr(state, "sampling_enabled", False) else cursor.fetchall()
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            
        except Exception as e:
            error_msg = str(e)
            result.error_message = error_msg; state.error_message = error_msg
            self.log(state, f"RDS Execution Failure: {error_msg}", level="ERROR")
            if error_msg not in state.execution_error_history:
                state.execution_error_history.append(f"Postgres Error: {error_msg}")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"RDS Execution completed in {result.execution_time_ms:.2f}ms. Rows: {result.row_count}")
        
        threading.Thread(target=self._bg_persist_results, args=(state, result), daemon=True).start()
        return state

    # --- Private Methods ---

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            if result.error_message:
                self.file_coordinator.write_csv(state.instance_id, [["failed", result.error_message]], ["status", "error"], state.model_name)
            else:
                self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        except Exception as e:
            Logger.log(f"RDS background persistence failed: {str(e)}", level="DEBUG")


class ErrorRefinerAgent(BaseAgent):
    """
    Attempts to refine SQL queries that failed with errors.
    Uses common error patterns to fix issues automatically.
    """
    def __init__(self, llm_service=None):
        super().__init__(name="ErrorRefiner")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.max_retries = 2
        
    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        res = state.execution_result
        if not res or not res.error_message:
            return state
        
        error_msg = res.error_message
        original_sql = state.chosen_query
        fixed_sql = self._try_auto_fix(original_sql, error_msg)
        
        if fixed_sql and fixed_sql != original_sql:
            self.log(state, f"Auto-fix applied for: {error_msg[:50]}...")
            state.chosen_query = fixed_sql
            state = self._execute_query_internal(state)
            
        if state.execution_result.error_message and self.llm:
            fixed_sql = self._try_llm_fix(state, original_sql, error_msg)
            if fixed_sql:
                state.chosen_query = fixed_sql
                state = self._execute_query_internal(state)
                self.log(state, f"LLM fix attempted. New result: {state.execution_result.row_count} rows")
        
        return state

    # --- Private Methods ---

    def _try_auto_fix(self, sql: str, error: str) -> str:
        if "no such function" in error.lower():
            import re
            func_match = re.search(r'no such function:?\s*(\w+)', error, re.I)
            if func_match:
                func_name = func_match.group(1)
                return re.sub(rf'\b{func_name}\s*\([^)]*\)', '0', sql, flags=re.I)
        return sql
    
    def _try_llm_fix(self, state: AgentState, sql: str, error: str) -> str:
        messages = self.prompt_loader.load_prompt("error_correction", sql=sql, error=error,
            tables_available=list(state.schema_info.keys()) if state.schema_info else 'Unknown')
        response = self.llm.get_completion(messages, max_tokens=500)
        
        if response and not response.startswith("ERROR:"):
            if "```" in response:
                response = response.split("```")[1] if "```sql" in response else response.split("```")[1]
            return response.strip()
        return None
    
    def _execute_query_internal(self, state: AgentState) -> AgentState:
        import sqlite3
        start_t = time.time()
        result = ExecutionResult()
        try:
            conn = sqlite3.connect(state.db_path)
            cursor = conn.cursor(); cursor.execute(state.chosen_query)
            if cursor.description: result.columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result.rows = [list(row) for row in rows]; result.row_count = len(rows)
            conn.close()
        except sqlite3.Error as e:
            result.error_message = str(e)
            if f"SQL Error: {str(e)}" not in state.execution_error_history:
                state.execution_error_history.append(f"SQL Error: {str(e)}")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = result
        return state

class BigQueryExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Google Cloud BigQuery.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="BigQueryExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)

    def get_table_schema(self, table_name: str, dataset_name: str = None) -> Dict[str, Any]:
        from google.cloud import bigquery
        from google.oauth2 import service_account
        
        creds_path = getattr(settings, "BQ_CREDENTIALS_PATH", "")
        project_id = settings.RDS_DATABASE # reusing database for project_id
        dataset_id = dataset_name or settings.SCHEMA
        
        try:
            if not os.path.exists(creds_path): return {}
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            client = bigquery.Client(credentials=credentials, project=project_id)
            
            table_ref = f"{project_id}.{dataset_id}.{table_name}"
            table = client.get_table(table_ref)
            
            columns = []
            for field in table.schema:
                columns.append({
                    "name": field.name,
                    "type": field.field_type,
                    "pk": False
                })
            return {"columns": columns}
        except Exception as e:
            Logger.log(f"BigQuery Schema Error for {table_name}: {str(e)}", level="DEBUG")
            return {}

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query: return state
        
        start_t = time.time()
        active_conn = {
            "database": settings.RDS_DATABASE,
            "schema": settings.SCHEMA,
            "bq_credentials_path": getattr(settings, "BQ_CREDENTIALS_PATH", "")
        }
        res = DBRepository._execute_bigquery(state.chosen_query, active_conn)
        res.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = res
        
        if res.error_message:
            self.log(state, f"BigQuery Error: {res.error_message}", level="ERROR")
        else:
            self.log(state, f"BigQuery Success: {res.row_count} rows in {res.execution_time_ms:.2f}ms")
            
        threading.Thread(target=self._bg_persist_results, args=(state, res), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            if result.error_message:
                self.file_coordinator.write_csv(state.instance_id, [["failed", result.error_message]], ["status", "error"], state.model_name)
            else:
                self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        except Exception as e:
            Logger.log(f"BQ background persistence failed: {str(e)}", level="DEBUG")

class SnowflakeExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Snowflake.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="SnowflakeExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)

    def get_table_schema(self, table_name: str, schema_name: str = None) -> Dict[str, Any]:
        active_conn = {
            "user": settings.RDS_USER,
            "password": settings.RDS_PASSWORD,
            "host": settings.RDS_HOST,
            "database": settings.RDS_DATABASE,
            "schema": schema_name or settings.SCHEMA,
            "sf_warehouse": getattr(settings, "SF_WAREHOUSE", ""),
            "sf_role": getattr(settings, "SF_ROLE", "")
        }
        
        try:
            query = f"DESCRIBE TABLE {active_conn['database']}.{active_conn['schema']}.{table_name}"
            res = DBRepository._execute_snowflake(query, active_conn)
            
            if res.error_message or not res.rows: return {}
            
            columns = []
            for row in res.rows:
                # row[0] is name, row[1] is type
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "pk": False
                })
            return {"columns": columns}
        except Exception as e:
            Logger.log(f"Snowflake Schema Error for {table_name}: {str(e)}", level="DEBUG")
            return {}

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query: return state
        
        start_t = time.time()
        active_conn = {
            "user": settings.RDS_USER,
            "password": settings.RDS_PASSWORD,
            "host": settings.RDS_HOST,
            "database": settings.RDS_DATABASE,
            "schema": settings.SCHEMA,
            "sf_warehouse": getattr(settings, "SF_WAREHOUSE", ""),
            "sf_role": getattr(settings, "SF_ROLE", "")
        }
        res = DBRepository._execute_snowflake(state.chosen_query, active_conn)
        res.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = res
        
        if res.error_message:
            self.log(state, f"Snowflake Error: {res.error_message}", level="ERROR")
        else:
            self.log(state, f"Snowflake Success: {res.row_count} rows in {res.execution_time_ms:.2f}ms")
            
        threading.Thread(target=self._bg_persist_results, args=(state, res), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            if result.error_message:
                self.file_coordinator.write_csv(state.instance_id, [["failed", result.error_message]], ["status", "error"], state.model_name)
            else:
                self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        except Exception as e:
            Logger.log(f"Snowflake background persistence failed: {str(e)}", level="DEBUG")
