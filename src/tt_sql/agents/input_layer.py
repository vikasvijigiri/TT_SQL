import os
import json
from typing import Dict, Any, List
from tt_sql.core.agent_base import BaseAgent, AgentState
from tt_sql.core.file_coordinator import FileCoordinator
from tt_sql.rag.vector_store import VectorStoreAgent
from tt_sql.core.sqlite_service import SQLiteService
import yaml
from tt_sql.core.paths import PIPELINE_CONFIG

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
    """Formats the raw RAG retrieved columns list into a compact, prompt-ready string.
    Each entry: table_name | column_name | type | description
    """
    if not rag_columns:
        return "No RAG columns retrieved."
    # Group by table
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        cname = col.get("column_name", "unknown")
        if tname not in tables:
            tables[tname] = []
        tables[tname].append(cname)

    lines = []
    for tname, cols in tables.items():
        lines.append(f"Table: {tname}")
        lines.append(f"- Columns: {', '.join(cols)}")
        lines.append("")
    
    return "\n".join(lines).strip()



from ..core.bq_service import BigQueryService
from ..core.sf_service import SnowflakeService

class ContextEnrichmentAgent(BaseAgent):
    """
    Enriches context using column-level RAG retrieval or direct BigQuery schema fetch.
    """
    def __init__(self, config: dict = None):
        super().__init__(name="TableSelector", config=config)
        self.file_coordinator = FileCoordinator()
        
    def run(self, state: AgentState) -> AgentState:
        is_bigquery = state.instance_id.startswith("bq")
        is_snowflake = state.instance_id.startswith("sf")
        
        # 1. Try RAG if enabled
        if getattr(state, "use_rag", False):
            try:
                vector_store = VectorStoreAgent(collection_override=state.db_name)
                col_limit = getattr(state, "rag_limit", 2)
                retrieved_columns = vector_store.retrieve_relevant_columns(state.user_query, limit=col_limit)

                if retrieved_columns:
                    rag_schema = {}
                    for col in retrieved_columns:
                        tname = col["table_name"]
                        if tname not in rag_schema:
                            rag_schema[tname] = {"columns": [], "foreign_keys": []}
                        rag_schema[tname]["columns"].append({
                            "column_name": col["column_name"],
                            "type":        col["type"],
                            "description": col["description"],
                            "pk":          col.get("pk", False)
                        })
                    state.schema_info = rag_schema
                    state.rag_columns = retrieved_columns
                    self.log(state, f"Column RAG: retrieved {len(retrieved_columns)} columns.")
                else:
                    self.log(state, "Column RAG: No relevant columns found. Falling back to full schema.")
            except Exception as e:
                self.log(state, f"RAG failed: {e}. Falling back to full schema.", level="WARN")
        else:
            self.log(state, "RAG is disabled. Fetching full schema.")

        # 2. SQLite Full Schema Logic (if applicable and schema info is still empty or RAG was skipped/failed)
        if not is_bigquery and not is_snowflake and (not state.schema_info or not getattr(state, "use_rag", False)):
            if os.path.exists(state.db_path):
                try:
                    self.log(state, f"Fetching full schema from SQLite: {os.path.basename(state.db_path)}")
                    sqlite_svc = SQLiteService(state.db_path)
                    full_schema = sqlite_svc.get_full_schema()
                    if full_schema:
                        state.schema_info = full_schema
                        self.log(state, f"SQLite full schema fetched: {len(full_schema)} tables.")
                except Exception as e:
                    self.log(state, f"Local schema extraction failed: {e}", level="ERROR")

        # 2. BigQuery Fallback: If BQ task and schema is still thin, fetch from API
        if is_bigquery and (state.db_name or state.external_knowledge):
            try:
                bq_service = BigQueryService()
                datasets_to_try = []
                if state.db_name: datasets_to_try.append(state.db_name)
                
                # Extract potential dataset from external_knowledge (e.g. "dataset_name.table_name.md")
                if state.external_knowledge and "." in state.external_knowledge:
                    potential_ds = state.external_knowledge.split(".")[0]
                    if potential_ds not in datasets_to_try:
                        datasets_to_try.append(potential_ds)

                bq_schema = {}
                for ds in datasets_to_try:
                    self.log(state, f"BigQuery API fetch starting for: {ds}")
                    bq_schema = bq_service.get_dataset_schema(ds)
                    if bq_schema:
                        state.schema_info = bq_schema
                        self.log(state, f"BigQuery API: Fetched full schema for dataset '{ds}' ({len(bq_schema)} tables).")
                        break
                
                if not bq_schema:
                    self.log(state, f"BigQuery API: No tables found for datasets {datasets_to_try}.", level="WARN")
            except Exception as e:
                self.log(state, f"BigQuery API fetch failed: {e}", level="WARN")

        # 3. Snowflake Fallback: Fetch from API
        if is_snowflake and (state.db_name or state.external_knowledge):
            try:
                sf_service = SnowflakeService()
                database = state.db_name or "PATENTS" # Default fallback
                schema = "PUBLIC" # Snowflake default
                
                if "." in database:
                    parts = database.split(".")
                    database = parts[0]
                    schema = parts[1]

                self.log(state, f"Snowflake API fetch starting for: {database}.{schema}")
                sf_schema = sf_service.get_schema(database, schema)
                if sf_schema:
                    state.schema_info = sf_schema
                    self.log(state, f"Snowflake API: Fetched full schema for `{database}.{schema}` ({len(sf_schema)} tables).")
                else:
                    self.log(state, "Snowflake API: No tables found.", level="WARN")
            except Exception as e:
                self.log(state, f"Snowflake API fetch failed: {e}", level="WARN")

        if not state.schema_info:
            self.log(state, "WARNING: No schema info could be retrieved.", level="WARN")
        else:
            self.file_coordinator.write_schema(state.instance_id, state.schema_info, state.model_name)

        # Load defaults from config
        with open(PIPELINE_CONFIG, 'r') as f:
            pipeline_cfg = yaml.safe_load(f)
            defaults = pipeline_cfg.get("defaults", {})

        state.query_intent = defaults.get("query_intent", "DATA_RETRIEVAL")
        state.complexity_score = defaults.get("complexity_score", "MEDIUM")
        return state
