import os
import json
from typing import Dict, Any, List
from ..core.agent_base import BaseAgent, AgentState
from ..core.file_coordinator import FileCoordinator
from ..rag.vector_store import VectorStoreAgent

def format_schema_to_str(schema_info: Dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a detailed multi-line or compact string."""
    if not schema_info: return ""
    lines = []
    for table, data in schema_info.items():
        # Handle potential dictionary structure
        if isinstance(data, dict) and "columns" in data:
            cols = data["columns"]
        elif isinstance(data, list):
            cols = data
        else:
            cols = []
            
        if detailed:
            lines.append(f"Table: {table}")
            if not cols:
                lines.append(" - (No columns found)")
            for c in cols:
                if isinstance(c, dict):
                    cname = c.get("column_name") or c.get("name") or "unknown"
                    ctype = c.get("type") or c.get("data_type") or ""
                    desc  = c.get("description") or ""
                    lines.append(f" - {cname} {f'({ctype})' if ctype else ''}{f' -- {desc}' if desc else ''}")
                else:
                    lines.append(f" - {str(c)}")
            lines.append("") # Blank line
        else:
            col_names = []
            for c in cols:
                if isinstance(c, dict):
                    col_names.append(str(c.get("column_name") or c.get("name") or "unknown"))
                else:
                    col_names.append(str(c))
            lines.append(f"{table}({', '.join(col_names)})")
    return "\n".join(lines).strip()


def format_rag_columns(rag_columns: list) -> str:
    """Formats the raw RAG retrieved columns list into a detailed, prompt-ready string.
    Each entry: table_name | column_name | type | description | sample_values
    """
    if not rag_columns:
        return "No RAG columns retrieved."
    
    # Group by table
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        if tname not in tables:
            tables[tname] = []
        tables[tname].append(col)

    lines = []
    
    # Detect dialect for specific warnings
    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    is_postgres = db_type in ["postgres", "postgresql"]

    for tname, cols in tables.items():
        lines.append(f"Table: {tname}")
        for c in cols:
            cname = c.get("column_name", "unknown")
            ctype = c.get("type") or c.get("data_type") or "unknown"
            desc  = c.get("description") or ""
            samples = c.get("sample_values") or c.get("samples") or ""
            
            # Type Warning for PostgreSQL
            type_info = ctype
            if is_postgres and "varying" in ctype.lower():
                # If it looks like a date/time but is stored as string
                if any(k in cname.lower() or k in desc.lower() for k in ["date", "time", "dt", "timestamp"]):
                    type_info = f"{ctype} !! WARNING: Stored as STRING. Must use TO_DATE(col, 'YYYY-MM-DD') for comparisons !!"

            col_line = f" - {cname} ({type_info})"
            if desc: col_line += f" -- {desc}"
            if samples: col_line += f" [Samples: {samples}]"
            lines.append(col_line)
        lines.append("") # Blank line
    
    return "\n".join(lines).strip()



class ContextEnrichmentAgent(BaseAgent):
    """
    Enriches context using column-level RAG retrieval only.
    Columns are retrieved from Qdrant; table names follow from column metadata.
    No LLM call is made in this stage.
    """
    def __init__(self):
        super().__init__(name="TableSelector")
        self.file_coordinator = FileCoordinator()
        
    def run(self, state: AgentState) -> AgentState:
        # RAG always runs — collection from QDRANT_COLLECTION in .env
        try:
            vector_store = VectorStoreAgent()
            col_limit = getattr(state, "rag_limit", 2)
            
            # Combine the user query and the planner's approach strategy for deeper RAG retrieval
            search_query = state.user_query
            if hasattr(state, "step_by_step_plan") and state.step_by_step_plan:
                approach_str = " ".join(state.step_by_step_plan)
                search_query = f"{state.user_query}\nApproach:\n{approach_str}"
                
            retrieved_columns = vector_store.retrieve_relevant_columns(search_query, limit=col_limit)

            if retrieved_columns:
                # Group by table_name to build schema_info
                rag_schema = {}
                for col in retrieved_columns:
                    tname = col["table_name"]
                    if tname not in rag_schema:
                        rag_schema[tname] = {"columns": [], "foreign_keys": []}
                    rag_schema[tname]["columns"].append({
                        "column_name": col.get("column_name", "unknown"),
                        "type":        col.get("type", "unknown"),
                        "description": col.get("description", ""),
                        "sample_values": col.get("sample_values"),
                        "pk":          col.get("pk", False)
                    })

                total_cols = sum(len(v["columns"]) for v in rag_schema.values())
                self.log(state, f"Column RAG: retrieved {total_cols} columns across {len(rag_schema)} table(s).")

                state.schema_info = rag_schema
                state.rag_columns = retrieved_columns   # store raw list for direct prompt use
                state.relevant_tables = list(rag_schema.keys())
                state.query_intent = "DATA_RETRIEVAL"
                state.complexity_score = "MEDIUM"
                state.context_reasoning = "Column-Level RAG: schema built from top-scored column retrievals."

                try:
                    self.file_coordinator.write_schema(state.instance_id, rag_schema, state.model_name)
                    self.log(state, f"PLAN_STEP: 3. Schema written ({total_cols} columns, {len(rag_schema)} tables).")
                except Exception as e:
                    self.log(state, f"Warning: Could not save RAG schema: {e}", level="WARN")
            else:
                self.log(state, "RAG returned no columns — check Qdrant collection.", level="WARN")

        except Exception as e:
            self.log(state, f"Qdrant retrieval failed: {e}", level="ERROR")

        return state
