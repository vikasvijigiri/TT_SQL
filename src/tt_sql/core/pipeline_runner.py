import os
import time
import json
import re
import types
from typing import Optional, Dict, Any, List

from tt_sql.core.logger import Logger
from tt_sql.core.llm_service import LLMService
from tt_sql.core.agent_base import AgentState
from tt_sql.core.paths import initialize_directories, InstancePaths

# Import Agents
from tt_sql.agents.input_layer import ContextEnrichmentAgent
from tt_sql.agents.planning_layer import StepByStepPlannerAgent
from tt_sql.agents.loop_layer import RefinementLoopAgent
from tt_sql.agents.execution_layer import SQLiteExecutorAgent, PostgresExecutorAgent


def get_agents(llm_service):
    """Factory to create agents with the given LLM service."""
    # Determine executor based on DB_TYPE
    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    executor = PostgresExecutorAgent() if db_type in ["postgres", "postgresql"] else SQLiteExecutorAgent()

    return [
        ContextEnrichmentAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service),
        executor
    ]

class OutputHandler:
    """Handles output logging and optional console printing."""
    def __init__(self, verbose=False):
        self.captured_text = ""
        self.verbose = verbose
        
    def info(self, text):
        self.captured_text += f"[INFO] {text}\n"
        if self.verbose: print(f"[INFO] {text}")
        
    def error(self, text):
        self.captured_text += f"[ERROR] {text}\n"
        if self.verbose: print(f"[ERROR] {text}")
        
    def debug(self, text):
        if self.verbose: print(f"[DEBUG] {text}")

