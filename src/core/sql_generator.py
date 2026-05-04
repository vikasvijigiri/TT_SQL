from core.logger import Logger
from agents.generic_agent import GenericAgent
from core.agent_base import AgentState

class SQLGenerator:
    """
    Generates SQL from a query plan using a grounded LLM approach.
    """

    def __init__(self, llm_service):
        self.llm = llm_service
        self.agent = GenericAgent(
            step_id="SQLGenerator",
            prompt_name="grounded_sql_generator",
            llm_service=self.llm
        )

    def generate(self, plan: dict, state: AgentState) -> str:
        """
        Generates SQL from plan.
        Uses the grounded_sql_generator prompt with subsetted or full schema.
        """
        if not plan or "error" in plan:
            return "SELECT * FROM (SELECT 1) WHERE 1=0"

        # 1. Use full schema if already injected in state (FastTrack or small schema)
        if getattr(state, "SCHEMA", ""):
            grounded_schema_str = state.SCHEMA
            Logger.log("SQLGenerator: Using full schema from state.")
        else:
            # Fallback to subsetting for very large schemas
            schema_subset = {}
            mappings = plan.get("mappings", [])
            
            # Include tables and columns from mappings
            for m in mappings:
                mapping = m["mapping"]
                table = mapping["table"]
                col = mapping["column"]
                if table not in schema_subset:
                    schema_subset[table] = {"columns": []}
                
                col_meta = mapping["meta"]
                if col_meta not in schema_subset[table]["columns"]:
                    schema_subset[table]["columns"].append(col_meta)

            # Include tables and columns from join plan
            for j in plan.get("joins", []):
                for t, c in [(j["source_table"], j["source_col"]), (j["target_table"], j["target_col"])]:
                    if t not in schema_subset:
                        schema_subset[t] = {"columns": []}
                    table_info = state.schema_info.get(t, {})
                    for col_info in table_info.get("columns", []):
                        if col_info["column_name"] == c:
                            if col_info not in schema_subset[t]["columns"]:
                                schema_subset[t]["columns"].append(col_info)
                            break

            from core.utils import format_schema_to_str
            grounded_schema_str = format_schema_to_str(schema_subset)
            Logger.log("SQLGenerator: Using subsetted schema.")

        # 2. Format join plan
        join_plan_str = "\n".join([
            f"JOIN {j['target_table']} ON {j['source_table']}.{j['source_col']} = {j['target_table']}.{j['target_col']}"
            for j in plan.get("joins", [])
        ])

        # 3. Call LLM
        state.grounded_schema = grounded_schema_str
        state.join_plan = join_plan_str
        
        self.agent.state_field = "_temp_sql"
        self.agent.output_key = "sql"
        
        state = self.agent.run(state)
        
        sql = getattr(state, "_temp_sql", "")
        if not sql:
            # Heuristic fallback if LLM returned empty string or failed
            return "SELECT * FROM (SELECT 1) WHERE 1=0"
            
        return sql
