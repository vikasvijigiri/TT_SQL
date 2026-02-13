import sqlite3
import time
from ..core.agent_base import BaseAgent, AgentState
from ..core.state import ExecutionResult

from ..core.agent_base import BaseAgent, AgentState
from ..core.state import ExecutionResult
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator

class SQLiteExecutorAgent(BaseAgent):
    """
    Executes the chosen SQL query against the database.
    """
    def __init__(self):
        super().__init__(name="SQLiteExecutor")
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        if not state.chosen_query:
            self.log(state, "No query chosen to execute.")
            return state

        db_path = state.db_path
        query = state.chosen_query
        
        start_t = time.time()
        result = ExecutionResult()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
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
            self.log(state, f"Execution Error: {e}")
            
            # Capture error in history for future iterations
            error_entry = f"SQL Error: {str(e)}"
            if error_entry not in state.execution_error_history:  # Avoid duplicates
                state.execution_error_history.append(error_entry)
                
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(state, f"Executed query. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms")
        
        # Write execution results to file (for Critic and history)
        execution_data = {
            "columns": result.columns,
            "rows": result.rows,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "error_message": result.error_message
        }
        self.file_coordinator.write_execution(state.instance_id, execution_data, state.model_name)
        self.log(state, f"Execution results written to results/execution/{state.instance_id}.json")
        
        # Write CSV as well
        if result.rows:
            self.file_coordinator.write_csv(state.instance_id, result.rows, result.columns, state.model_name)
            self.log(state, f"CSV results written to results/csv/{state.instance_id}.csv")
        
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