def run_analysis_pipeline(question, db_name, instance_id, model_name, rag_source="qdrant", use_rag=False, rag_limit=3, verbose=False, output_handler=None, stop_checker=None):
    """
    Core pipeline execution logic. Pure Python, no UI dependencies.
    Returns: (final_state, iter_count, is_fatal, captured_transcript)
    """
    # Initialize Logger Global Verbose
    Logger._verbose = verbose
    
    if output_handler is None:
        output_handler = OutputHandler()

    # Paths
    db_path_absolute = str(InstancePaths.database(db_name))

    if not use_rag and not InstancePaths.database(db_name).exists():
        output_handler.error(f"Database not found at {db_path_absolute}")
        return None, 0, True, output_handler.captured_text

    # --- RAG: Upfront collection existence check ---
    if use_rag:
        import requests, urllib3
        urllib3.disable_warnings()
        qdrant_url   = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
        qdrant_key   = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT_API", "")
        collection   = os.getenv("QDRANT_COLLECTION", "")
        headers      = {"api-key": qdrant_key}
        if not collection:
            msg = "[RAG] QDRANT_COLLECTION is not set in .env. Cannot run RAG mode."
            output_handler.error(msg)
            Logger.log(msg, level="ERROR")
            return None, 0, True, output_handler.captured_text
        check_url = f"{qdrant_url}/collections/{collection}"
        try:
            resp = requests.get(check_url, headers=headers, verify=False, timeout=10)
            if resp.status_code == 404:
                msg = (
                    f"[RAG] Collection '{collection}' does not exist in Qdrant.\n"
                    f"Please push your table embeddings to Qdrant collection '{collection}' first."
                )
                output_handler.error(msg)
                Logger.log(msg, level="ERROR")
                return None, 0, True, output_handler.captured_text
            elif resp.status_code != 200:
                msg = f"[RAG] Qdrant returned HTTP {resp.status_code} for collection '{collection}'. Check your QDRANT_URL and QDRANT_API."
                output_handler.error(msg)
                Logger.log(msg, level="ERROR")
                return None, 0, True, output_handler.captured_text
            Logger.log(f"[RAG] Collection '{collection}' verified OK.")
        except requests.exceptions.RequestException as e:
            msg = f"[RAG] Cannot reach Qdrant at {qdrant_url}: {e}"
            output_handler.error(msg)
            Logger.log(msg, level="ERROR")
            return None, 0, True, output_handler.captured_text


    # Initialize directories
    initialize_directories(model_name)

    # Initialize Components
    llm_service = LLMService(model=model_name)
    agents_list = get_agents(llm_service)


    # Build agent map
    agent_map = {agent.name: agent for agent in agents_list}

    # Initial State
    state = AgentState(
        user_query=question,
        db_path=db_path_absolute,
        db_name=db_name,          # pass raw db name for RAG collection routing
        instance_id=instance_id,
        rag_source=rag_source,
        use_rag=use_rag,
        rag_limit=rag_limit,
        model_name=model_name
    )

    # Logger Setup
    safe_model_name = model_name.replace("/", "_").replace(":", "_")
    log_file_path = str(InstancePaths.log(instance_id, model_name))
    Logger.set_log_file(log_file_path)
    Logger.log(f"Started analysis for {instance_id} using {model_name}")
    Logger.log(f"Question: {question}")
    Logger.log(f"Database: {db_name}")

    start_time = time.time()
    


    try:
        Logger.log_stage_header("📥 INPUT LAYER")

        # --- SUB-QUESTION EXECUTION LOOP ---
        questions_to_process = state.sub_questions if state.sub_questions else [question]
        final_states = []
        is_any_fatal = False

        for i, sub_q in enumerate(questions_to_process):
            # Reuse base instance ID (no suffixes)
            sub_id = instance_id
            
            Logger.log(f"--- Starting Task {sub_id}: {sub_q} ---")
            
            # Create sub-state reusing schema & intent
            current_state = AgentState(
                user_query=sub_q,
                db_path=state.db_path,
                db_name=state.db_name,
                instance_id=sub_id,
                rag_source=state.rag_source,
                use_rag=state.use_rag,
                rag_limit=state.rag_limit,
                model_name=state.model_name,
                schema_info=state.schema_info,
                query_intent=state.query_intent
            )
            
            Logger.log_stage_header("📋 PLANNING LAYER")

            # --- Stage 4: Step-by-Step Planner ---
            if stop_checker and stop_checker(): return None, 0, True, output_handler.captured_text
            if "QueryPlanner" in agent_map:
                current_state = agent_map["QueryPlanner"].run(current_state)

            Logger.log_stage_header("📥 CONTEXT ENRICHMENT")

            # --- Stage 6: Context Enrichment (RAG) ---
            if stop_checker and stop_checker(): return None, 0, True, output_handler.captured_text
            if "TableSelector" in agent_map:
                current_state = agent_map["TableSelector"].run(current_state)

            Logger.log_stage_header("⚡ GENERATION LAYER")

            # --- Stage 7: Refinement Loop ---
            if stop_checker and stop_checker(): return None, 0, True, output_handler.captured_text
            # Sync stop signal
            if stop_checker and stop_checker(): current_state.stop_requested = True
            
            if "RefinementLoop" in agent_map:
                current_state = agent_map["RefinementLoop"].run(current_state)

            # --- Stage 8: Final Executor ---
            if stop_checker and stop_checker(): return None, 0, True, output_handler.captured_text
            
            # Run whichever executor is in the map
            executor_name = "PostgresExecutor" if "PostgresExecutor" in agent_map else "SQLiteExecutor"
            if executor_name in agent_map:
                current_state = agent_map[executor_name].run(current_state)

            # Check fatal errors
            if (current_state.chosen_query and "ERROR:" in current_state.chosen_query) or \
               (current_state.error_message and "ERROR:" in current_state.error_message):
                is_any_fatal = True
                
            final_states.append(current_state)
            
        elapsed = time.time() - start_time
        Logger.log(f"Analysis completed in {elapsed:.2f} seconds.")
        last_state = final_states[-1] if final_states else state
        
        # Comprehensive Fatal Error Check
        if not is_any_fatal:
            for s in final_states:
                if (s.execution_result and s.execution_result.error_message) or \
                   (s.error_message and "ERROR:" in s.error_message.upper()) or \
                   (s.chosen_query and "ERROR:" in s.chosen_query.upper()):
                    is_any_fatal = True
                    break

        # Check Fatal Errors
        if is_any_fatal:
            output_handler.error(f"Errors occurred in one or more sub-questions.")

        return last_state, 0, is_any_fatal, output_handler.captured_text

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        output_handler.error(f"Critical Pipeline Error: {str(e)}\n{tb}")
        Logger.log(f"Critical Pipeline Error: {str(e)}\n{tb}", level="ERROR")
        return None, 0, True, output_handler.captured_text
