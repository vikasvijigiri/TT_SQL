import time
import threading
from typing import Optional
from app.domain.agents.base import BaseAgent
from app.schemas.agent_state import AgentState
from app.infrastructure.database.manager import DatabaseManager

class ExecutorAgent(BaseAgent):
    """
    Executes SQL queries against the active database using DatabaseManager.
    Handles results persistence and error tracking for refinement loops.
    """
    def __init__(self, **kwargs):
        super().__init__(name="SQLExecutor", **kwargs)

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query:
            self.log(state, "No query provided for execution.", level="WARNING")
            return state

        start_t = time.time()
        # Use unified manager for execution
        result = DatabaseManager.execute(state.chosen_query, user_slug=self.user_slug)
        
        # Hydrate execution metadata
        result.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = result

        if result.error_message:
            self.log(state, f"Execution Failure: {result.error_message}", level="ERROR")
            state.execution_error_history.append(f"SQL Error: {result.error_message}")
        else:
            self.log(state, f"Success: {result.row_count} records in {result.execution_time_ms:.2f}ms")
            
        # Asynchronous result persistence
        threading.Thread(target=self._persist_results, args=(state, result), daemon=True).start()
        
        return state

    def _persist_results(self, state: AgentState, result: any):
        # Result persistence handled by final orchestration layer or specialized service
        pass
