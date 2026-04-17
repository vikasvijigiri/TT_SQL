import os
import time
import threading
import json
import re
import types
from typing import Optional, Dict, Any, List

from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.utils.logger import Logger
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.registry.paths import initialize_directories, InstancePaths, get_model_results_dir, get_metadata_dir

# Import Agents
from app.services.agents.input_layer import ContextEnrichmentAgent
from app.services.agents.planning_layer import StepByStepPlannerAgent
from app.services.agents.loop_layer import RefinementLoopAgent
from app.services.agents.execution_layer import SQLiteExecutorAgent, PostgresExecutorAgent
from app.services.agents.orchestration_layer import OrchestratorAgent
from concurrent.futures import ThreadPoolExecutor


# Simple query patterns that don't need a Planner LLM call
_SIMPLE_QUERY_PATTERNS = re.compile(
    r'\b(count|sum|avg|average|total|how many|how much|list all|show all|get all|'
    r'top \d+|bottom \d+|maximum|minimum|max|min)\b',
    re.IGNORECASE
)
_COMPLEX_QUERY_PATTERNS = re.compile(
    r'\b(compare|between|relationship|trend|over time|year.over.year|'
    r'vs\.?|versus|correlat|breakdown|segment|group by|join|rank|percentile)\b',
    re.IGNORECASE
)

def _is_simple_query(question: str) -> bool:
    """Returns True if the query is simple enough to skip the Planner LLM call."""
    if _COMPLEX_QUERY_PATTERNS.search(question):
        return False
    word_count = len(question.split())
    if word_count > 25:  # Long questions are likely complex
        return False
    return bool(_SIMPLE_QUERY_PATTERNS.search(question))


