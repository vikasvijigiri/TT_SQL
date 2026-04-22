import json
from typing import Dict, Any, List
from app.domain.agents.base import BaseAgent
from app.schemas.agent_state import AgentState
from app.infrastructure.external.llm import LLMService
from app.core.config.prompt_loader import PromptLoader, _load_yaml_cached
from .utils import format_rag_columns

class ReviewerAgent(BaseAgent):
    """
    Evaluates generated SQL results against query intent and schema constraints.
    Provides structured feedback for iterative refinement if errors are detected.
    """
    def __init__(self, llm: LLMService, **kwargs):
        super().__init__(name="SQLReviewer", **kwargs)
        self.llm = llm
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        try:
            # Context Preparation
            execution_ctx = self._format_execution_context(state)
            dialect_info = self._get_dialect_config(state)
            
            messages = self.prompt_loader.load_prompt(
                "sql_critic",
                user_query=state.user_query,
                action_plan="\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan or [])),
                sql=state.chosen_query or "No query generated.",
                schema_path=format_rag_columns(state.rag_columns),
                potential_pool=format_rag_columns(state.rag_pool),
                previous_feedback=state.critic_feedback or "None",
                dialect=dialect_info["name"],
                dialect_instructions=dialect_info["instructions"],
                execution_results=execution_ctx
            )

            response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
            if response:
                state.is_result_valid = response.get("is_valid", False)
                fb = response.get("feedback", [])
                state.critic_feedback = "; ".join(fb) if isinstance(fb, list) else str(fb)
                
                self.log(state, f"Valid: {state.is_result_valid} | Feedback: {state.critic_feedback[:100]}...")
            else:
                state.is_result_valid = True  # Fallback safety
                
        except Exception as e:
            return self.handle_error(state, e)
            
        return state

    def _format_execution_context(self, state: AgentState) -> str:
        """Standardizes database output into a prompt-readable format."""
        res = state.execution_result
        if not res: return "No execution attempted."
        if res.error_message: return f"DATABASE ERROR:\n{res.error_message}"
        
        headers = f"| {' | '.join(res.columns)} |"
        divider = f"| {' | '.join(['---']*len(res.columns))} |"
        rows = [" | ".join(map(str, r)) for r in res.rows[:10]]
        return f"{headers}\n{divider}\n" + "\n".join(rows)

    def _get_dialect_config(self, state: AgentState) -> Dict[str, str]:
        from app.core.config.settings import settings
        db_type = (state.connection_details or {}).get("db_type") or settings.DB_TYPE or "sqlite"
        key = "postgresql" if "postgres" in db_type.lower() else "sqlite"
        
        try:
            from app.infrastructure.storage.path_manager import PROJECT_ROOT
            dialects = _load_yaml_cached(str(PROJECT_ROOT / "app/services/prompts/dialects.yaml"))
            config = dialects.get(key, dialects.get("default", {}))
            return {"name": key.title(), "instructions": config.get("critic_instructions", "")}
        except Exception:
            return {"name": key.title(), "instructions": "Review against standard SQL logic."}
