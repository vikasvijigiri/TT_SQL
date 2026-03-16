import json
import os
from typing import Dict, Any, List
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.repositories.persistence.file_coordinator import FileCoordinator
from app.services.utils.logger import Logger
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

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        sql_to_criticize = state.chosen_query or ""
        schema_context = format_rag_columns(state.rag_columns) if state.rag_columns else "RAG schema not available."

        action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan)) if state.step_by_step_plan else "No plan available."
        execution_context = "No execution results available."
        if state.execution_result:
            if state.execution_result.error_message:
                execution_context = f"EXECUTION FAILED WITH DATABASE ERROR:\n{state.execution_result.error_message}"
            else:
                columns = state.execution_result.columns or []; rows = state.execution_result.rows or []
                if not columns and not rows: execution_context = "Query returned 0 rows and 0 columns."
                elif not rows: execution_context = f"| {' | '.join(str(c) for c in columns)} |\n(0 rows returned)"
                else:
                    table_lines = [f"| {' | '.join(str(c) for c in columns)} |", f"| {' | '.join(['---']*len(columns))} |"]
                    for row in rows:
                        row_str = ' | '.join(str(x).replace('|', '\\|') for x in row)
                        table_lines.append(f"| {row_str} |")
                    execution_context = "\n".join(table_lines)

        from app.repositories.config import settings
        dialect_key = "postgresql" if settings.DB_TYPE.lower() in ["postgres", "postgresql"] else "sqlite"
        try:
            from app.services.utils.prompt_loader import _load_yaml_cached
            from app.repositories.registry.paths import PROMPTS_DIR
            dialects = _load_yaml_cached(str(PROMPTS_DIR / "dialects.yaml"))
            dialect_config = dialects.get(dialect_key, dialects.get("sqlite", {}))
            dialect = "PostgreSQL" if dialect_key == "postgresql" else "SQLite"
            dialect_instructions = dialect_config.get("critic_instructions", "")
        except Exception:
            dialect = "SQLite"; dialect_instructions = "Validate against standard SQL syntax."

        potential_pool = format_rag_columns(state.rag_pool[:50]) if state.rag_pool else "No pool available."

        messages = self.prompt_loader.load_prompt("sql_critic", user_query=state.user_query, action_plan=action_plan, sql=sql_to_criticize, schema_path=schema_context, potential_pool=potential_pool, previous_feedback=getattr(state, 'critic_feedback', 'None'), dialect=dialect, dialect_instructions=dialect_instructions, execution_results=execution_context)
        
        response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
        if response:
            state.is_result_valid = response.get("is_valid", False)
            state.critic_feedback = "; ".join(response.get("feedback", [])) if isinstance(response.get("feedback"), list) else str(response.get("feedback", ""))
            if response.get("failure_categories"): self.log(state, f"Failure categories: {', '.join(response['failure_categories'])}")
            self.log(state, f"Feedback: {state.critic_feedback}")
            Logger.log_code(json.dumps(response, indent=2), language="json")
        else:
            state.is_result_valid = True; self.log(state, "Critic failed to respond. Assuming VALID.")
        return state

    # --- Private Methods ---

    def _compact_schema(self, schema: Dict[str, Any]) -> str:
        if not schema: return ""
        lines = []
        for table, data in schema.items():
            cols = data.get("columns", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            col_names = [c.get("column_name", c.get("name", str(c))) if isinstance(c, dict) else str(c) for c in cols]
            lines.append(f"{table}({', '.join(col_names)})")
        return "\n".join(lines)
