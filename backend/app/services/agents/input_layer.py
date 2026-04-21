import os
import json
from typing import Dict, Any, List
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState
from app.repositories.persistence.file_coordinator import FileCoordinator
import sys
from pathlib import Path

import re
from app.services.engines.rag_service import query_qdrant

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
                lines.append("")
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

def format_rag_columns(rag_columns: list, db_type: str = "postgres") -> str:
    """Formats the raw RAG retrieved columns list into a detailed, prompt-ready string."""
    if not rag_columns:
        return ""
    
    tables = {}
    for col in rag_columns:
        tname = col.get("table_name", "unknown")
        if tname not in tables:
            tables[tname] = []
        tables[tname].append(col)

    lines = []
    is_postgres = db_type.lower() in ["postgres", "postgresql"]

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
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="TableSelector", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    def hydrate_columns(self, set_data: Dict[str, List[str]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Helper to hydrate column names into full metadata objects."""
        hydrated = []
        for tname, col_names in set_data.items():
            table_meta = metadata.get(tname, {})
            cols_meta = table_meta.get("columns", [])
            for cname in col_names:
                found = False
                for cm in cols_meta:
                    if cm.get("column_name") == cname:
                        hydrated.append({
                            "table_name": tname,
                            "column_name": cname,
                            "type": cm.get("type", "unknown"),
                            "description": cm.get("description", ""),
                            "sample_values": cm.get("sample_values", []),
                            "pk": cm.get("pk", False)
                        })
                        found = True
                        break
                if not found:
                    hydrated.append({"table_name": tname, "column_name": cname, "type": "unknown"})
        return hydrated

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        """
        Executes the RAG enrichment phase by querying the vector database and re-hydrating metadata.
        """
        self.log(state, "Step: Identifying Relevant Schema (Advanced RAG Enrichment)")
        
        try:
            # Invoke the structured RAG pipeline
            import inspect
            actual_kwargs = {
                "collection_name": state.db_name,
                "instance_id": state.instance_id,
                "results_dir": self.results_dir,
                "user_slug": self.user_slug,
                "qdrant_url": (state.connection_details or {}).get("qdrant_url"),
                "qdrant_api_key": (state.connection_details or {}).get("qdrant_api_key")
            }
            
            # Dynamic filtering of kwargs based on actual service signature
            sig = inspect.signature(query_qdrant)
            filtered_kwargs = {k: v for k, v in actual_kwargs.items() if k in sig.parameters}
            
            results = query_qdrant(state.user_query, **filtered_kwargs)
            
            if not results or ("final_sets" not in results and "top_3_sets" not in results):
                err_msg = "RAG retrieval failed: No relevant context found in Knowledge Base. Please ensure you have run 'Inject Knowledge' for this project."
                self.log(state, err_msg, level="WARNING")
                state.rag_pool = []
                state.schema_info = {}
                return state

            # Access Primary Schema Set
            primary_set = results.get("primary_set") or results.get("Set A") or list(results.get("top_3_sets", {}).values())[0]
            
            # Load metadata for re-hydration
            metadata_path = results.get("metadata_path")
            if not metadata_path or not os.path.exists(metadata_path):
                from app.repositories.registry.paths import get_metadata_dir
                from app.repositories.connectors.sql_repo import DBRepository
                active_conn = DBRepository._get_active_connection(user_slug=self.user_slug)
                collection_name = DBRepository.get_collection_name(active_conn, state.db_name or "metadata")
                metadata_path = get_metadata_dir(self.user_slug) / f"{collection_name}.json"
            
            from app.services.utils.schema_registry import SchemaRegistry
            metadata = SchemaRegistry.get_metadata(str(metadata_path))

            # Hydrate the column metadata for the chosen set
            state.rag_columns = self.hydrate_columns(primary_set, metadata)
            state.rag_pool = state.rag_columns # Simplify: pool is the primary set for now
            
            # Group metadata by table for downstream agent consumption (state.schema_info)
            rag_schema = {}
            for col in state.rag_columns:
                tname = col["table_name"]
                if tname not in rag_schema:
                    rag_schema[tname] = {"columns": [], "foreign_keys": []}
                rag_schema[tname]["columns"].append(col)

            state.schema_info = rag_schema
            state.relevant_tables = list(rag_schema.keys())
            db_type = (state.connection_details or {}).get("db_type", "postgres")
            state.formatted_rag_pool = format_rag_columns(state.rag_pool, db_type=db_type)
            state.query_intent = "DATA_RETRIEVAL"
            state.complexity_score = "MEDIUM"
            
            # Transparency Metrics
            anchors = results.get("anchors", [])
            iterations = results.get("iterations", 1)
            sufficient = results.get("sufficient", False)
            
            state.context_reasoning = (
                f"Anchor-Driven RAG: Completed in {iterations} scans. "
                f"Anchors: {', '.join(anchors[:5])}{'...' if len(anchors) > 5 else ''}. "
                f"Sufficiency reached: {sufficient}."
            )

            # Verification Logging
            col_count = sum(len(v.get("columns", [])) for v in rag_schema.values())
            self.log(state, f"📍 Anchors Identified: {', '.join(anchors)}")
            self.log(state, f"🔍 Iterative Scan: Completed {iterations} windows. Sufficiency: {'✅' if sufficient else '⚠️ Partial'}")
            self.log(state, f"Schema Context Hydrated: {len(rag_schema)} tables, {col_count} columns.")

        except Exception as e:
            import traceback
            self.log(state, f"Context Enrichment Failure:\n{traceback.format_exc()}", level="ERROR")
            return self.handle_error(state, e)

        return state
