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
            try:
                with open(Logger._log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n## 🔄 Iteration {attempt} / {self.max_retries}\n\n")
            except: pass

            # 1. Generate SQL
            try:
                with open(Logger._log_file, "a", encoding="utf-8") as f:
                    f.write(f"### 🔨 SQLBuilder\n\n")
            except: pass
            state = self.generator.run(state)

            # Guard: skip if SQL is too large
            sql_len = len(state.chosen_query or "")
            if sql_len > 5000:
                self.log(state, f"⚠️ SQL too large ({sql_len} chars). Skipping.")
                state.is_result_valid = False
                break

            # 2. Critic validates SQL logic (NO execution yet)
            try:
                with open(Logger._log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n### 🔍 SQLCritic\n\n")
            except: pass
            state = self.critic.run(state)

            # 3. Check if validated
            if state.is_result_valid:
                self.log(state, f"✅ VALIDATED on attempt {attempt}.")
                Logger.log_divider()
                break

            # 4. Pass Critic feedback to Builder for next attempt
            state.history = [{
                "role": "user",
                "content": state.critic_feedback
            }]

            if attempt == self.max_retries:
                self.log(state, f"Max retries ({self.max_retries}) reached. Using last attempt.")

            Logger.log_divider()

        # 5. Execute SQL ONLY after critic approves (or max retries)
        try:
            with open(Logger._log_file, "a", encoding="utf-8") as f:
                f.write(f"## ▶️ Final Execution\n\n### 💾 SQLiteExecutor\n\n")
        except: pass
        state = self.executor.run(state)

        return state
