import os
import sqlite3
import psycopg2
import time
from google.cloud import bigquery
from google.oauth2 import service_account
from typing import Dict, Any, List, Optional
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.state import ExecutionResult
from tt_sql.core.prompt_loader import PromptLoader
from tt_sql.core.file_coordinator import FileCoordinator

class SQLiteExecutorAgent(BaseAgent):
    """
    Executes the chosen SQL query against the database.
    """
    def __init__(self, db_path: Optional[str] = None):
        super().__init__(name="SQLiteExecutor")
        self.file_coordinator = FileCoordinator()
        self.db_path = db_path
        
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Fetch real schema info for a specific table from local SQLite."""
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
        except:
            return {}

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            self.log(state, "No valid SQL query chosen to execute. Skipping database call.")
            return state

        db_path = state.db_path
        query = state.chosen_query
        
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Final sanity check: must start with SELECT, WITH, etc.
            if not any(query.upper().strip().startswith(kw) for kw in ["SELECT", "WITH", "PRAGMA", "EXPLAIN"]):
                 raise sqlite3.Error(f"String does not appear to be a valid SQL command: '{query[:50]}...'")

            cursor.execute(query)
            
            # Fetch columns
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            # Fetch rows
            if getattr(state, "sampling_enabled", False):
                rows = cursor.fetchmany(5)
                self.log(state, f"Sampling enabled: Fetched top {len(rows)} rows.")
            else:
                rows = cursor.fetchall()
            
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            
            conn.close()
            
        except sqlite3.Error as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"Execution Error: {e}")
            
            # Capture error in history for future iterations
            error_entry = f"SQL Error: {str(e)}"
            if error_entry not in state.execution_error_history:  # Avoid duplicates
                state.execution_error_history.append(error_entry)
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Executed query. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms")
        
        # Write CSV for all states (Parity with logs)
        if result.error_message:
            self.file_coordinator.write_csv(
                state.instance_id, 
                [["failed", result.error_message]], 
                ["status", "error"], 
                state.model_name
            )
            self.log(state, "Error CSV written.")
        else:
            self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
            self.log(state, f"CSV results written (Rows: {result.row_count}).")
        
        return state

class ResultValidatorAgent(BaseAgent):
    """
    Validates execution results.
    """
    def __init__(self):
        super().__init__(name="ResultValidator")

    def run(self, state: AgentState) -> AgentState:
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
    Executes SQL queries against an Amazon RDS PostgreSQL database.
    """
    def __init__(self):
        super().__init__(name="PostgresExecutor")
        self.file_coordinator = FileCoordinator()

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Fetch real schema info for a specific table from RDS."""
        host = os.getenv("RDS_HOST")
        database = os.getenv("RDS_DATABASE", "postgres")
        user = os.getenv("RDS_USER")
        password = os.getenv("RDS_PASSWORD")
        port = os.getenv("RDS_PORT", "5432")
        schema = os.getenv("SCHEMA", "public").strip().replace('"', '')
        
        conn = None
        try:
            conn = psycopg2.connect(
                host=host, database=database, user=user, password=password, port=port,
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
        except:
            if conn: conn.close()
            return {}

    def run(self, state: AgentState) -> AgentState:
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            self.log(state, "No valid SQL query chosen to execute. Skipping database call.")
            return state

        query = state.chosen_query
        
        # Load RDS credentials from environment
        host = os.getenv("RDS_HOST")
        database = os.getenv("RDS_DATABASE", "postgres")
        user = os.getenv("RDS_USER")
        password = os.getenv("RDS_PASSWORD")
        port = os.getenv("RDS_PORT", "5432")
        schema = os.getenv("SCHEMA", "public").strip().replace('"', '') # e.g., acme-chatbot

        start_t = time.time()
        result = ExecutionResult()
        
        conn = None
        try:
            # Establish connection
            conn = psycopg2.connect(
                host=host,
                database=database,
                user=user,
                password=password,
                port=port,
                connect_timeout=10
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Set schema (search_path)
            if schema and schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{schema}", public;')
                self.log(state, f"Search path set to: {schema}")

            # Execute query
            cursor.execute(query)
            
            # Fetch columns
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]
            
            # Fetch rows
            if getattr(state, "sampling_enabled", False):
                rows = cursor.fetchmany(5)
                self.log(state, f"Sampling enabled: Fetched top {len(rows)} rows.")
            else:
                rows = cursor.fetchall()
            
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"Postgres Execution Error: {e}")
            
            # Capture error in history for future iterations
            error_entry = f"Postgres Error: {str(e)}"
            if error_entry not in state.execution_error_history:
                state.execution_error_history.append(error_entry)
                
        finally:
            if conn:
                conn.close()
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Executed query on RDS. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms")
        
        # Write CSV results
        if result.error_message:
            self.file_coordinator.write_csv(
                state.instance_id, 
                [["failed", result.error_message]], 
                ["status", "error"], 
                state.model_name
            )
        else:
            self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        
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
        
    def run(self, state: AgentState) -> AgentState:
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
        
        response = self.llm.get_completion(messages, max_tokens=500, agent_name=self.name)
        
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

from ..core.bq_service import BigQueryService
from ..core.sf_service import SnowflakeService

class BigQueryExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Google BigQuery.
    """
    def __init__(self):
        super().__init__(name="BigQueryExecutor")
        self.file_coordinator = FileCoordinator()
        self.bq_service = BigQueryService()

    def run(self, state: AgentState) -> AgentState:
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            self.log(state, "No valid SQL query chosen to execute. Skipping database call.")
            return state

        query = state.chosen_query
        client = self.bq_service.get_client()

        start_t = time.time()
        result = ExecutionResult()

        try:
            # For BigQuery tasks, the dataset should ideally be prefixed in the SQL
            # If not, the public project might need to be explicitly set
            
            # Execute query
            query_job = client.query(query)
            rows = query_job.result() # Wait for job to complete
            
            # Fetch columns
            result.columns = [field.name for field in rows.schema]
            
            # Fetch rows
            all_rows = []
            for row in rows:
                all_rows.append(list(row.values()))
                
            if getattr(state, "sampling_enabled", False):
                result.rows = all_rows[:5]
                self.log(state, f"Sampling enabled: Fetched top {len(result.rows)} rows.")
            else:
                result.rows = all_rows
                
            result.row_count = len(all_rows)
            
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"BigQuery Execution Error: {e}")
            
            # Capture error in history
            error_entry = f"BigQuery Error: {str(e)}"
            if error_entry not in state.execution_error_history:
                state.execution_error_history.append(error_entry)
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Executed query on BigQuery. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms")
        
        # Write CSV results
        if result.error_message:
            self.file_coordinator.write_csv(
                state.instance_id, 
                [["failed", result.error_message]], 
                ["status", "error"], 
                state.model_name
            )
        else:
            self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        
        return state

class SnowflakeExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Snowflake.
    """
    def __init__(self):
        super().__init__(name="SnowflakeExecutor")
        self.file_coordinator = FileCoordinator()
        self.sf_service = SnowflakeService()

    def run(self, state: AgentState) -> AgentState:
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            self.log(state, "No valid SQL query chosen to execute. Skipping database call.")
            return state

        query = state.chosen_query
        
        # Snowflake database/schema routing
        database = state.db_name
        schema = "PUBLIC"
        if database and "." in database:
            parts = database.split(".")
            database = parts[0]
            schema = parts[1]

        conn = self.sf_service.get_connection(database=database, schema=schema)
        if not conn:
            self.log(state, "Failed to establish Snowflake connection.", level="ERROR")
            state.error_message = "Failed to establish Snowflake connection."
            return state

        start_t = time.time()
        result = ExecutionResult()

        try:
            cursor = conn.cursor()
            cursor.execute(query)
            
            # Fetch columns
            if cursor.description:
                result.columns = [desc[0] for desc in cursor.description]
            
            # Fetch rows
            if getattr(state, "sampling_enabled", False):
                rows = cursor.fetchmany(5)
                self.log(state, f"Sampling enabled: Fetched top {len(rows)} rows.")
            else:
                rows = cursor.fetchall()
            
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"Snowflake Execution Error: {e}")
            
            # Capture error in history
            error_entry = f"Snowflake Error: {str(e)}"
            if error_entry not in state.execution_error_history:
                state.execution_error_history.append(error_entry)
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Executed query on Snowflake. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms")
        
        # Write CSV results
        if result.error_message:
            self.file_coordinator.write_csv(
                state.instance_id, 
                [["failed", result.error_message]], 
                ["status", "error"], 
                state.model_name
            )
        else:
            self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
        
        return state
