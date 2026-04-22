import threading
from typing import List, Dict, Any
from app.domain.agents.base import BaseAgent
from app.schemas.agent_state import AgentState, CandidateQuery
from app.infrastructure.external.llm import LLMService
from app.core.config.prompt_loader import PromptLoader, _load_yaml_cached
from app.infrastructure.storage.path_manager import StorageManager
from app.core.logging.logger import Logger
from .utils import format_schema_to_str

class CoderAgent(BaseAgent):
    """
    Translates execution plans and schema context into optimized SQL queries.
    Handles dialect-specific instructions and iterative refinement.
    """
    def __init__(self, llm: LLMService, **kwargs):
        super().__init__(name="SQLBuilder", **kwargs)
        self.llm = llm
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        try:
            # SQL Generation Context
            schema_context = format_schema_to_str(state.schema_info, detailed=False)
            dialect_info = self._get_dialect_config(state)
            
            # Label mapping for refinement loops
            has_feedback = bool(state.history and state.history[-1].get("content"))
            sql_label = "REFINEMENT (FIX ERRORS):" if has_feedback else "Previous Code:" if state.chosen_query else ""

            # Construct Prompt
            messages = self.prompt_loader.load_prompt(
                "sql_builder",
                user_query=state.user_query,
                action_plan="\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan or [])),
                schema_path=schema_context,
                potential_pool=getattr(state, 'formatted_rag_pool', ""),
                previous_sql=state.chosen_query or "",
                previous_sql_label=sql_label,
                dialect=dialect_info["name"],
                dialect_instructions=dialect_info["instructions"]
            )

            # Append critic feedback if present
            if has_feedback:
                messages[-1]["content"] += f"\n\nCRITIC FEEDBACK:\n{state.history[-1].get('content')}"

            # LLM Call
            response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
            if not (response and response.get("sql")):
                raise ValueError("LLM failed to generate valid SQL result.")

            sql_str = response["sql"].replace("```sql", "").replace("```", "").strip()
            state.chosen_query = sql_str
            state.candidate_queries = [CandidateQuery(sql=sql_str, approach=response.get("approach", "standard"), score=0.9)]
            
            # Background I/O
            threading.Thread(target=self._persist_sql, args=(state, sql_str), daemon=True).start()

            self.log(state, f"Dialect: {dialect_info['name']} | Approach: {response.get('approach', 'standard')}")
            Logger.log_code(sql_str, language="sql")

        except Exception as e:
            return self.handle_error(state, e)
            
        return state

    def _get_dialect_config(self, state: AgentState) -> Dict[str, str]:
        """Resolves dialect name and specialized instructions from YAML config."""
        from app.core.config.settings import settings
        db_type = (state.connection_details or {}).get("db_type") or settings.DB_TYPE or "sqlite"
        
        map = {"postgres": "postgresql", "postgresql": "postgresql", "bigquery": "bigquery", "snowflake": "snowflake"}
        key = map.get(db_type.lower(), "sqlite")
        
        try:
            from app.infrastructure.storage.path_manager import PROJECT_ROOT
            dialects = _load_yaml_cached(str(PROJECT_ROOT / "app/services/prompts/dialects.yaml"))
            config = dialects.get(key, dialects.get("default", {}))
            return {"name": key.title(), "instructions": config.get("builder_instructions", "")}
        except Exception:
            return {"name": key.title(), "instructions": "Use standard SQL syntax."}

    def _persist_sql(self, state: AgentState, sql: str):
        # Implementation moved to specialized persistence service or direct coordinator
        pass
