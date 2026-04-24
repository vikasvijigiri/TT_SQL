import yaml

from core.agent_base import AgentState, BaseAgent
from core.llm_service import LLMService
from core.logger import Logger
from core.paths import DIALECT_RULES
from core.prompt_loader import PromptLoader


class SQLCriticAgent(BaseAgent):
    """Agent responsible for reviewing and validating generated SQL queries.

    This agent acts as a judge, comparing the proposed SQL against the user
    query, schema, and execution results.
    """

    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="SQLCritic", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState) -> AgentState:
        # RESET local state signals for this iteration
        state.is_result_valid = False
        state.critic_feedback = ""

        if not state.chosen_query:
            state.critic_feedback = "No SQL query provided for review."
            return state

        Logger.log_call(f"{self.name}.run")

        # Dialect rules
        db_type = state.dialect
        with open(DIALECT_RULES) as f:
            all_rules = yaml.safe_load(f)
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules.get(
            "critic_instructions", rules.get("instructions", "")
        )

        from core.utils import format_execution_results, format_schema_to_str

        schema_context = format_schema_to_str(state.schema_info)
        execution_results = "No execution results available yet."
        if state.execution_result:
            execution_results = format_execution_results(state.execution_result)

        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(
                f"  {i + 1}. {s}" for i, s in enumerate(state.step_by_step_plan)
            )

        # CUMULATIVE FEEDBACK HISTORY
        feedback_history = "None."
        if state.feedback_history:
            history_lines = [f"Attempt {i+1}: {fback}" for i, fback in enumerate(state.feedback_history)]
            feedback_history = "\n".join(history_lines)

        messages = self.prompt_loader.load_prompt(
            "sql_critic",
            user_query=state.user_query,
            action_plan=action_plan,
            sql=state.chosen_query,
            execution_results=execution_results,
            schema_path=schema_context,
            potential_pool=schema_context,
            previous_feedback=feedback_history,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
        )

        response = self.llm.get_json_completion(
            messages, state=state, agent_name=self.name
        )

        is_valid = False
        feedback = "[CRITICAL]: Failed to get logic-review from Critic LLM."

        if response and isinstance(response, dict):
            is_valid = response.get("is_valid", False)
            feedback = response.get("feedback", "No feedback provided.")
        elif response:
            feedback = "[CRITICAL]: Critic returned a non-dictionary response. Retrying logic check."

        # --- HIGH-PRIORITY: SYNTAX/EXECUTION ERROR OVERRIDE ---
        if state.execution_result and state.execution_result.error_message:
            is_valid = False
            feedback = f"[CRITICAL_SYNTAX_ERROR]: Your SQL failed. Error: {state.execution_result.error_message}. Fix this immediately."
            self.log(state, "Prioritizing syntax error over logic.", level="WARN")

        # --- GHOST DATA GUARD (Issue 5 Refinement) ---
        elif is_valid and state.execution_result:
            row_count = state.execution_result.row_count
            if row_count == 0:
                # Only fail if it's not the final attempt and not explicitly accepted
                if state.iteration_count < 5 and "expected" not in feedback.lower() and "no data" not in feedback.lower():
                    is_valid = False
                    feedback = "[NULL_RESULT_AUDIT]: The query returned 0 rows. This is often a logical failure (e.g., case-sensitivity mismatch or wrong join). Verify if data exists for these filters."
                else:
                    self.log(state, "Empty result accepted as potentially valid.", level="INFO")

            elif row_count > 0:
                first_row = state.execution_result.rows[0]
                meaningless = ["", "none", "null", "[]", "{}", "nan"]
                if all(v is None or str(v).strip().lower() in meaningless for v in first_row):
                    # Ghost data (all nulls) is almost always a failure
                    if state.iteration_count < 5:
                        is_valid = False
                        feedback = "[GHOST_DATA_AUDIT]: Result contains only empty/null values. Logical failure likely on Join keys."

        state.is_result_valid = is_valid
        state.critic_feedback = feedback
        state.feedback_history.append(feedback)
        
        self.log(state, f"Critic Outcome: {'PASS' if is_valid else 'FAIL'}")
        return state
