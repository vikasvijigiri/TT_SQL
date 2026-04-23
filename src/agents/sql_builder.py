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
        db_type = state.dialect

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

        self.log(state, f"PROMPT_VAR: action_plan={action_plan[:200]}...")
        schema_sum = str(schema_context)[:100] + "..." if len(str(schema_context)) > 100 else str(schema_context)
        self.log(state, f"PROMPT_VAR: schema_path={schema_sum}")

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


from .sql_critic import SQLCriticAgent


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
