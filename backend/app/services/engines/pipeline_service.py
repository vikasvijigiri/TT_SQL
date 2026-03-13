import os
import time
import json
import re
import types
from typing import Optional, Dict, Any, List

from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.utils.logger import Logger
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.registry.paths import initialize_directories, InstancePaths, get_model_results_dir

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
    Logger.set_log_file(sys_log_path)
    
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
        state.query_intent = "simple_lookup"
        state.complexity_score = 1
    # Execution Loop with Parallelization for Start
    orchestrator = agents[-1]
    
    # Planner listed first so its narration fires before RAG's when both finish close together
    # For simple queries, skip the QueryPlanner entirely (already injected a default plan above)
    planner_names = ["TableSelector"] if simple_query else ["QueryPlanner", "TableSelector"]
    planning_agents = [a for a in agents if a.name in planner_names]
    planning_agents.sort(key=lambda a: 0 if a.name == "QueryPlanner" else 1)
    other_agents = [a for a in agents if a.name not in ["QueryPlanner", "TableSelector", "Orchestrator"]]



    if planning_agents:
        Logger.log_stage_header("ðŸ’  Concurrent Analysis & Strategic Alignment")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        with ThreadPoolExecutor(max_workers=len(planning_agents)) as pool:
            def worker_wrapper(agent, state_obj, log_file):
                Logger.bind_log_file(log_file)
                return agent.name, agent.run(state_obj)

            log_file = str(InstancePaths.log(instance_id, model_name, base_dir=logs_dir))
            
            future_to_agent = {
                pool.submit(worker_wrapper, agent, state.copy(), log_file): agent.name 
                for agent in planning_agents
            }
            
            # As each agent finishes, merge state and fire Orchestrator narration
            # as a NON-BLOCKING daemon thread so it doesn't delay the next stage
            for future in as_completed(future_to_agent):
                agent_name, result_state = future.result()
                
                if agent_name == "QueryPlanner":
                    if result_state.step_by_step_plan:
                        state.step_by_step_plan = result_state.step_by_step_plan
                    # Fire narration in background â€” does NOT block RAG or any next step
                    if orchestrator:
                        state_snap = state.copy()
                        def _narrate_plan(s, orc=orchestrator, tok=on_token, main_state=state):
                            res = orc.run(s, on_token=tok, mode="PLAN")
                            if res.business_summary:
                                main_state.business_summary = res.business_summary
                        threading.Thread(target=_narrate_plan, args=(state_snap,), daemon=True).start()
                        
                elif agent_name == "TableSelector":
                    if result_state.schema_info:
                        state.schema_info = result_state.schema_info
                        state.rag_columns = result_state.rag_columns
                        state.rag_pool = result_state.rag_pool
                        state.rag_multi_sets = result_state.rag_multi_sets
                        state.formatted_rag_pool = result_state.formatted_rag_pool
                        state.relevant_tables = result_state.relevant_tables
                    # Fire RAG narration in background too
                    if orchestrator:
                        state_snap = state.copy()
                        def _narrate_rag(s, orc=orchestrator, tok=on_token, main_state=state):
                            res = orc.run(s, on_token=tok, mode="RAG")
                            if res.business_summary:
                                main_state.business_summary = (main_state.business_summary or "") + "\n\n---\n\n" + res.business_summary
                        threading.Thread(target=_narrate_rag, args=(state_snap,), daemon=True).start()
                
                # Merge logs
                if result_state.logs:
                    for log_entry in result_state.logs:
                        if log_entry not in state.logs:
                            state.logs.append(log_entry)

    # 2. Run remaining agents sequentially
    for agent in other_agents:
        stage_label = "Formulating Precise Insights" if agent.name == "RefinementLoop" else "Retrieving Records"
        Logger.log_stage_header(f"ðŸ’  {stage_label}")
        
        kwargs = {"on_token": on_token}
        if agent.name == "RefinementLoop":
            # Use a separate thread for intermediate narrative to avoid blocking the technical loop
            import threading
            def bg_narrative(s_snapshot):
                # We need to eventually merge this back, but for now, we just want it to stream.
                # To actually persist it, we'll let the orchestrator run on the main state object
                # but we must be careful. For safety, we'll just let it update the business_summary
                # of the original state object.
                def run_and_merge():
                    res = orchestrator.run(s_snapshot, on_token=on_token, mode="MID")
                    state.business_summary = res.business_summary
                
                threading.Thread(target=run_and_merge, daemon=True).start()
            kwargs["on_intermediate"] = bg_narrative
            
        state = agent.run(state, **kwargs)
        
        if state.error_message and "ERROR:" in state.error_message.upper():
            Logger.log(f"Pause for technical adjustment: {stage_label}", level="ERROR")
            break

    # Final Synthesis
    if not (state.error_message and "ERROR:" in state.error_message.upper()):
        Logger.log_stage_header("ðŸ’  Executive Summary")
        state = orchestrator.run(state, on_token=on_token, mode="FINAL")

    state.total_duration = time.time() - start_time
    Logger.log(f"--- Analysis Completed for {instance_id} in {state.total_duration:.2f}s ---")
    return state
