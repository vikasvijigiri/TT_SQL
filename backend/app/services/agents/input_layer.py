import os
import json
from typing import Dict, Any, List
from app.services.agents.base import BaseAgent
from app.models.agent_state import AgentState
from app.repos.file_coordinator import FileCoordinator
import sys
from pathlib import Path

import re
from app.services.rag_service import query_qdrant

def sanitize_string(text: str) -> str:
    """Removes newlines, extra whitespace, and problematic characters."""
    if not text:
        return ""
    # Collapse multiple whitespaces and newlines into a single space
    text = re.sub(r'\s+', ' ', text)
    # Remove problematic unicode marks or non-breaking spaces if any
    text = text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    return text.strip()

def format_schema_to_str(schema_info: Dict[str, Any], detailed: bool = True) -> str:
    """Formats schema dict into a detailed multi-line or compact string."""
    if not schema_info: return ""
    lines = []
    for table, data in schema_info.items():
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
                    desc  = sanitize_string(c.get("description") or "")
                    lines.append(f" - {cname} {f'({ctype})' if ctype else ''}{f' -- {desc}' if desc else ''}")
                else:
                    lines.append(f" - {str(c)}")
            lines.append("") 
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
    """Formats the raw RAG retrieved columns list into a detailed, prompt-ready string."""
    if not rag_columns:
        return "No RAG columns retrieved."
    
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        if tname not in tables:
            tables[tname] = []
        tables[tname].append(col)

    lines = []
    from app.models.config import settings
    db_type = settings.DB_TYPE
    is_postgres = db_type in ["postgres", "postgresql"]

    for tname, cols in tables.items():
        lines.append(f"Table: {tname}")
        for c in cols:
            cname = c.get("column_name", "unknown")
            ctype = c.get("type") or c.get("data_type") or "unknown"
            desc  = sanitize_string(c.get("description") or "")
            samples = c.get("sample_values") or c.get("samples") or ""
            
            type_info = ctype
            if is_postgres and "varying" in ctype.lower():
                if any(k in cname.lower() or k in desc.lower() for k in ["date", "time", "dt", "timestamp"]):
                    type_info = f"{ctype} !! WARNING: Stored as STRING. Must use TO_DATE(col, 'YYYY-MM-DD') for comparisons !!"

            col_line = f" - {cname} ({type_info})"
            if desc: col_line += f" -- {desc}"
            if samples: col_line += f" [Samples: {samples}]"
            lines.append(col_line)
        lines.append("") 
    
    return "\n".join(lines).strip()

class ContextEnrichmentAgent(BaseAgent):
    """
    ContextEnrichmentAgent is responsible for retrieving relevant database schema
    metadata using vector search (RAG). It identifies the most pertinent tables
    and columns to provide the necessary context for SQL generation.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="TableSelector", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir)
        
    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        """
        Executes the RAG enrichment phase by querying the vector database.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            
        Returns:
            AgentState: The updated state with schema_info and rag_pool populated.
        """
        self.log(state, "Step: Identifying Relevant Schema (RAG Enrichment)")
        
        try:
            # Construct a comprehensive search query combining user query and approach strategy
            search_query = state.user_query
            if state.step_by_step_plan:
                search_query += "\nApproach Strategy:\n" + "\n".join(state.step_by_step_plan)

            # Invoke the structured RAG pipeline
            try:
                results = query_qdrant(
                    search_query, 
                    instance_id=state.instance_id,
                    collection_name=state.db_name,
                    results_dir=self.results_dir,
                    logs_dir=self.logs_dir,
                    metadata_dir=self.metadata_dir,
                    model_name=state.model_name
                )
                
                if results and "final_sets" in results:
                    sets_data = results["final_sets"]
                    state.rag_multi_sets = sets_data
                    
                    # Deduplicate all candidates across multi-sets to form the universal rag_pool
                    seen_cols = set()
                    rag_pool = []
                    for set_name, cols in sets_data.items():
                        for col in cols:
                            key = f"{col.get('table_name')}.{col.get('column_name')}"
                            if key not in seen_cols:
                                seen_cols.add(key)
                                rag_pool.append(col)
                    state.rag_pool = rag_pool

                    # Initialize schema from the primary set (Set A) for standard processing
                    primary_set_name = "Set A" if "Set A" in sets_data else list(sets_data.keys())[0]
                    retrieved_columns = sets_data[primary_set_name]
                    
                    # Group metadata by table for downstream agent consumption
                    rag_schema = {}
                    for col in retrieved_columns:
                        tname = col.get("table_name", "unknown")
                        if tname not in rag_schema:
                            rag_schema[tname] = {"columns": [], "foreign_keys": []}
                        
                        rag_schema[tname]["columns"].append({
                            "column_name": col.get("column_name", "unknown"),
                            "type":        col.get("type", "unknown"),
                            "description": col.get("description", ""),
                            "sample_values": col.get("sample_values"),
                            "pk":          col.get("pk", False)
                        })

                    state.schema_info = rag_schema
                    state.rag_columns = retrieved_columns
                    state.relevant_tables = list(rag_schema.keys())
                    
                    # Cache the formatted pool to optimize subsequent retry prompt building
                    state.formatted_rag_pool = format_rag_columns(state.rag_pool)

                    state.query_intent = "DATA_RETRIEVAL"
                    state.complexity_score = "MEDIUM"
                    state.context_reasoning = f"Column-Level RAG: schema built from {primary_set_name}."

                    total_cols = len(retrieved_columns)
                    self.log(state, f"RAG Success: retrieved {len(sets_data)} discrete sets. '{primary_set_name}' has {total_cols} columns.")
                else:
                    self.log(state, "RAG returned no candidates. Please verify the Qdrant collection and metadata.", level="WARN")
                    state.rag_pool = []
                    state.schema_info = {}

            except Exception as rag_err:
                self.log(state, f"Vector Search Failure: {str(rag_err)}", level="WARNING")
                state.rag_pool = []
                state.schema_info = {}

        except Exception as e:
            return self.handle_error(state, e)

        return state
