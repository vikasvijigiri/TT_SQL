import json
import os
from typing import Dict, Any, List
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader
from tt_sql.core.file_coordinator import FileCoordinator
from tt_sql.core.logger import Logger
from .input_layer import format_rag_columns, format_schema_to_str
import yaml
from tt_sql.core.paths import DIALECT_RULES

class CriticAgent(BaseAgent):
    """
    Evaluates the SQL logic using a strict checklist approach.
    Decides if the result is satisfactory or requires refinement.
    """
    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="SQLCritic", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def _format_execution_results(self, result: Any) -> str:
        """Formats ExecutionResult into a readable table for the critic."""
        if not result:
            return "No execution results available."
        
        # Check for error in ExecutionResult object
        if hasattr(result, 'error_message') and result.error_message:
            return f"Execution Error: {result.error_message}"
        
        # Handle rows/columns
        rows = getattr(result, 'rows', [])
        cols = getattr(result, 'columns', [])
        
        if not rows:
            return "Query executed successfully but returned 0 rows."
        
        # Sample for display
        sample = rows[:5]
        
        if cols:
            header = " | ".join(cols)
            row_strs = [" | ".join(str(v) for v in row) for row in sample]
            return f"{header}\n" + "-" * len(header) + "\n" + "\n".join(row_strs)
        else:
            return "\n".join([" | ".join(str(v) for v in row) for row in sample])


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

            col_names = [c.get("column_name", c.get("name", c)) if isinstance(c, dict) else str(c) for c in cols]
            lines.append(f"{table}({', '.join(col_names)})")
        return "\n".join(lines)

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        # Read SQL from file if state doesn't have it
        sql_to_criticize = self.file_coordinator.read_sql(state.instance_id, state.model_name) or state.chosen_query

        # Schema Context Selection: Use RAG columns if available, otherwise fallback to full schema_info
        if state.rag_columns:
            schema_context = format_rag_columns(state.rag_columns)
        elif state.schema_info:
            schema_context = format_schema_to_str(state.schema_info)
        else:
            self.log(state, "WARNING: No schema info available — schema context is empty.", level="WARN")
            schema_context = "Schema not available."

        # Build action plan text
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan))

        # Get previous feedback for enforcement checking
        previous_feedback = getattr(state, 'critic_feedback', '') or 'None (first attempt)'

        # Dialect Detection
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if state.instance_id.startswith("bq"): db_type = "bigquery"
        
        with open(DIALECT_RULES, 'r') as f:
            all_rules = yaml.safe_load(f)
            
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules["critic_instructions"]

        # Format Execution Results
        execution_results = self._format_execution_results(state.execution_result)

        # Potential Pool (Context Enrichment)
        potential_pool = "No additional contextual columns available."
        if state.rag_columns:
            potential_pool = format_rag_columns(state.rag_columns)

        messages = self.prompt_loader.load_prompt(
            "sql_critic",
            user_query=state.user_query,
            action_plan=action_plan,
            sql=sql_to_criticize,
            schema_path=schema_context,
            execution_results=execution_results,
            potential_pool=potential_pool,
            previous_feedback=previous_feedback,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
            agent_role=self.role,
            agent_task=self.task
        )
        
        # Get Critique
        response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
        
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
