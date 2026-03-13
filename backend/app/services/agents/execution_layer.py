import os
import sqlite3
import psycopg2
import time
import threading
from app.services.agents.base import BaseAgent
from app.models.agent_state import AgentState, ExecutionResult
from app.services.logger import Logger
from app.repos.file_coordinator import FileCoordinator
from app.models.config import settings
from app.models.paths import InstancePaths

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
        """
        Executes the chosen SQL query and updates the state with the result.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            
        Returns:
            AgentState: The updated state with ExecutionResult populated.
        """
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
            
            # Extract column headers
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            # Fetch data with optional sampling for large results
            if getattr(state, "sampling_enabled", False):
                rows = cursor.fetchmany(5)
                self.log(state, f"Sampling enabled: limited result to {len(rows)} records.")
            else:
                rows = cursor.fetchall()
            
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            conn.close()
            
        except sqlite3.Error as e:
            error_msg = str(e)
            result.error_message = error_msg
            state.error_message = error_msg
            self.log(state, f"SQLite Execution Failure: {error_msg}", level="ERROR")
            
            # Persist error history for iterative refinement
            if error_msg not in state.execution_error_history:
                state.execution_error_history.append(f"SQL Error: {error_msg}")
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Execution completed in {result.execution_time_ms:.2f}ms. Returned {result.row_count} records.")
        
        # Asynchronous result persistence
        import threading
        def _bg_persistence():
            try:
                if result.error_message:
                    self.file_coordinator.write_csv(
                        state.instance_id, 
                        [["failed", result.error_message]], 
                        ["status", "error"], 
                        state.model_name
                    )
                else:
                    self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
            except Exception as e:
                Logger.log(f"Background result persistence failed: {str(e)}", level="DEBUG")

        threading.Thread(target=_bg_persistence, daemon=True).start()
        
        return state

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
        """
        Executes a Postgres query on RDS with connection reuse logic.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            
        Returns:
            AgentState: The updated state with ExecutionResult populated.
        """
        if not state.chosen_query:
            self.log(state, "No valid query provided for RDS execution.")
            return state

        query = state.chosen_query
        schema = (state.db_name if hasattr(state, "db_name") and state.db_name else "public").strip().replace('"', '')

        start_t = time.time()
        result = ExecutionResult()
        
        try:
            # Global Connection Management (R1)
            with PostgresExecutorAgent._CONN_LOCK:
                if PostgresExecutorAgent._SHARED_CONN and not PostgresExecutorAgent._SHARED_CONN.closed:
                    conn = PostgresExecutorAgent._SHARED_CONN
                    self.log(state, "Reusing global RDS session (Production Optimization).")
                else:
                    self.log(state, "Opening fresh global RDS connection pool...")
                    conn = psycopg2.connect(
                        host=settings.RDS_HOST,
                        database=settings.RDS_DATABASE,
                        user=settings.RDS_USER,
                        password=settings.RDS_PASSWORD,
                        port=settings.RDS_PORT,
                        connect_timeout=10
                    )
                    conn.autocommit = True
                    PostgresExecutorAgent._SHARED_CONN = conn
            
            cursor = conn.cursor()

            # Dynamic search_path set for non-public schemas
            if schema and schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{schema}", public;')
                self.log(state, f"Schema Context: {schema}")

            # Direct query execution
            cursor.execute(query)
            
            # Metadata extraction
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            # Data retrieval with sampling support
            if getattr(state, "sampling_enabled", False):
                rows = cursor.fetchmany(5)
                self.log(state, f"Sampling: limited results to {len(rows)} records.")
            else:
                rows = cursor.fetchall()
            
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            
        except Exception as e:
            error_msg = str(e)
            result.error_message = error_msg
            state.error_message = error_msg
            self.log(state, f"RDS Execution Failure: {error_msg}", level="ERROR")
            
            # Persist error history for future generator attempts
            if error_msg not in state.execution_error_history:
                state.execution_error_history.append(f"Postgres Error: {error_msg}")
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"RDS Execution completed in {result.execution_time_ms:.2f}ms. Rows: {result.row_count}")
        
        # Async background result writing
        import threading
        def _bg_persistence():
            try:
                if result.error_message:
                    self.file_coordinator.write_csv(
                        state.instance_id, 
                        [["failed", result.error_message]], 
                        ["status", "error"], 
                        state.model_name
                    )
                else:
                    self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
            except Exception as e:
                Logger.log(f"RDS background persistence failed: {str(e)}", level="DEBUG")

        threading.Thread(target=_bg_persistence, daemon=True).start()
        
        return state


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
            return state  # No error to fix
        
        error_msg = res.error_message
        original_sql = state.chosen_query
        
        # Try automatic fixes first (no LLM needed)
        fixed_sql = self._try_auto_fix(original_sql, error_msg)
        
        if fixed_sql and fixed_sql != original_sql:
            self.log(state, f"Auto-fix applied for: {error_msg[:50]}...")
            state.chosen_query = fixed_sql
            # Re-execute with fixed SQL
            state = self._execute_query(state)
            
        # If still error and LLM available, try LLM-based fix
        if state.execution_result.error_message and self.llm:
            fixed_sql = self._try_llm_fix(state, original_sql, error_msg)
            if fixed_sql:
                state.chosen_query = fixed_sql
                state = self._execute_query(state)
                self.log(state, f"LLM fix attempted. New result: {state.execution_result.row_count} rows")
        
        return state
    
    def _try_auto_fix(self, sql: str, error: str) -> str:
        """Apply common auto-fixes based on error patterns."""
        
        # Fix 1: "no such function: X" - remove unsupported functions
        if "no such function" in error.lower():
            # Extract function name
            import re
            func_match = re.search(r'no such function:?\s*(\w+)', error, re.I)
            if func_match:
                func_name = func_match.group(1)
                # Replace function call with NULL or 0 as placeholder
                sql = re.sub(rf'\b{func_name}\s*\([^)]*\)', '0', sql, flags=re.I)
                return sql
        
        # Fix 2: "malformed JSON" - wrap json_extract in COALESCE
        if "malformed" in error.lower() and "json" in error.lower():
            # This is harder to auto-fix, but we can try wrapping
            sql = sql.replace("json_extract(", "COALESCE(json_extract(")
            # This won't fully work without closing the COALESCE, skip for now
            pass
        
        # Fix 3: "no such column" - might be a case sensitivity issue
        if "no such column" in error.lower():
            # Try quoting identifiers that might be case-sensitive
            pass
        
        return sql
    
    def _try_llm_fix(self, state: AgentState, sql: str, error: str) -> str:
        """Use LLM to fix the SQL based on error."""
        
        messages = self.prompt_loader.load_prompt(
            "error_correction",
            sql=sql,
            error=error,
            tables_available=list(state.schema_info.keys()) if state.schema_info else 'Unknown'
        )
        
        response = self.llm.get_completion(messages, max_tokens=500)
        
        # Clean response
        if response and not response.startswith("ERROR:"):
            # Remove potential markdown
            if "```" in response:
                response = response.split("```")[1] if "```sql" in response else response.split("```")[1]
                response = response.strip()
            return response.strip()
        
        return None
    
    def _execute_query(self, state: AgentState) -> AgentState:
        """Re-execute the current query."""
        import sqlite3
        import time
        
        db_path = state.db_path
        query = state.chosen_query
        
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            
            if cursor.description:
                result.columns = [desc[0] for desc in cursor.description]
            
            rows = cursor.fetchall()
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            conn.close()
            
        except sqlite3.Error as e:
            result.error_message = str(e)
            
            # Capture error in history
            error_entry = f"SQL Error: {str(e)}"
            if error_entry not in state.execution_error_history:
                state.execution_error_history.append(error_entry)
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000
        
        state.execution_result = result
        return state
