import os
import yaml

from core.agent_base import AgentState, BaseAgent
from core.file_coordinator import FileCoordinator
from core.llm_service import LLMService
from core.logger import Logger
from core.paths import DIALECT_RULES
from core.prompt_loader import PromptLoader
from core.utils import format_rag_columns, format_schema_to_str


class SQLBuilderAgent(BaseAgent):
    """Agent responsible for generating SQL queries."""

    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="SQLBuilder", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        """Executes the SQL generation workflow without historical leakage."""
        Logger.log_call(f"{self.name}.run", {"instance_id": state.instance_id})

        # 1. Schema Context (Context Expansion Strategy)
        target_schema = state.schema_info
        expansion_active = False
        if state.iteration_count > 2 and state.full_schema_info:
            target_schema = state.full_schema_info
            expansion_active = True
            self.log(state, "CONTEXT_EXPANSION: TableSelector may have missed tables. Using Full Schema.", level="WARN")

        schema_context = format_schema_to_str(target_schema) if target_schema else "No schema."

        # 2. Action Plan
        action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan)) if state.step_by_step_plan else "No plan."

        # 3. Dialect rules
        db_type = state.dialect
        with open(DIALECT_RULES) as f:
            all_rules = yaml.safe_load(f)
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules.get("instructions", "")

        # 4. Success/Failure Evidence
        previous_sql = state.chosen_query or ""
        previous_sql_label = "PREVIOUS SQL (FAILED ATTEMPT):" if previous_sql else ""

        from core.utils import format_execution_results
        execution_results = format_execution_results(state.execution_result) if state.execution_result else "No results."

        # --- COMPREHENSIVE FAILURE HISTORY (Issue 1/3) ---
        history_lines = []
        if state.execution_error_history:
            for i, (err, fback) in enumerate(zip(state.execution_error_history, state.feedback_history or [])):
                history_lines.append(f"--- ATTEMPT {i+1} ---\nERROR: {err}\nCRITIC: {fback}")
        
        failure_history = "\n\n".join(history_lines) if history_lines else "None."

        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            potential_pool=schema_context,
            previous_sql=previous_sql,
            previous_sql_label=previous_sql_label,
            execution_results=execution_results,
            failure_history=failure_history,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
        )

        # MANDATORY CORRECTION BLOCK
        latest_error = state.execution_error_history[-1] if state.execution_error_history else "None."
        latest_feedback = state.critic_feedback or "No previous logic-review."
        
        feedback_context = (
            f"\n\n### [MANDATORY RECOVERY PROTOCOL]\n"
            f"1. **Analyze History**: Look at ALL previous attempts below. Identify why they were rejected.\n"
            f"2. **Constraint Enforcement**: If an attempt failed due to a Specific Syntax Error, DO NOT use that exact syntax again.\n"
            f"3. **Consistency**: You are oscillating. Ensure this SQL solves the LATEST ERROR without re-introducing previous ones.\n\n"
            f"LATEST CRITIC FEEDBACK: {latest_feedback}\n"
            f"LATEST EXECUTION ERROR: {latest_error}\n"
            f"--------------------------------------------"
        )
        
        for msg in reversed(messages):
            if msg["role"] == "user":
                msg["content"] += feedback_context
                break

        response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)

        if response and isinstance(response, dict) and response.get("sql"):
            sql = response["sql"].replace("```sql", "").replace("```", "").strip()
            state.chosen_query = sql
            state.is_result_valid = True
            self.file_coordinator.write_sql(state.instance_id, sql.split("\n"), state.model_name)
        else:
            state.is_result_valid = False
            state.critic_feedback = "CRITICAL: SQL Generator returned malformed or non-dictionary response."

        return state


from .sql_critic import SQLCriticAgent


class RefinementLoopAgent(BaseAgent):
    """Orchestrator for the iterative SQL generation and correction process."""

    def __init__(self, llm_service: LLMService, executor: BaseAgent, config: dict = None):
        super().__init__(name="RefinementLoop", config=config)
        self.generator = SQLBuilderAgent(llm_service)
        self.critic = SQLCriticAgent(llm_service)
        self.max_retries = self.config.get("max_retries", 5)
        self.pivot_threshold = self.config.get("pivot_threshold", 2)
        from .query_planner import StepByStepPlannerAgent
        self.planner = StepByStepPlannerAgent(llm_service)
        self.executor = executor

    def run(self, state: AgentState) -> AgentState:
        for attempt in range(1, self.max_retries + 1):
            state.iteration_count = attempt
            if getattr(state, "stop_requested", False): break
            state = self.generator.run(state)
            if not state.is_result_valid: break
            state.sampling_enabled = True
            state = self.executor.run(state)
            if not getattr(state, "direct_mode", False):
                state = self.critic.run(state)
                if state.is_result_valid: break
                if attempt == self.pivot_threshold:
                    state = self.planner.run(state)
            else:
                break
        if state.is_result_valid:
            state.sampling_enabled = False
            state = self.executor.run(state)
        return state
