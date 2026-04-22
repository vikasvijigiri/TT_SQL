import json
import re

from core.agent_base import AgentState, BaseAgent
from core.llm_service import LLMService
from core.prompt_loader import PromptLoader
from core.utils import format_schema_to_str


class TableSelectorAgent(BaseAgent):
    """Agent responsible for narrowing down the schema to relevant tables.

    This agent analyzes the user query and intent to identify which tables
    from the full database schema are necessary to answer the question,
    effectively pruning the context for the SQL generator.
    """

    def __init__(self, llm_service: LLMService, config: dict = None):
        """Initializes the TableSelectorAgent.

        Args:
            llm_service (LLMService): Service for interacting with LLM APIs.
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="TableSelector", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState) -> AgentState:
        """Executes the table selection workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The updated state with relevant_tables populated
                and schema_info pruned.
        """
        if not state.schema_info:
            self.log(
                state, "No schema info available to select tables from.", level="WARN"
            )
            return state

        if getattr(state, "use_rag", False) and len(state.schema_info) < 5:
            self.log(
                state,
                f"RAG already narrowed schema to {len(state.schema_info)} tables. Skipping selection.",
            )
            return state

        self.log(
            state, f"Starting table selection from {len(state.schema_info)} tables."
        )

        schema_str = format_schema_to_str(state.schema_info, detailed=False)

        prompt_vars = {
            "user_query": state.user_query,
            "intent_path": state.query_intent or "Not analyzed yet.",
            "kb_context": state.external_knowledge or "No external context provided.",
            "schema_path": schema_str,
        }

        self.log(state, f"PROMPT_VAR: intent_path={prompt_vars['intent_path']}")
        self.log(state, f"PROMPT_VAR: kb_context={prompt_vars['kb_context']}")
        schema_summary = schema_str[:100] + "..." if len(schema_str) > 100 else schema_str
        self.log(state, f"PROMPT_VAR: schema_path={schema_summary}")

        messages = self.prompt_loader.load_prompt("table_selector", **prompt_vars)

        try:
            response_text = self.llm.get_completion(
                messages, state=state, agent_name=self.name
            )
            state.last_raw_response = response_text

            json_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
            if json_match:
                response_json = json.loads(json_match.group(1))
            else:
                response_json = json.loads(response_text)

            selected_tables = response_json.get("relevant_tables", [])
            state.query_intent = response_json.get("intent", state.query_intent)
            state.complexity_score = response_json.get(
                "complexity", state.complexity_score
            )

            valid_tables = [t for t in selected_tables if t in state.schema_info]

            if valid_tables:
                state.relevant_tables = valid_tables
                self.log(
                    state,
                    f"Selected {len(valid_tables)} tables: {', '.join(valid_tables)}",
                )
                pruned_schema = {t: state.schema_info[t] for t in valid_tables}
                state.schema_info = pruned_schema
            else:
                self.log(
                    state,
                    "Failed to select valid tables. Falling back to full schema.",
                    level="WARN",
                )
                state.relevant_tables = list(state.schema_info.keys())

        except Exception as e:
            self.log(
                state,
                f"Table selection failed: {e}. Falling back to full schema.",
                level="ERROR",
            )
            state.relevant_tables = list(state.schema_info.keys())

        return state
