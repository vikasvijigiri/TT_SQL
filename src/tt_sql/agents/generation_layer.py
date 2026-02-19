import json
from typing import List
from ..core.agent_base import BaseAgent, AgentState
from ..core.state import CandidateQuery
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.logger import Logger
from ..core.file_coordinator import FileCoordinator

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
        """Converts JSON schema to a compact string: Table(col1, col2)"""
        if not schema: return ""
        lines = []
        if isinstance(schema, dict):
             for table, data in schema.items():
                # Handle potential dictionary structure (tables -> {columns: [...]})
                # Check for 'columns' key or if data is a list
                cols = []
                if isinstance(data, dict) and "columns" in data:
                    cols = data["columns"]
                elif isinstance(data, list):
                    cols = data
                
                # Extract names
                col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in cols]
                lines.append(f"{table}({', '.join(col_names)})")
        return "\n".join(lines)

    def run(self, state: AgentState) -> AgentState:
        from ..core.paths import InstancePaths
        
        # Get schema path
        schema_path = str(InstancePaths.schema(state.instance_id, state.model_name))


        
        # Previous SQL = last attempt (for retry refinement)
        previous_sql = state.chosen_query or ""
        if previous_sql.startswith("ERROR:"):
            previous_sql = ""  # Don't pass error strings as SQL

        rag_context = ""
        rag_source = getattr(state, "rag_source", "none")
        if rag_source == "qdrant":
            try:
                from ..rag.vector_store import VectorStoreAgent
                rag_agent = VectorStoreAgent()
                examples = rag_agent.retrieve_similar_examples(state.user_query)
                if examples:
                    rag_context = "\nSIMILAR PAST EXAMPLES (FOR REFERENCE):\n"
                    for i, ex in enumerate(examples):
                        rag_context += f"Example {i+1}:\nQuery: {ex['query']}\nSQL: {ex['sql']}\n\n"
                    self.log(state, f"Injected {len(examples)} RAG examples into prompt.")
            except Exception as e:
                Logger.log(f"RAG retrieval failed: {e}", level="ERROR")

        # Optimize Schema Context: only send relevant tables (from TableSelector)
        if state.schema_info:
             full_schema = state.schema_info
             if state.relevant_tables:
                 full_schema = {k: v for k, v in full_schema.items() if k in state.relevant_tables}
             schema_context = self._compact_schema(full_schema)
        else:
             try:
                 with open(schema_path, "r", encoding="utf-8") as f:
                     schema_context = self._compact_schema(json.load(f))
             except:
                 schema_context = "Schema not available."

        # Build action plan text
        action_plan = "No plan available."
        if state.step_by_step_plan:
            action_plan = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.step_by_step_plan))

        # Prompt Loading: matches sqlite_generation.yaml
        messages = self.prompt_loader.load_prompt(
            "sql_builder",
            user_query=state.user_query,
            action_plan=action_plan,
            schema_path=schema_context,
            previous_sql=previous_sql
        )
        
        # Consolidate RAG context and Critic feedback into the main user message
        extra_context = ""
        if rag_context:
            extra_context += f"\n{rag_context}"

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
                if msg["role"] == "user" and "Previous Valid SQL Foundation" in msg["content"]:
                    msg["content"] = msg["content"].replace(
                        "Previous Valid SQL Foundation:",
                        "PREVIOUS SQL (HAS ERRORS — REWRITE FROM SCRATCH):"
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
