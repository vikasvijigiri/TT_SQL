import json
import os
from typing import List
from ..core.agent_base import BaseAgent, AgentState
from ..core.state import CandidateQuery
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.logger import Logger
from ..core.file_coordinator import FileCoordinator
from .input_layer import format_rag_columns

class MultiCandidateGeneratorAgent(BaseAgent):
    """
    Generates multiple SQL candidates (e.g., standard join, CTE, etc.).
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="SQLBuilder")
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

        # Dialect Detection
        db_type = os.getenv("DB_TYPE", "sqlite").lower()
        if db_type in ["postgres", "postgresql"]:
            dialect = "PostgreSQL"
            dialect_instructions = (
                " - YOU MUST ONLY USE POSTGRESQL COMMANDS. ANY SQLITE-SPECIFIC SYNTAX WILL CAUSE A FATAL ERROR.\n"
                " - Use CURRENT_DATE for the current date. NEVER use date('now').\n"
                " - Use INTERVAL for date arithmetic (e.g., col + INTERVAL '1 month').\n"
                " - Use DATE_TRUNC('month', col) for month-level grouping or filtering.\n"
                " - Use ILIKE for case-insensitive matching.\n"
                " - ROUND OFF: ALWAYS round numeric results, percentages, and averages to 2 decimal places using ROUND(v::numeric, 2).\n"
                " - DATE CASTING: For columns containing dates as strings (character varying), you MUST use TO_DATE(col, 'YYYY-MM-DD') before comparison or truncation.\n"
                " - Use NULLIF(denominator, 0) to prevent division by zero.\n"
                " - SCHEMA QUALIFICATION: You MUST always qualify table names with the schema name in double quotes: \"acme-chatbot\".table_name (e.g. FROM \"acme-chatbot\".otif).\n"
                " - PRIORITIZE INBUILT FUNCTIONS: Use native PostgreSQL functions (e.g., DATE_TRUNC, COALESCE, GREATEST, LEAST) whenever possible instead of complex manual logic."
            )
        else:
            dialect = "SQLite"
            dialect_instructions = (
                " - Use SQLite syntax only.\n"
                " - Use date('now') for current date.\n"
                " - Use datetime(col, '+1 month') for date arithmetic.\n"
                " - For division: CAST(x AS REAL) / y.\n"
                " - No ILIKE, use LOWER(col) = LOWER('val').\n"
                " - No POWER() function, use x * x."
            )

        # Prompt Loading: matches sql_builder.yaml
        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            previous_sql=previous_sql,
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
                    extra_context += f"\n\nCRITIC FEEDBACK (YOU MUST FIX ALL ISSUES BELOW):\n{content}"
                    has_critic_feedback = True

        # When critic feedback exists, relabel previous SQL so builder knows it has errors
        if has_critic_feedback and previous_sql:
            for msg in messages:
                if msg["role"] == "user" and "Previous Valid SQL Foundation:\n" in msg["content"]:
                    msg["content"] = msg["content"].replace(
                        "Previous Valid SQL Foundation:\n",
                        "PREVIOUS SQL (HAS ERRORS AND CONTINUES TO FAIL — YOU MUST FIX ALL ISSUES BELOW):\n"
                    )
                    break

        if extra_context:
            # Append to the last user message instead of creating new ones
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["content"] += extra_context
                    break
        
        
        candidates = []
        response = self.llm.get_json_completion(messages, state=state)
        
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
            # Don't add a fallback candidate, let it fail or return an error string
            sql_str = f"ERROR: LLM_FAILURE - {error_details}"
            candidates.append(CandidateQuery(sql=sql_str, approach="error_fallback"))

        state.candidate_queries = candidates
        if candidates:
            chosen = candidates[0]
            state.chosen_query = chosen.sql
            
            # Split into lines for file storage (line-by-line as requested)
            sql_lines = [line for line in chosen.sql.split('\n') if line.strip()]
            self.file_coordinator.write_sql(state.instance_id, sql_lines, state.model_name)
            
            self.log(state, f"Approach: {chosen.approach}")
            if chosen.explanation:
                self.log(state, f"Explanation: {chosen.explanation}")
        
        Logger.log_code(state.chosen_query, language="sql")
        return state
