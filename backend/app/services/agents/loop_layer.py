import os
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.agents.critic_layer import CriticAgent
from app.services.utils.logger import Logger
from app.services.agents.generation_layer import MultiCandidateGeneratorAgent
from app.repositories.persistence.file_coordinator import FileCoordinator
from app.services.agents.input_layer import format_rag_columns
from app.repositories.config import settings

def _is_clean_success(state: AgentState, attempt: int) -> bool:
    """
    Returns True if execution produced rows with no error â€” Critic can be skipped.
    Only applies on attempt 1 (no previous failures to validate against).
    """
    if attempt != 1:
        return False
    er = state.execution_result
    if not er:
        return False
    if er.error_message:
        return False
    if not er.rows or len(er.rows) == 0:
        return False
    return True


class RefinementLoopAgent(BaseAgent):
    """
    RefinementLoopAgent orchestrates the iterative SQL generation, execution, and 
    criticism cycle. It implements a self-healing loop that attempts to resolve
    execution errors through automated feedback and candidate regeneration.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="RefinementLoop", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        
        # Initialize internal agent components
        self.generator = MultiCandidateGeneratorAgent(
            llm_service, results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug
        )

        # Executor is resolved dynamically in run() based on current settings.DB_TYPE
        self.executor = None
        self._results_dir = results_dir
        self._logs_dir = logs_dir
        self._metadata_dir = metadata_dir

        self.critic = CriticAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)
        self.max_retries = 1

    def run(self, state: AgentState, on_token: callable = None, on_intermediate: callable = None) -> AgentState:
        """
        Executes the iterative refinement cycle.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            on_intermediate (callable, optional): Callback for capturing intermediate results.
            
        Returns:
            AgentState: The updated state after successful refinement or max retries.
        """
        # Resolve executor dynamically based on current active project's DB type
        db_type = settings.DB_TYPE.lower()
        if db_type in ["postgres", "postgresql"]:
            from app.services.agents.execution_layer import PostgresExecutorAgent
            self.executor = PostgresExecutorAgent(
                results_dir=self._results_dir, logs_dir=self._logs_dir, metadata_dir=self._metadata_dir, user_slug=self.user_slug
            )
        elif db_type == "bigquery":
            from app.services.agents.execution_layer import BigQueryExecutorAgent
            self.executor = BigQueryExecutorAgent(
                results_dir=self._results_dir, logs_dir=self._logs_dir, metadata_dir=self._metadata_dir, user_slug=self.user_slug
            )
        elif db_type == "snowflake":
            from app.services.agents.execution_layer import SnowflakeExecutorAgent
            self.executor = SnowflakeExecutorAgent(
                results_dir=self._results_dir, logs_dir=self._logs_dir, metadata_dir=self._metadata_dir, user_slug=self.user_slug
            )
        else:
            from app.services.agents.execution_layer import SQLiteExecutorAgent
            self.executor = SQLiteExecutorAgent(
                results_dir=self._results_dir, logs_dir=self._logs_dir, metadata_dir=self._metadata_dir, user_slug=self.user_slug
            )

        try:
            # Initialize loop context
            if not state.history:
                 state.history = []
            state.subtask_history = []
            state.execution_error_history = []
            state.sampling_enabled = False

            self.log(state, f"Starting refinement loop (max {self.max_retries} attempts).")
            Logger.log_divider()

            has_narrated_intermediate = False

            for attempt in range(1, self.max_retries + 1):
                if getattr(state, "stop_requested", False):
                    self.log(state, "Stop requested. Halting refinement loop.")
                    break

                Logger.log_title(f"Iteration {attempt} / {self.max_retries}")

                # 1. SQL Generation Phase
                Logger.log_title("SQLBuilder")
                state = self.generator.run(state, on_token=on_token)

                # Validation: Prevent excessive resource consumption
                sql_len = len(state.chosen_query or "")
                if sql_len > 5000:
                    self.log(state, f"Refinement Aborted: SQL query size ({sql_len} chars) exceeds safety limits.", level="ERROR")
                    state.is_result_valid = False
                    break

                # 2. Database Execution Phase
                Logger.log_title("DatabaseExecutor")
                state.sampling_enabled = False
                state = self.executor.run(state, on_token=on_token)

                # Narrative Hook: Trigger intermediate business logic if results are found
                # We narrates on iteration 1 or if insights haven't been shared yet
                if on_intermediate and callable(on_intermediate) and state.execution_result and state.execution_result.rows:
                    if not has_narrated_intermediate or attempt > 1:
                        self.log(state, f"Summarizing insights from {state.execution_result.row_count} records (Iteration {attempt}).")
                        on_intermediate(state)
                        has_narrated_intermediate = True

                # 3. Fast-Path Optimization: Skip Critic on clean initial success
                if _is_clean_success(state, attempt):
                    self.log(state, "Fast Path Triggered: Clean execution on attempt 1. Critic phase bypassed.")
                    state.is_result_valid = True
                    state.critic_feedback = ""
                    Logger.log_divider()
                    break

                # 4. Critique & Feedback Phase
                if state.execution_result and state.execution_result.error_message:
                    self.log(state, f"Iteration {attempt} Failed: {state.execution_result.error_message}", level="WARNING")

                Logger.log_title("SQLCritic")
                state = self.critic.run(state, on_token=on_token)

                if state.is_result_valid:
                    self.log(state, f"Validation Successful: Query confirmed by Critic on attempt {attempt}.")
                    if not state.execution_result.error_message:
                        Logger.log_divider()
                        break
                    else:
                        self.log(state, f"Inconsistency Detected: Critic approved a failing query.", level="ERROR")
                        state.is_result_valid = False

                # 5. Iterative Context Management
                feedback_lines = []
                if state.critic_feedback:
                    feedback_lines.append(f"CRITIC FEEDBACK:\n{state.critic_feedback}")
                if state.execution_result and state.execution_result.error_message:
                    feedback_lines.append(f"EXECUTION ERROR:\n{state.execution_result.error_message}")
                
                state.history = [{"role": "user", "content": "\n".join(feedback_lines)}]

                if attempt == self.max_retries:
                    self.log(state, "Refinement Loop Limit reached. Proceeding with best-effort state.", level="WARNING")

                Logger.log_divider()

        except Exception as e:
            self.log(state, f"Refinement Loop Exception: {str(e)}", level="ERROR")
            state.is_result_valid = False
            
        return state

