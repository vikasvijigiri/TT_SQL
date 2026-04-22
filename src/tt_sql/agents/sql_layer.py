import json
import os
from typing import Dict, Any, List
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator
from ..core.logger import Logger
from .input_layer import format_rag_columns, format_schema_to_str
from ..core.paths import DIALECT_RULES
import yaml

class SQLBuilder(BaseAgent):
    """
    Responsible for generating the SQL query based on the plan and schema.
    """
    def __init__(self, llm_service: LLMService, config: dict = None):
        super().__init__(name="SQLBuilder", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        # Build action plan text
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(f"- {s}" for s in state.step_by_step_plan)

        # Schema Context Selection: Use RAG columns if available, otherwise fallback to full schema_info
        if state.rag_columns:
            schema_context = format_rag_columns(state.rag_columns)
        elif state.schema_info:
            schema_context = format_schema_to_str(state.schema_info)
        else:
            self.log(state, "WARNING: No schema info available — schema context is empty.", level="WARN")
            schema_context = "Schema not available."

        # Dialect Detection
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if state.instance_id.startswith("bq"): db_type = "bigquery"
        
        with open(DIALECT_RULES, 'r') as f:
            all_rules = yaml.safe_load(f)
            
        rules = all_rules.get(db_type, all_rules["sqlite"])
        dialect = rules["dialect"]
        dialect_instructions = rules["generator_instructions"]

        # Handle previous attempts
        previous_sql = state.chosen_query or "None"
        previous_sql_label = ""
        if state.chosen_query:
            previous_sql_label = "PREVIOUS SQL (HAS ERRORS - FIX THEM):"

        # Potential Pool (Context Enrichment)
        potential_pool = "No additional contextual columns available."
        if state.rag_columns:
            potential_pool = format_rag_columns(state.rag_columns)

        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            potential_pool=potential_pool,
            dialect=dialect,
            dialect_instructions=dialect_instructions,
            previous_sql=previous_sql,
            previous_sql_label=previous_sql_label
        )
        
        response = self.llm.get_json_completion(messages, state=state)
        
        if response:
            sql = response.get("sql", "").strip()
            if sql:
                # Remove markdown formatting if present
                if sql.startswith("```sql"):
                    sql = sql[6:].strip()
                if sql.endswith("```"):
                    sql = sql[:-3].strip()
                
                state.chosen_query = sql
                # Save to file
                self.file_coordinator.save_sql(state.instance_id, state.model_name, sql)
                self.log(state, f"Generated SQL ({len(sql)} chars)")
                Logger.log_code(sql, language="sql")
            else:
                self.log(state, "Builder returned empty SQL.")
        else:
            self.log(state, "Builder failed to generate SQL.")
            
        return state
