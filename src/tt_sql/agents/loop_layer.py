import os
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.state import SubTaskResult
from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader
from .execution_layer import SQLiteExecutorAgent
from .critic_layer import CriticAgent
from tt_sql.core.logger import Logger
from .generation_layer import MultiCandidateGeneratorAgent
from tt_sql.core.file_coordinator import FileCoordinator

class RefinementLoopAgent(BaseAgent):
    """
    Simple Generate → Execute → Critic loop with up to 5 retries.
    Builds the entire SQL in one shot (no sub-question iteration).
    """
    def __init__(self, llm_service: LLMService, executor: BaseAgent = None, config: dict = None):
        super().__init__(name="RefinementLoop", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        
        self.generator = MultiCandidateGeneratorAgent(llm_service)
        
        # Use provided executor or fallback to DB_TYPE based one
        if executor:
            self.executor = executor
        else:
            db_type = os.getenv("DB_TYPE", "sqlite").lower()
            if db_type == "postgres" or db_type == "postgresql":
                from .execution_layer import PostgresExecutorAgent
                self.executor = PostgresExecutorAgent()
            elif db_type == "bigquery":
                from .execution_layer import BigQueryExecutorAgent
                self.executor = BigQueryExecutorAgent()
            elif db_type == "snowflake":
                from .execution_layer import SnowflakeExecutorAgent
                self.executor = SnowflakeExecutorAgent()
            else:
                from .execution_layer import SQLiteExecutorAgent
                self.executor = SQLiteExecutorAgent()
            
        self.critic = CriticAgent(llm_service)
        self.file_coordinator = FileCoordinator()
        
        # Load max_retries from config
        import yaml
        from ..core.paths import PIPELINE_CONFIG
        with open(PIPELINE_CONFIG, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
            self.max_retries = pipeline_cfg.get("defaults", {}).get("max_retries", 5)

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

            if not state.is_result_valid or not state.chosen_query:
                self.log(state, "Generator failed to produce a valid query candidate.", level="ERROR")
                # We can either break or continue if we want to retry but usually fatal
                break

            # Guard: skip if SQL is too large
            sql_len = len(state.chosen_query or "")
            if sql_len > 5000:
                self.log(state, f"Warning: SQL too large ({sql_len} chars). Skipping.")
                state.is_result_valid = False
                break

            # 2. Critic validates SQL logic (NO execution yet)
            Logger.log_title("SQLCritic")
            state = self.critic.run(state)

            # 3. Check if validated
            if state.is_result_valid:
                self.log(state, f"VALIDATED on attempt {attempt}.")
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
        Logger.log_title("Final Execution")
        Logger.log_title("DatabaseExecutor")
        state = self.executor.run(state)

        return state
