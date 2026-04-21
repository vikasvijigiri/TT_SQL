import os
import time
import threading
import json
import re
from typing import Optional, Dict, Any, List

from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.utils.logger import Logger
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.registry.paths import initialize_directories, InstancePaths, get_model_results_dir, get_metadata_dir

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
                          session_id: Optional[str] = None) -> AgentState:
    """
    Lean, sequential execution of the Text-to-SQL agents.
    Optimized for speed and simplicity by avoiding redundant planning and parallel branches.
    """
    if on_token:
        on_token("✦ ")

    Logger._verbose = verbose
    user_slug = user_email.split('@')[0] if user_email else None
    
    initialize_directories(model_name, user_slug=user_slug)
    llm_service = LLMService(model=model_name)
    
    # Define Simplified Agent Stack
    agents = [
        ContextEnrichmentAgent(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug),
        RefinementLoopAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug),
        OrchestratorAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)
    ]

    # Filter Agents if requested
    if enabled_agents:
        enabled_lower = [a.lower() for a in enabled_agents]
        agents = [a for a in agents if a.name.lower() in enabled_lower]

    # Resolve active database connection
    active_conn = DBRepository._get_active_connection(user_slug=user_slug)
    resolved_db_path = active_conn.get("sqlite_path", "")

    state = AgentState(
        user_query=question,
        db_path=resolved_db_path,
        db_name=active_conn.get("db_name") or active_conn.get("schema") or active_conn.get("database") or db_name,
        instance_id=instance_id,
        use_rag=use_rag,
        model_name=model_name,
        user_email=user_email,
        session_id=session_id,
        connection_details=active_conn
    )

    # Setup Logging
    sys_log_path = str(get_model_results_dir(model_name, user_slug=user_slug) / "execution_log.md")
    Logger.set_master_log_file(sys_log_path)
    
    log_path = str(InstancePaths.log(instance_id, model_name, base_dir=logs_dir, user_slug=user_slug))
    Logger.bind_log_file(log_path)
    
    Logger.log(f"--- Starting Lean Analysis: {instance_id} | Question: {question} ---")
    start_time = time.time()

    # 1. Context Enrichment (RAG)
    selector = next((a for a in agents if a.name == "TableSelector"), None)
    if selector:
        Logger.log_stage_header("✦ Context Enrichment & Schema Alignment")
        state = selector.run(state, on_token=on_token)

    # 2. SQL Generation & Refinement Loop
    loop_agent = next((a for a in agents if a.name == "RefinementLoop"), None)
    if loop_agent:
        Logger.log_stage_header("💡 Technical Insight Formulation")
        state = loop_agent.run(state, on_token=on_token)
        
        # Immediate result delivery to UI
        if on_result and state.chosen_query and state.execution_result:
            on_result(state)

    # 3. Final Business Synthesis
    orchestrator = next((a for a in agents if a.name == "Orchestrator"), None)
    if orchestrator and not (state.error_message and "ERROR:" in state.error_message.upper()):
        Logger.log_stage_header("📊 Executive Summary")
        state = orchestrator.run(state, on_token=on_token, mode="FINAL")

    state.total_duration = time.time() - start_time
    Logger.log(f"--- Lean Analysis Completed for {instance_id} in {state.total_duration:.2f}s ---")
    return state
