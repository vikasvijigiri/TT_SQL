import os
import inspect
from typing import Dict, Any, List
from app.domain.agents.base import BaseAgent
from app.schemas.agent_state import AgentState
from app.infrastructure.storage.path_manager import StorageManager
from .utils import format_rag_columns

class PlannerAgent(BaseAgent):
    """
    Enriches query context using RAG or full schema pass-through.
    Identifies relevant tables and columns for SQL generation.
    """
    
    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        self.log(state, "Step: Identifying Relevant Schema (RAG Enrichment)")
        try:
            if not state.use_rag:
                return self._run_full_schema(state)
            
            # Standard Iterative RAG
            results = self._query_knowledge_base(state)
            if not results: return state

            primary_set = results.get("primary_set") or list(results.get("top_3_sets", {}).values())[0]
            metadata = self._load_metadata(results.get("metadata_path"), state)

            state.rag_columns = self._hydrate_columns(primary_set, metadata)
            state.rag_pool = state.rag_columns
            state.schema_info = self._group_by_table(state.rag_columns)
            state.relevant_tables = list(state.schema_info.keys())
            
            db_type = (state.connection_details or {}).get("db_type", "postgres")
            state.formatted_rag_pool = format_rag_columns(state.rag_pool, db_type=db_type)
            state.context_reasoning = f"RAG: Scanned {results.get('iterations')} windows. Anchors: {', '.join(results.get('anchors', [])[:3])}."
            
            self.log(state, f"Context Hydrated: {len(state.schema_info)} tables, {len(state.rag_columns)} columns.")
        except Exception as e:
            return self.handle_error(state, e)
        return state

    def _run_full_schema(self, state: AgentState) -> AgentState:
        self.log(state, "RAG disabled. Loading full project schema...")
        # Logic for full schema hydration (moved to separate utility or kept here)
        from app.utils.schema_registry import SchemaRegistry
        path = StorageManager.get_metadata_dir(self.user_slug, state.project_slug) / f"{state.db_name}.json"
        
        if not path.exists():
            self.log(state, f"Metadata not found at {path}", level="WARNING")
            return state

        metadata = SchemaRegistry.get_metadata(str(path))
        cols = []
        for tname, tmeta in metadata.items():
            for cm in tmeta.get("columns", []):
                cols.append({"table_name": tname, **cm})
        
        state.schema_info = {t: {"columns": [c for c in cols if c["table_name"] == t]} for t in metadata.keys()}
        state.rag_columns = cols
        state.rag_pool = cols
        state.relevant_tables = list(metadata.keys())
        state.context_reasoning = "Full schema pass-through enabled."
        return state

    def _query_knowledge_base(self, state: AgentState) -> Dict[str, Any]:
        actual_kwargs = {
            "collection_name": state.db_name,
            "instance_id": state.instance_id,
            "user_slug": self.user_slug,
            "qdrant_url": (state.connection_details or {}).get("qdrant_url"),
            "qdrant_api_key": (state.connection_details or {}).get("qdrant_api_key")
        }
        sig = inspect.signature(query_qdrant)
        filtered = {k: v for k, v in actual_kwargs.items() if k in sig.parameters}
        return query_qdrant(state.user_query, **filtered)

    def _load_metadata(self, path: str, state: AgentState) -> Dict[str, Any]:
        from app.utils.schema_registry import SchemaRegistry
        if not path or not os.path.exists(path):
            from app.infrastructure.storage.path_manager import StorageManager
            path = StorageManager.get_project_dir(self.user_slug, state.project_slug or "default") / "metadata_extracts" / f"{state.db_name or 'metadata'}.json"
        return SchemaRegistry.get_metadata(str(path))

    def _hydrate_columns(self, set_data: Dict[str, List[str]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        hydrated = []
        for tname, col_names in set_data.items():
            t_meta = metadata.get(tname, {}).get("columns", [])
            for cname in col_names:
                m = next((m for m in t_meta if m.get("column_name") == cname), {"column_name": cname})
                hydrated.append({"table_name": tname, **m})
        return hydrated

    def _group_by_table(self, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        schema = {}
        for col in columns:
            t = col["table_name"]
            schema.setdefault(t, {"columns": [], "foreign_keys": []})["columns"].append(col)
        return schema
