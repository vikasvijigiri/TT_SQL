import os
import time
import threading
import json
import re
from typing import Optional, Dict, Any, List

from app.schemas.agent_state import AgentState
from app.services.llm_service import LLMService
from app.utils.prompt_loader import PromptLoader
from app.core.logger import Logger
from app.db.sql_repo import DBRepository
from app.repositories.paths import (
    initialize_directories, InstancePaths, get_model_results_dir, 
    get_metadata_dir, get_active_project_slug
)
from app.utils.schema_registry import SchemaRegistry
from app.services.agents.input_layer import format_rag_columns

# Import Agents (Lean Stack)
from app.services.agents.input_layer import ContextEnrichmentAgent
from app.services.agents.loop_layer import RefinementLoopAgent
from app.services.agents.orchestration_layer import OrchestratorAgent

def run_analysis_pipeline(question: str, 
                          db_name: str, 
                          instance_id: str, 
                          model_name: str, 
                          dataset_name: Optional[str] = None,
                          enabled_agents: Optional[List[str]] = None, 
                          use_rag: bool = False, 
                          verbose: bool = False,
                          on_token: callable = None,
                          on_result: callable = None,
                          results_dir: Optional[str] = None,
                          logs_dir: Optional[str] = None,
                          user_email: Optional[str] = None,
                          project_slug: Optional[str] = None,
                          session_id: Optional[str] = None,
                          config_override: Optional[Dict[str, Any]] = None,
                          existing_state: Optional[AgentState] = None) -> AgentState:
    """
    Lean, sequential execution of the Text-to-SQL agents.
    Optimized for speed and simplicity by avoiding redundant planning and parallel branches.
    """
    if on_token:
        on_token("✦ ")

    Logger._verbose = verbose
    user_slug = user_email.split('@')[0] if user_email else None
    p_slug = project_slug or get_active_project_slug(user_slug=user_slug)
    
    initialize_directories(model_name, user_slug=user_slug, project_slug=p_slug)
    llm_service = LLMService(model=model_name, config_override=config_override)
    
    # Define Simplified Agent Stack
    agents = [
        ContextEnrichmentAgent(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug, project_slug=p_slug),
        RefinementLoopAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug, project_slug=p_slug),
        OrchestratorAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug, project_slug=p_slug)
    ]

    # Filter Agents if requested
    if enabled_agents:
        enabled_lower = [a.lower() for a in enabled_agents]
        agents = [a for a in agents if a.name.lower() in enabled_lower]

    # Resolve active database connection
    active_conn = DBRepository._get_active_connection(user_slug=user_slug)
    resolved_db_path = active_conn.get("sqlite_path", "")
    resolved_db_name = active_conn.get("db_name") or active_conn.get("schema") or active_conn.get("database") or db_name

    # Handle Bulk SQLite resolution
    if active_conn.get("db_type") == "bulk_sqlite":
        db_root = active_conn.get("db_root")
        if db_root:
            # Dynamically resolve path using db_name from request/task
            # Ensure we don't add .sqlite if it's already there
            db_filename = db_name if db_name.lower().endswith(('.sqlite', '.db')) else f"{db_name}.sqlite"
            resolved_db_path = os.path.join(db_root, db_filename)
            resolved_db_name = db_name
            Logger.log(f"✦ Bulk Resolution: Resolved '{db_name}' to {resolved_db_path}")

    if existing_state:
        state = existing_state
        state.user_query = question
        state.db_path = resolved_db_path
        state.db_name = resolved_db_name
        state.instance_id = instance_id
        state.use_rag = use_rag
        state.model_name = model_name
        state.user_email = user_email
        state.session_id = session_id
        state.connection_details = active_conn
    else:
        state = AgentState(
            user_query=question,
            db_path=resolved_db_path,
            db_name=resolved_db_name,
            instance_id=instance_id,
            use_rag=use_rag,
            model_name=model_name,
            user_email=user_email,
            session_id=session_id,
            connection_details=active_conn
        )

    # Setup Logging
    model_dir = get_model_results_dir(model_name, user_slug=user_slug)
    sys_log_path = str(model_dir / "execution_log.md")
    Logger.set_master_log_file(sys_log_path)
    
    log_path = str(InstancePaths.log(instance_id, model_dir))
    Logger.bind_log_file(log_path)
    
    Logger.log(f"--- Starting Lean Analysis: {instance_id} | Question: {question} ---")
    start_time = time.time()

    # 1. Context Enrichment (RAG)
    if any(a.name == "TableSelector" for a in agents):
        if getattr(state, "stop_requested", False):
            return state
            
        if use_rag:
            Logger.log_stage_header("✦ Context Enrichment & Schema Alignment")
            state = next(a for a in agents if a.name == "TableSelector").run(state, on_token=on_token)
        else:
            # Skip the agent but still load the full schema for SQL generation
            state = _hydrate_full_schema(state, user_slug)

    # 2. SQL Generation & Refinement Loop
    if any(a.name == "RefinementLoop" for a in agents):
        if getattr(state, "stop_requested", False):
            return state

        Logger.log_stage_header("💡 Technical Insight Formulation")
        state = next(a for a in agents if a.name == "RefinementLoop").run(state, on_token=on_token)
        if on_result and state.chosen_query and state.execution_result:
            on_result(state)

    # 3. Final Business Synthesis
    if any(a.name == "Orchestrator" for a in agents) and not state.error_message:
        if getattr(state, "stop_requested", False):
            return state

        Logger.log_stage_header("📊 Executive Summary")
        state = next(a for a in agents if a.name == "Orchestrator").run(state, on_token=on_token, mode="FINAL")

    state.total_duration = time.time() - start_time
    Logger.log(f"--- Lean Analysis Completed for {instance_id} in {state.total_duration:.2f}s ---")
    return state

