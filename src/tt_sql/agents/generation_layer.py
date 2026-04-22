import json
import os
from typing import List
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.state import CandidateQuery
from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader
from tt_sql.core.logger import Logger
from tt_sql.core.file_coordinator import FileCoordinator
from .input_layer import format_rag_columns, format_schema_to_str
import yaml
from tt_sql.core.paths import DIALECT_RULES, PIPELINE_CONFIG

class MultiCandidateGeneratorAgent(BaseAgent):
    """
    Generates multiple SQL candidates (e.g., standard join, CTE, etc.).
    """
    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="SQLBuilder", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def _compact_schema(self, schema: dict) -> str:
        """Converts JSON schema to a detailed multi-line string."""
        if not schema: return ""
        lines = []
        if isinstance(schema, dict):
             for table, data in schema.items():
                cols = []
                if isinstance(data, dict) and "columns" in data:
                    cols = data["columns"]
                elif isinstance(data, list):
                    cols = data
                
                lines.append(f"Table: {table}")
                for c in cols:
                    if isinstance(c, dict):
                        cname = c.get("column_name") or c.get("name") or "unknown"
                        ctype = c.get("type") or c.get("data_type") or ""
                        desc  = c.get("description") or ""
                        lines.append(f" - {cname} {f'({ctype})' if ctype else ''}{f' -- {desc}' if desc else ''}")
                    else:
                        lines.append(f" - {str(c)}")
                lines.append("")
        return "\n".join(lines).strip()

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        # Get schema path
        schema_path = str(InstancePaths.schema(state.instance_id, state.model_name))


        
        # Previous SQL = last attempt (for retry refinement)
        previous_sql = state.chosen_query or ""
        if previous_sql.startswith("ERROR:"):
            previous_sql = ""  # Don't pass error strings as SQL

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

        # Dialect Detection and Dynamic Instructions
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if state.instance_id.startswith("bq"): db_type = "bigquery"
        
        with open(DIALECT_RULES, 'r') as f:
            all_rules = yaml.safe_load(f)
            
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules["instructions"]

        # Load labels from pipeline config
        with open(PIPELINE_CONFIG, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
            labels = pipeline_cfg.get("labels", {})

        # Potential Pool (Context Enrichment)
        potential_pool = "No additional contextual columns available."
        if state.rag_columns:
            potential_pool = format_rag_columns(state.rag_columns)

        # Previous SQL Label
        previous_sql_label = ""
        if previous_sql:
            previous_sql_label = "PREVIOUS SQL (HAS ERRORS - FIX THEM):"

        # Prompt Loading: matches sql_builder.yaml
        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            potential_pool=potential_pool,
            previous_sql=previous_sql,
            previous_sql_label=previous_sql_label,
            dialect=dialect,
            dialect_instructions=dialect_instructions
        )
        
        # Consolidate Critic feedback into the main user message
        extra_context = ""

        has_critic_feedback = False
        if state.history:
            for item in state.history[-1:]:
                content = item.get("content", "")
                if content:
                    extra_context += f"{labels.get('critic_feedback_header', '')}{content}"
                    has_critic_feedback = True

        # When critic feedback exists, relabel previous SQL so builder knows it has errors
        if has_critic_feedback and previous_sql:
            error_label = labels.get('previous_sql_error_label', '')
            for msg in messages:
                if msg["role"] == "user" and "Previous Valid SQL Foundation:\n" in msg["content"]:
                    msg["content"] = msg["content"].replace(
                        "Previous Valid SQL Foundation:\n",
                        error_label
                    )
                    break

        if extra_context:
            # Append to the last user message instead of creating new ones
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] += extra_context
                    break
        
        
        candidates = []
        response = self.llm.get_json_completion(messages, state=state, agent_name=self.name)
        
        # Fields expected from YAML prompt:
        # - corrections: List[str]
        # - sql: str (complete SQL as single string)
        # - approach: str
        # - explanation: str
        
        if response:
            corrections = response.get("corrections", [])
            sql_str = response.get("sql")
            if not sql_str:
                # If SQL is missing from JSON but JSON parsed, try to find it
                self.log(state, "SQL field missing in LLM response", level="WARN")
                return state
            approach = response.get("approach", "standard")
            explanation = response.get("explanation", "")
            reasoning = response.get("reasoning", "")
            
            if reasoning:
                self.log(state, f"Reasoning: {reasoning}")
            
            if corrections:
                self.log(state, "Corrections applied:")
                for c in corrections:
                    self.log(state, f"  - {c}")
            
            # Clean any accidental markdown markers
            sql_str = sql_str.replace("```sql", "").replace("```", "").strip()

            candidates.append(CandidateQuery(
                sql=sql_str, 
                approach=approach,
                explanation=explanation,
                score=0.9
            ))
        
        if not candidates:
            error_details = state.last_raw_response if hasattr(state, 'last_raw_response') else "No response"
            self.log(state, f"FATAL: LLM failed to generate SQL. Details: {error_details}", level="ERROR")
            state.is_result_valid = False
            state.chosen_query = None
            return state

        state.candidate_queries = candidates
        if candidates:
            # ... existing logic ...
            chosen = candidates[0]
            
            # Simple SQL validation before acceptance
            if not chosen.sql or chosen.sql.upper().startswith("ERROR") or len(chosen.sql) < 5:
                 self.log(state, "Generated SQL is empty, invalid, or an error string. Rejecting.", level="ERROR")
                 state.is_result_valid = False
                 state.chosen_query = None
                 return state

            state.chosen_query = chosen.sql
            state.is_result_valid = True  # Generator marks valid if it successfully built a query string
            
            # Split into lines for file storage
            sql_lines = [line for line in chosen.sql.split('\n') if line.strip()]
            self.file_coordinator.write_sql(state.instance_id, sql_lines, state.model_name)
            
            self.log(state, f"Approach: {chosen.approach}")
            if chosen.explanation:
                self.log(state, f"Explanation: {chosen.explanation}")
        
        Logger.log_code(state.chosen_query, language="sql")
        return state
