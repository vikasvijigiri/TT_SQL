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
    """Agent responsible for generating SQL queries.

    This agent takes the execution plan, the narrowed schema context,
    and any previous feedback to generate a syntactically correct and
    logically sound SQL query for the target database dialect.
    """

    def __init__(self, llm_service: LLMService, config: dict = None):
        """Initializes the SQLBuilderAgent.

        Args:
            llm_service (LLMService): Service for interacting with LLM APIs.
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="SQLBuilder", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        """Executes the SQL generation workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The updated state containing the chosen_query.
        """
        Logger.log_call(f"{self.name}.run", {"instance_id": state.instance_id})

        # Schema Context
        if state.rag_columns:
            schema_context = format_rag_columns(state.rag_columns)
        elif state.schema_info:
            schema_context = format_schema_to_str(state.schema_info)
        else:
            schema_context = "Schema not available."

        # Action Plan
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(
                f"  {i + 1}. {s}" for i, s in enumerate(state.step_by_step_plan)
            )

        # Dialect
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if state.instance_id.startswith("bq"):
            db_type = "bigquery"

        with open(DIALECT_RULES) as f:
            all_rules = yaml.safe_load(f)
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules.get(
            "instructions", rules.get("generator_instructions", "")
        )

        previous_sql = state.chosen_query or ""
        previous_sql_label = (
            "PREVIOUS SQL (HAS ERRORS - FIX THEM):" if previous_sql else ""
        )

        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            potential_pool=schema_context,
            previous_sql=previous_sql,
            previous_sql_label=previous_sql_label,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
        )

        # Add feedback from history if present
        if state.history:
            feedback_raw = state.history[-1].get("content", "")
            if isinstance(feedback_raw, list):
                feedback_str = "\n".join(f"- {item}" for item in feedback_raw)
            else:
                feedback_str = str(feedback_raw)

            extra_context = (
                "\n\nCRITIC FEEDBACK (YOU MUST FIX ALL ISSUES BELOW):\n" + feedback_str
            )
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] += extra_context
                    break

        response = self.llm.get_json_completion(
            messages, state=state, agent_name=self.name
        )

        if response and response.get("sql"):
            sql = response["sql"].replace("```sql", "").replace("```", "").strip()
            state.chosen_query = sql
            state.is_result_valid = True

            sql_lines = [line for line in sql.split("\n") if line.strip()]
            self.file_coordinator.write_sql(
                state.instance_id, sql_lines, state.model_name
            )
            self.log(state, f"Generated SQL ({len(sql)} chars)")
        else:
            self.log(state, "Failed to generate SQL.", level="ERROR")
            state.is_result_valid = False

        return state


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
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if state.instance_id.startswith("bq"):
            db_type = "bigquery"
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
            verdict = response.get("verdict", "FAIL").upper()
            feedback = response.get("feedback", "No feedback provided.")

            state.is_result_valid = verdict == "PASS"
            state.critic_feedback = feedback

            self.log(state, f"Critic Verdict: {verdict}")
            if not state.is_result_valid:
                self.log(state, f"Critic Feedback: {feedback[:100]}...")
        else:
            self.log(
                state,
                "Critic failed to respond. Assuming valid to prevent loop.",
                level="WARN",
            )
            state.is_result_valid = True

        return state


class RefinementLoopAgent(BaseAgent):
    """Orchestrator for the iterative SQL generation and correction process.

    This agent manages the structural flow between the SQLBuilder,
    SQLCritic, and Executor. It retries generation multiple times if the
    critic finds issues, ensuring high-quality output.
    """

    def __init__(
        self, llm_service: LLMService, executor: BaseAgent, config: dict = None
    ):
        """Initializes the RefinementLoopAgent.

        Args:
            llm_service (LLMService): Service for interacting with LLM APIs.
            executor (BaseAgent): Database-specific executor agent for final validation.
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="RefinementLoop", config=config)
        self.generator = SQLBuilderAgent(llm_service)
        self.critic = SQLCriticAgent(llm_service)
        self.executor = executor
        self.max_retries = 5

    def run(self, state: AgentState) -> AgentState:
        """Executes the refinement loop workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The final state after iterative refinement and final execution.
        """
        self.log(state, f"Starting refinement loop (max {self.max_retries} attempts).")

        for attempt in range(1, self.max_retries + 1):
            if getattr(state, "stop_requested", False):
                break

            Logger.log_title(f"Iteration {attempt} / {self.max_retries}")

            # 1. Generate
            state = self.generator.run(state)
            if not state.is_result_valid:
                break

            # 2. Critic
            if not getattr(state, "direct_mode", False):
                state = self.critic.run(state)
                if state.is_result_valid:
                    self.log(state, f"Validated on attempt {attempt}.")
                    break

                # Feedback for next cycle
                state.history = [{"role": "user", "content": state.critic_feedback}]
            else:
                self.log(state, "Direct mode: skipping critic.")
                break

        # 3. Final Execution
        Logger.log_title("Final Execution")
        state = self.executor.run(state)
        return state
