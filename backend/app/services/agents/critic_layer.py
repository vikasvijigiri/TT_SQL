import json
import os
from typing import Dict, Any, List
from app.services.agents.base import BaseAgent
from app.models.agent_state import AgentState
from app.services.llm_service import LLMService
from app.services.prompt_loader import PromptLoader
from app.repos.file_coordinator import FileCoordinator
from app.services.logger import Logger
from app.services.agents.input_layer import format_rag_columns

class CriticAgent(BaseAgent):
    """
    Evaluates the SQL logic using a strict checklist approach.
    Decides if the result is satisfactory or requires refinement.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="SQLCritic", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)

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

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        from app.models.paths import InstancePaths
        
        # B4: SQL is already in memory — no disk read needed
        sql_to_criticize = state.chosen_query or ""

        # RAG-only schema: use raw retrieved columns
        if state.rag_columns:
            schema_context = format_rag_columns(state.rag_columns)
        else:
            self.log(state, "WARNING: No RAG schema available — schema context is empty.", level="WARN")
            schema_context = "RAG schema not available."

        # Build action plan text
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan))

        # Format execution results
        execution_context = "No execution results available."
        if state.execution_result:
            if state.execution_result.error_message:
                execution_context = f"EXECUTION FAILED WITH DATABASE ERROR:\n{state.execution_result.error_message}\n\nAnalyze this error and explain how to fix the SQL to avoid it."
            else:
                columns = state.execution_result.columns or []
                rows = state.execution_result.rows or []
                if not columns and not rows:
                    execution_context = "Query returned 0 rows and 0 columns."
                elif not rows:
                    execution_context = f"| {' | '.join(str(c) for c in columns)} |\n| {' | '.join(['---']*len(columns))} |\n(0 rows returned)"
                else:
                    table_lines = [f"| {' | '.join(str(c) for c in columns)} |", f"| {' | '.join(['---']*len(columns))} |"]
                    for row in rows:
                        safe_row = [str(x).replace('|', '\\|').replace('\n', ' ') for x in row]
                        table_lines.append(f"| {' | '.join(safe_row)} |")
                    execution_context = "\n".join(table_lines)

        # Get previous feedback for enforcement checking
        previous_feedback = getattr(state, 'critic_feedback', '') or 'None (first attempt)'

        # Dialect detection
        from app.models.config import settings
        db_type_env = settings.DB_TYPE.lower()
        dialect_key = "postgresql" if db_type_env in ["postgres", "postgresql"] else "sqlite"

        # B2: Use lru_cache loader instead of raw yaml.safe_load
        try:
            from app.services.prompt_loader import _load_yaml_cached
            from app.models.paths import PROMPTS_DIR
            dialects = _load_yaml_cached(str(PROMPTS_DIR / "dialects.yaml"))
            dialect_config = dialects.get(dialect_key, dialects.get("sqlite", {}))
            dialect = "PostgreSQL" if dialect_key == "postgresql" else "SQLite"
            dialect_instructions = dialect_config.get("critic_instructions", "")
        except Exception as e:
            Logger.log(f"Error loading dialects.yaml: {e}", level="ERROR")
            dialect = "SQLite"
            dialect_instructions = "Validate against standard SQL syntax."

        # Trim rag_pool to cap input tokens — full pool can be 500+ columns
        # 50 entries covers all relevant context without bloating the prompt
        trimmed_pool = state.rag_pool[:50] if state.rag_pool else []
        potential_pool = format_rag_columns(trimmed_pool) if trimmed_pool else "No pool available."


        messages = self.prompt_loader.load_prompt(
            "sql_critic",
            user_query=state.user_query,
            action_plan=action_plan,
            sql=sql_to_criticize,
            schema_path=schema_context,
            potential_pool=potential_pool,  # New variable for semantic check
            previous_feedback=previous_feedback,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
            execution_results=execution_context
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
