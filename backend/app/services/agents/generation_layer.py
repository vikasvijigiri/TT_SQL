import json
import os
import threading
from typing import List
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState, CandidateQuery
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.repositories.persistence.file_coordinator import FileCoordinator
from app.services.utils.logger import Logger
from app.services.agents.input_layer import format_rag_columns

class MultiCandidateGeneratorAgent(BaseAgent):
    """
    MultiCandidateGeneratorAgent is responsible for synthesizing the SQL query based on
    the execution plan and the enriched schema context. It utilizes the LLM to 
    generate candidate queries tailored to the target database dialect.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="SQLBuilder", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    def _format_compact_schema(self, schema_info: dict) -> str:
        """Formats schema as: - Table: col1 (desc), col2 (desc)..."""
        if not schema_info:
            return ""
        
        lines = []
        for table, data in schema_info.items():
            cols = data.get("columns", [])
            col_strings = []
            for c in cols:
                name = c.get("column_name") or c.get("name") or "unknown"
                desc = c.get("description") or ""
                col_strings.append(f"{name} ({desc})" if desc else name)
            
            lines.append(f"- {table}: {', '.join(col_strings)}")
        return "\n".join(lines)

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        """
        Executes the SQL generation phase by translating the plan into SQL syntax.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            
        Returns:
            AgentState: The updated state with the chosen candidate query.
        """
        try:
            # Format schema context compactly for the prompt
            schema_context = self._format_compact_schema(state.schema_info)
            
            # Previous SQL context for refinement loops
            previous_sql = state.chosen_query or ""
            if previous_sql.upper().startswith("ERROR:"):
                previous_sql = ""

            # Standardize action plan visualization
            action_plan = ""
            if state.step_by_step_plan:
                action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan))

            # Dialect resolution logic
            from app.repositories.config import settings
            db_type_env = settings.DB_TYPE.lower()
            
            if db_type_env in ["postgres", "postgresql"]:
                dialect_key = "postgresql"
                dialect = "PostgreSQL"
            elif db_type_env == "bigquery":
                dialect_key = "bigquery"
                dialect = "BigQuery"
            elif db_type_env == "snowflake":
                dialect_key = "snowflake"
                dialect = "Snowflake"
            else:
                dialect_key = "sqlite"
                dialect = "SQLite"
            
            try:
                from app.services.utils.prompt_loader import _load_yaml_cached
                from app.repositories.registry.paths import PROMPTS_DIR
                dialects = _load_yaml_cached(str(PROMPTS_DIR / "dialects.yaml"))
                dialect_config = dialects.get(dialect_key, dialects.get("default", {}))
                dialect_instructions = dialect_config.get("builder_instructions", "")
            except Exception as e:
                Logger.log(f"Error loading dialects config: {str(e)}", level="ERROR")
                # Minimal fallback if even the 'default' key fails
                dialect_instructions = "Use standard SQL syntax compatible with the target database."

            # Dynamic context labeling for LLM guidance
            has_critic_feedback = bool(state.history and any(item.get("content") for item in state.history[-1:]))
            
            LABEL_MAP = {
                "REFINEMENT": "PREVIOUS SQL (HAS ERRORS - YOU MUST FIX ALL ISSUES BELOW):",
                "FOUNDATION": "Previous Valid SQL Foundation:",
                "EMPTY": "Previous SQL (None):"
            }
            
            if has_critic_feedback:
                sql_label = LABEL_MAP["REFINEMENT"]
            elif previous_sql:
                sql_label = LABEL_MAP["FOUNDATION"]
            else:
                sql_label = "" # Don't show a 'None' label on the first attempt

            # Leverage pre-formatted RAG pool for context-heavy generation
            potential_pool = getattr(state, 'formatted_rag_pool', None) or ""

            # Construct and execute LLM completion
            messages = self.prompt_loader.load_prompt(
                "sql_builder",
                user_query=state.user_query,
                action_plan=action_plan,
                schema_path=schema_context,
                potential_pool=potential_pool,
                previous_sql=previous_sql,
                previous_sql_label=sql_label,
                dialect=dialect,
                dialect_instructions=dialect_instructions
            )

            # Integrate critic feedback if relevant
            if has_critic_feedback:
                feedback = state.history[-1].get("content", "")
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        msg["content"] += f"\n\nCRITIC FEEDBACK:\n{feedback}"
                        break

            # Use a single high-quality SQL candidate rather than managing lists
            response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
            
            if response and response.get("sql"):
                sql_str = response.get("sql").replace("```sql", "").replace("```", "").strip()
                corrections = response.get("corrections", [])
                
                if corrections:
                    self.log(state, f"SQL Refinement Applied: {', '.join(corrections)}")

                state.chosen_query = sql_str
                state.candidate_queries = [CandidateQuery(sql=sql_str, approach=response.get("approach", "standard"), score=0.9)]
            else:
                error_details = getattr(state, 'last_raw_response', "Empty response")
                self.log(state, f"SQL Generation Failed. Raw context: {error_details[:200]}...", level="ERROR")
                state.chosen_query = f"ERROR: Generation Failure - {error_details[:100]}"
                return state
            
            # Non-blocking persistent storage
            def _bg_write_sql():
                try:
                    sql_lines = [line for line in sql_str.split('\n') if line.strip()]
                    self.file_coordinator.write_sql(state.instance_id, sql_lines, state.model_name)
                except Exception as e:
                    Logger.log(f"Background SQL write failed: {str(e)}", level="DEBUG")
                    
            threading.Thread(target=_bg_write_sql, daemon=True).start()

            approach = response.get("approach", "standard")
            explanation = response.get("explanation", "")

            self.log(state, f"Approach: {approach}")
            if explanation:
                self.log(state, f"Reasoning: {explanation}")
                
            Logger.log_code(state.chosen_query, language="sql")

        except Exception as e:
            self.log(state, f"Synthesis Error: {str(e)}", level="ERROR")
            state.chosen_query = f"ERROR: Synthesis Exception - {str(e)}"
            
        return state
