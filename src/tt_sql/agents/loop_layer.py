import os
from ..core.agent_base import BaseAgent, AgentState
from ..core.state import SubTaskResult
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from .execution_layer import SQLiteExecutorAgent
from .critic_layer import CriticAgent
from ..core.logger import Logger
from .generation_layer import MultiCandidateGeneratorAgent
from ..core.file_coordinator import FileCoordinator

class RefinementLoopAgent(BaseAgent):
    """
    Simple Generate → Execute → Critic loop with up to 5 retries.
    Builds the entire SQL in one shot (no sub-question iteration).
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="RefinementLoop")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        
        self.generator = MultiCandidateGeneratorAgent(llm_service)
        
        # Select executor based on DB_TYPE
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if db_type == "postgres" or db_type == "postgresql":
            from .execution_layer import PostgresExecutorAgent
            self.executor = PostgresExecutorAgent()
        else:
            from .execution_layer import SQLiteExecutorAgent
            self.executor = SQLiteExecutorAgent()
            
        self.critic = CriticAgent(llm_service)
        self.file_coordinator = FileCoordinator()
        self.max_retries = 5

    def run(self, state: AgentState) -> AgentState:
        # 0. Clear existing context for a fresh instance
        if state.instance_id:
            sql_p = self.file_coordinator.get_sql_path(state.instance_id, state.model_name)
            # fb_p = self.file_coordinator.get_feedback_path(...) - REMOVED
            if os.path.exists(sql_p): os.remove(sql_p)
            # if os.path.exists(fb_p): os.remove(fb_p)
            
            # if state.schema_info:
            #     self.file_coordinator.write_schema(...) - REMOVED

        # Clear all history for fresh start
        state.history = []
        state.subtask_history = []
        state.execution_error_history = []
        state.sampling_enabled = False  # Full execution, no sampling

        self.log(state, f"Starting refinement loop (max {self.max_retries} attempts).")
        Logger.log_divider()

        for attempt in range(1, self.max_retries + 1):
            if getattr(state, "stop_requested", False):
                self.log(state, "Stop requested. Halting refinement loop.")
                break

            # Iteration header
            Logger.log_title(f"Iteration {attempt} / {self.max_retries}")

            # 1. Generate SQL
            Logger.log_title("SQLBuilder")
            state = self.generator.run(state)

            # Guard: skip if SQL is too large
            sql_len = len(state.chosen_query or "")
            if sql_len > 5000:
                self.log(state, f"Warning: SQL too large ({sql_len} chars). Skipping.")
                state.is_result_valid = False
                break

            # 2. Execute SQL with sampling for Critic
            Logger.log_title("DatabaseExecutor (Sampling)")
            state.sampling_enabled = True
            state = self.executor.run(state)

            # 3. Critic validates SQL logic and execution results
            if state.execution_result and state.execution_result.error_message:
                self.log(state, f"EXECUTION FAILED on attempt {attempt}: {state.execution_result.error_message}")
                # We do NOT skip the critic now; we let it analyze the error.
            
            Logger.log_title("SQLCritic")
            state = self.critic.run(state)
                
            # If Critic approves, do final full execution to save full CSV
            if state.is_result_valid:
                self.log(state, f"SUCCESS: Validated by Critic on attempt {attempt}. Executing full query to save outputs.")
                Logger.log_title("DatabaseExecutor (Full)")
                state.sampling_enabled = False
                state = self.executor.run(state)
                
                if not state.execution_result.error_message:
                    Logger.log_divider()
                    break
                else:
                    # Edge case: sampled execution passed, but full execution failed 
                    self.log(state, f"FINAL FULL EXECUTION FAILED: {state.execution_result.error_message}")
                    state.is_result_valid = False

            # 4. If invalid (Critic or Execution failure), pass feedback back to Builder
            feedback = ""
            if state.critic_feedback:
                feedback += f"CRITIC FEEDBACK:\n{state.critic_feedback}\n"
            
            if state.execution_result and state.execution_result.error_message:
                feedback += f"EXECUTION ERROR:\n{state.execution_result.error_message}\n"
            
            state.history = [{
                "role": "user",
                "content": feedback
            }]

            if attempt == self.max_retries:
                self.log(state, f"Max retries ({self.max_retries}) reached. Pipeline failed.")

            Logger.log_divider()

        return state
