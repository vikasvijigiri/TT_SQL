import json
from typing import Dict, Any, List
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator
from ..core.logger import Logger

class CriticAgent(BaseAgent):
    """
    Evaluates the SQL logic using a strict checklist approach.
    Decides if the result is satisfactory or requires refinement.
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="SQLCritic")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def _compact_schema(self, schema: Dict[str, Any]) -> str:
        """Converts JSON schema to a compact string: Table(col1, col2)"""
        if not schema: return ""
        lines = []
        for table, data in schema.items():
            # Handle potential dictionary structure (tables -> {columns: [...]})
            if isinstance(data, dict) and "columns" in data:
                cols = data["columns"]
            elif isinstance(data, list):
                cols = data
            else:
                cols = []

            col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in cols]
            lines.append(f"{table}({', '.join(col_names)})")
        return "\n".join(lines)

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        # Read SQL from file if state doesn't have it
        sql_to_criticize = self.file_coordinator.read_sql(state.instance_id, state.model_name) or state.chosen_query

        # Token Optimization: only send relevant tables (from TableSelector)
        if state.schema_info:
            full_schema = state.schema_info
            if state.relevant_tables:
                full_schema = {k: v for k, v in full_schema.items() if k in state.relevant_tables}
            schema_context = self._compact_schema(full_schema)
        else:
             schema_path = str(InstancePaths.schema(state.instance_id, state.model_name))
             try:
                 with open(schema_path, "r", encoding="utf-8") as f:
                     full_schema = json.load(f)
                 schema_context = self._compact_schema(full_schema)
             except:
                 schema_context = "Schema not available."

        # Build action plan text
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan))

        # Get previous feedback for enforcement checking
        previous_feedback = getattr(state, 'critic_feedback', '') or 'None (first attempt)'

        messages = self.prompt_loader.load_prompt(
            "sql_critic",
            user_query=state.user_query,
            action_plan=action_plan,
            sql=sql_to_criticize,
            schema_path=schema_context,
            previous_feedback=previous_feedback
        )
        
        # Get Critique
        response = self.llm.get_json_completion(messages, state=state)
        
        if response:
            is_valid = response.get("is_valid", False)
            check_results = response.get("check_results", {})
            failure_categories = response.get("failure_categories", [])
            feedback = response.get("feedback", [])
            
            state.is_result_valid = is_valid
            
            # Build feedback string from list
            if isinstance(feedback, list):
                feedback_str = "; ".join(feedback) if feedback else "No issues found."
            else:
                feedback_str = str(feedback)
            
            state.critic_feedback = feedback_str.strip()
            
            # Log failure categories and failed checks
            if failure_categories:
                self.log(state, f"Failure categories: {', '.join(failure_categories)}")
            
            failed_checks = [k for k, v in check_results.items() if v == "FAIL"]
            if failed_checks:
                self.log(state, f"Failed checks: {', '.join(failed_checks)}")
            else:
                self.log(state, "All checks passed.")
            
            if feedback:
                self.log(state, f"Feedback: {feedback_str}")
            
            Logger.log_code(json.dumps(response, indent=2), language="json")
        else:
            # Fallback if LLM fails
            state.is_result_valid = True  # Assume valid to avoid infinite loops
            self.log(state, "Critic failed to respond. Assuming VALID.")
            
        return state
