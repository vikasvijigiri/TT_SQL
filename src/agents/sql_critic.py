import os

import yaml

from core.agent_base import AgentState, BaseAgent
from core.llm_service import LLMService
from core.paths import DIALECT_RULES
from core.prompt_loader import PromptLoader
from core.utils import format_schema_to_str


class SQLCriticAgent(BaseAgent):
    """Agent responsible for auditing and validating generated SQL.

    This agent reviews the generated SQL against the user query, the plan,
    and the schema. It provides binary validation (pass/fail) and detailed
    natural language feedback for refinement.
    """

    def __init__(self, llm_service: LLMService, config: dict = None):
        """Initializes the SQLCriticAgent.

        Args:
            llm_service (LLMService): Service for interacting with LLM APIs.
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="SQLCritic", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState) -> AgentState:
        """Executes the SQL auditing workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The updated state containing is_result_valid and critic_feedback.
        """
        if not state.chosen_query:
            return state

        schema_str = (
            format_schema_to_str(state.schema_info) if state.schema_info else "N/A"
        )

        # Preparation for prompt
        db_type = state.dialect
        with open(DIALECT_RULES) as f:
            all_rules = yaml.safe_load(f)
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules.get(
            "critic_instructions", rules.get("instructions", "")
        )

        action_plan = (
            "\n".join(f"- {s}" for s in state.step_by_step_plan)
            if state.step_by_step_plan
            else "N/A"
        )
        schema_path = (
            format_schema_to_str(state.schema_info) if state.schema_info else "N/A"
        )
        potential_pool = schema_path  # Simplification: same as schema
        execution_results = "No execution data yet."
        if state.execution_result and state.execution_result.rows:
            execution_results = str(state.execution_result.rows[:5])

        previous_feedback = state.critic_feedback if state.critic_feedback else "None"

        self.log(
            state, f"PROMPT_VAR: execution_results={str(execution_results)[:100]}..."
        )
        self.log(
            state, f"PROMPT_VAR: previous_feedback={str(previous_feedback)[:100]}..."
        )

        messages = self.prompt_loader.load_prompt(
            "sql_critic",
            agent_role="Expert SQL Logic Auditor",
            agent_task="Review the following SQL query for logical correctness, schema consistency, and intent alignment.",
            user_query=state.user_query,
            action_plan=action_plan,
            sql=state.chosen_query,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
            schema_path=schema_path,
            potential_pool=potential_pool,
            execution_results=execution_results,
            previous_feedback=previous_feedback,
        )

        response = self.llm.get_json_completion(
            messages, state=state, agent_name=self.name
        )

        if response:
            is_valid = response.get("is_valid", False)
            feedback = response.get("feedback", "No feedback provided.")

            state.is_result_valid = is_valid
            state.critic_feedback = feedback

            verdict_str = "PASS" if is_valid else "FAIL"
            self.log(state, f"Critic Verdict: {verdict_str}")
            if not state.is_result_valid:
                self.log(state, f"Critic Feedback: {str(feedback)[:100]}...")
        else:
            self.log(
                state,
                "Critic failed to respond. Assuming valid to prevent loop.",
                level="WARN",
            )
            state.is_result_valid = True

        return state