def run_analysis_pipeline(question: str, 
                          db_name: str, 
                          instance_id: str, 
                          model_name: str, 
                          dataset_name: Optional[str] = None,
                          enabled_agents: Optional[List[str]] = None, 
                          use_rag: bool = False, 
                          verbose: bool = False,
                          on_token: callable = None,
                          results_dir: Optional[str] = None,
                          logs_dir: Optional[str] = None) -> AgentState:
    """
    Direct, linear execution of the Text-to-SQL agents.
    """
    print("DEBUG: >>> PIPELINE START")
    if on_token:
        on_token("✦ ")

    Logger._verbose = verbose
    initialize_directories(model_name)
    print(f"DEBUG: Initializing LLMService for model: {model_name}")
    llm_service = LLMService(model=model_name)
    
    # Define Agent Stack
    # Note: RefinementLoopAgent creates its own executor internally â€” no standalone executor needed
    agents = [
        StepByStepPlannerAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir),
        ContextEnrichmentAgent(results_dir=results_dir, logs_dir=logs_dir),
        RefinementLoopAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir),
        OrchestratorAgent(llm_service, results_dir=results_dir, logs_dir=logs_dir)
    ]

    # Filter Agents
    if enabled_agents:
        enabled_lower = [a.lower() for a in enabled_agents]
        agents = [a for a in agents if a.name.lower() in enabled_lower]
        if verbose: Logger.log(f"ðŸš€ Running Agents: {[a.name for a in agents]}", level="INFO")

    # RAG Validation
    if use_rag:
        try:
            import requests
            from app.repositories.config import settings
            q_url = settings.QDRANT_URL.rstrip("/")
            q_key = settings.QDRANT_API_KEY
            coll  = db_name
            if not q_url or not coll:
                raise ValueError("Qdrant URL or db_name (Collection) missing in settings")
            
            resp = requests.get(f"{q_url}/collections/{coll}", headers={"api-key": q_key}, timeout=5)
            if resp.status_code != 200:
                Logger.log(f"âš ï¸ Warning: Qdrant collection '{coll}' access issue (HTTP {resp.status_code})", level="WARNING")
        except Exception as e:
            Logger.log(f"âš ï¸ RAG initialization warning: {e}", level="WARNING")

    # State Setup
    state = AgentState(
        user_query=question,
        db_path=str(InstancePaths.database(db_name)),
        db_name=db_name,
        instance_id=instance_id,
        use_rag=use_rag,
        model_name=model_name
    )

    # Execution Log should be inside model-specific log folder as well
    sys_log_path = str(get_model_results_dir(model_name) / "log" / "execution_log.md")
    Logger.set_master_log_file(sys_log_path)
    
    # Instance-specific log
    log_path = str(InstancePaths.log(instance_id, model_name, base_dir=logs_dir))
    
    # We bind the log file for THIS thread to the instance log
    # This ensures that query-specific details go to qXXX.md
    Logger.bind_log_file(log_path)
    
    Logger.log(f"--- Starting: {instance_id} | Question: {question} ---")
    start_time = time.time()

    start_time = time.time()

    # Planner bypass for simple queries â€” saves ~3-5s on count/list/total questions
    simple_query = _is_simple_query(question)
    if simple_query:
        Logger.log("âš¡ FAST PATH: Simple query detected â€” Planner LLM call bypassed.")
        state.step_by_step_plan = ["Retrieve schema context", "Generate SQL directly", "Execute and return results"]
        state.query_intent = "simple_lookup"    # Execution Loop: Planning Phase
    orchestrator = agents[-1]
    planner = next((a for a in agents if a.name == "StepByStepPlanner"), None)
    selector = next((a for a in agents if a.name == "TableSelector"), None)

    if selector or (planner and not simple_query):
        Logger.log_stage_header("✦ Concurrent Analysis & Strategic Alignment")
        
        # 1. RAG Enrichment (Essential for context)
        if selector:
            state = selector.run(state, on_token=on_token)
            if orchestrator:
                # Fire RAG narration in background
                state_snap = state.copy()
                def _narrate_rag(s, orc=orchestrator, tok=on_token, main_state=state):
                    res = orc.run(s, on_token=tok, mode="RAG")
                    if res.business_summary:
                        main_state.business_summary = (main_state.business_summary or "") + "\n\n---\n\n" + res.business_summary
                threading.Thread(target=_narrate_rag, args=(state_snap,), daemon=True).start()

        # 2. Strategic Planning (using RAG context if available)
        if planner and not simple_query:
            state = planner.run(state, on_token=on_token)
            if orchestrator:
                # Fire Plan narration in background
                state_snap = state.copy()
                def _narrate_plan(s, orc=orchestrator, tok=on_token, main_state=state):
                    res = orc.run(s, on_token=tok, mode="PLAN")
                    if res.business_summary:
                        main_state.business_summary = (main_state.business_summary or "") + "\n\n---\n\n" + res.business_summary
                threading.Thread(target=_narrate_plan, args=(state_snap,), daemon=True).start()

    # 3. Formulating Insights (Parallel Multi-Set Execution)
    Logger.log_stage_header("💡 Formulating Precise Insights")
    
    # Check if we have multiple schema variants to analyze in parallel
    multi_sets = getattr(state, "rag_multi_sets", {})
    if multi_sets and len(multi_sets) > 1:
        Logger.log(f"🚀 Launching Parallel Analysis for {len(multi_sets)} schema variants.")
        
        loop_agent = next((a for a in agents if a.name == "RefinementLoop"), None)
        selector_agent = next((a for a in agents if a.name == "TableSelector"), None) # Need its hydrate_columns
        
        if loop_agent and selector_agent:
            candidates = []
            
            def run_branch(set_name, set_data):
                # Create an isolated state for this branch
                branch_state = state.copy(deep=True)
                branch_state.candidate_results = [] # Clear for sub-branch
                
                # Re-hydrate schema for THIS specific set
                metadata_path = str(get_metadata_dir() / f"{state.db_name}.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f).get("tables", {})
                    
                    branch_hydrated = selector_agent.hydrate_columns(set_data, metadata)
                    branch_state.rag_columns = branch_hydrated
                    
                    # Update schema_info for Generator
                    rag_schema = {}
                    for col in branch_hydrated:
                        tname = col["table_name"]
                        if tname not in rag_schema:
                            rag_schema[tname] = {"columns": [], "foreign_keys": []}
                        rag_schema[tname]["columns"].append(col)
                    branch_state.schema_info = rag_schema
                    branch_state.relevant_tables = list(rag_schema.keys())
                
                # Execute Loop
                # Note: We skip on_intermediate for parallel branches to avoid UI clutter
                branch_state = loop_agent.run(branch_state, on_token=None)
                
                return {
                    "set_name": set_name,
                    "sql": branch_state.chosen_query,
                    "result": branch_state.execution_result,
                    "valid": branch_state.is_result_valid,
                    "columns": branch_state.execution_result.columns if branch_state.execution_result else []
                }

            with ThreadPoolExecutor(max_workers=len(multi_sets)) as executor:
                futures = {executor.submit(run_branch, name, data): name for name, data in multi_sets.items()}
                for future in futures:
                    try:
                        res = future.result()
                        candidates.append(res)
                        Logger.log(f"✅ Branch {res['set_name']} completed. (Valid: {res['valid']})")
                    except Exception as e:
                        Logger.log(f"❌ Branch {futures[future]} failed: {e}", level="ERROR")
            
            state.candidate_results = candidates
            
            # Select a 'best' default to carry forward (Orchestrator will do deeper selection)
            valid_cand = next((c for c in candidates if c['valid']), None)
            best_cand = valid_cand or (candidates[0] if candidates else None)
            
            if best_cand:
                state.chosen_query = best_cand["sql"]
                state.execution_result = best_cand["result"]
                state.is_result_valid = best_cand["valid"]

    else:
        # Fallback to sequential execution if only one set or parallel disabled
        other_agents = [a for a in agents if a.name not in ["StepByStepPlanner", "TableSelector", "Orchestrator"]]
        for agent in other_agents:
            kwargs = {"on_token": on_token}
            if agent.name == "RefinementLoop":
                def bg_narrative(s_snapshot):
                    def run_and_merge():
                        res = orchestrator.run(s_snapshot, on_token=on_token, mode="MID")
                        state.business_summary = res.business_summary
                    threading.Thread(target=run_and_merge, daemon=True).start()
                kwargs["on_intermediate"] = bg_narrative
            
            state = agent.run(state, **kwargs)
            if state.error_message and "ERROR:" in state.error_message.upper():
                break

    # Final Synthesis
    if not (state.error_message and "ERROR:" in state.error_message.upper()):
        Logger.log_stage_header("💡 Executive Summary")
        state = orchestrator.run(state, on_token=on_token, mode="FINAL")

    state.total_duration = time.time() - start_time
    Logger.log(f"--- Analysis Completed for {instance_id} in {state.total_duration:.2f}s ---")
    return state