def _hydrate_full_schema(state: AgentState, user_slug: str = None) -> AgentState:
    """
    Silently loads the entire database schema into the agent state.
    Used as a fast-path when RAG is disabled.
    """
    try:
        active_conn = DBRepository._get_active_connection(user_slug=user_slug)
        collection_name = DBRepository.get_collection_name(active_conn, state.db_name or "metadata")
        project_slug = get_active_project_slug(user_slug=user_slug)
        metadata_path = get_metadata_dir(user_slug, project_slug) / f"{collection_name}.json"
        
        if not metadata_path.exists():
            Logger.log(f"Metadata not found at {metadata_path}. SQL generation may be degraded.", level="WARNING")
            state.schema_info = {}
            return state

        metadata = SchemaRegistry.get_metadata(str(metadata_path))
        
        full_schema = {}
        all_rag_cols = []
        for tname, tmeta in metadata.items():
            table_cols = []
            for cm in tmeta.get("columns", []):
                col_obj = {
                    "table_name": tname,
                    "column_name": cm.get("column_name"),
                    "type": cm.get("type", "unknown"),
                    "description": cm.get("description", ""),
                    "sample_values": cm.get("sample_values", []),
                    "pk": cm.get("pk", False)
                }
                table_cols.append(col_obj)
                all_rag_cols.append(col_obj)
            full_schema[tname] = {"columns": table_cols, "foreign_keys": tmeta.get("foreign_keys", [])}
        
        state.schema_info = full_schema
        state.rag_columns = all_rag_cols
        state.rag_pool = all_rag_cols
        state.relevant_tables = list(full_schema.keys())
        db_type = (state.connection_details or {}).get("db_type", "postgres")
        state.formatted_rag_pool = format_rag_columns(state.rag_pool, db_type=db_type)
        state.context_reasoning = "RAG disabled: Entire database schema loaded into context via Fast-Path."
        
    except Exception as e:
        Logger.log(f"Fast-Path Schema hydration failed: {str(e)}", level="ERROR")
        
    return state
