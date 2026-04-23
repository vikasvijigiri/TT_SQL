import os
import time

import requests
import urllib3

from agents.sql_builder import RefinementLoopAgent
from agents.executor import (
    BigQueryExecutorAgent,
    PostgresExecutorAgent,
    SnowflakeExecutorAgent,
    SQLiteExecutorAgent,
)

# (Removed PipelineConfig dependency)
# Import Agents (Consolidated)
from agents.query_planner import ContextEnrichmentAgent, StepByStepPlannerAgent
from agents.table_selector import TableSelectorAgent
from core.agent_base import AgentState
from core.config import get_settings
from core.llm_service import LLMService
from core.logger import Logger
from core.paths import InstancePaths, initialize_directories


def reset_pipeline_infrastructure(include_heavy_models: bool = False):
    """
    Resets all global and thread-local state in the pipeline components.
    Useful for ensuring strict isolation between tasks in batch runs.
    """
    LLMService.clear_cache()
    Logger.reset()
    # 3. Vector Database
    from rag.vector_store import VectorStoreAgent

    VectorStoreAgent.clear_caches(include_models=include_heavy_models)

    # 5. Snowflake Service
    try:
        from core.sf_service import SnowflakeService

        SnowflakeService.reset()
    except Exception:
        pass


# (Removed factory-based get_agents)


class OutputHandler:
    """Handles output logging and optional console printing."""

    def __init__(self, verbose=False):
        self.captured_text = ""
        self.verbose = verbose

    def info(self, text):
        self.captured_text += f"[INFO] {text}\n"
        if self.verbose:
            print(f"[INFO] {text}")

    def error(self, text):
        self.captured_text += f"[ERROR] {text}\n"
        if self.verbose:
            print(f"[ERROR] {text}")

    def debug(self, text):
        if self.verbose:
            print(f"[DEBUG] {text}")


def run_analysis_pipeline(
    question: str,
    db_name: str,
    instance_id: str = "default",
    model_name: str = "default_model",
    rag_source: str = "qdrant",
    use_rag: bool = False,
    rag_limit: int = 3,
    verbose: bool = False,
    output_handler: OutputHandler = None,
    stop_checker: Callable[[], bool] = None,
    external_knowledge: str = None,
):
    """
    Core pipeline execution logic. Pure Python, no UI dependencies.
    Returns: (final_state, iter_count, is_fatal, captured_transcript)
    """
    Logger.log_call(
        "run_analysis_pipeline", {"instance_id": instance_id, "model": model_name}
    )
    # 0. Strict Task Isolation Reset
    reset_pipeline_infrastructure()

    # 1. Initialize Logs immediately to prevent trace loss
    log_file_path = str(InstancePaths.log(instance_id, model_name))
    Logger.set_log_file(log_file_path)
    Logger.log(f"Started analysis for {instance_id} using {model_name}")
    Logger.log(f"Question: {question}")
    Logger.log(f"Database: {db_name}")

    # Initialize Logger Global Verbose
    Logger._verbose = verbose

    if output_handler is None:
        output_handler = OutputHandler()

    # Paths
    db_path_absolute = str(InstancePaths.database(db_name))

    is_bigquery = (
        instance_id.startswith("bq") or os.getenv("DB_TYPE", "").lower() == "bigquery"
    )
    is_snowflake = (
        instance_id.startswith("sf") or os.getenv("DB_TYPE", "").lower() == "snowflake"
    )

    if (
        not use_rag
        and not is_bigquery
        and not is_snowflake
        and not InstancePaths.database(db_name).exists()
    ):
        output_handler.error(f"Database not found at {db_path_absolute}")
        return None, 0, True, output_handler.captured_text

    # --- RAG: Upfront collection existence check (Cached) ---
    settings = get_settings()
    if use_rag:
        if not hasattr(run_analysis_pipeline, "_qdrant_cache"):
            run_analysis_pipeline._qdrant_cache = {}

        cache_key = f"{db_name}"
        if cache_key in run_analysis_pipeline._qdrant_cache:
            use_rag = run_analysis_pipeline._qdrant_cache[cache_key]
        else:
            urllib3.disable_warnings()
            qdrant_url = (settings.QDRANT_URL or "http://localhost:6333").rstrip("/")
            qdrant_key = settings.QDRANT_API_KEY or ""
            collection = db_name
            headers = {"api-key": qdrant_key}

            if not collection:
                Logger.log(
                    "[RAG] No collection specified. Disabling RAG.", level="WARN"
                )
                use_rag = False
                run_analysis_pipeline._qdrant_cache[cache_key] = False
            else:
                check_url = f"{qdrant_url}/collections/{collection}"
                try:
                    resp = requests.get(
                        check_url, headers=headers, verify=False, timeout=5
                    )
                    if resp.status_code == 200:
                        Logger.log(f"[RAG] Collection '{collection}' verified OK.")
                        run_analysis_pipeline._qdrant_cache[cache_key] = True
                        use_rag = True
                    else:
                        Logger.log(
                            f"[RAG] Collection '{collection}' check failed ({resp.status_code}).",
                            level="WARN",
                        )
                        run_analysis_pipeline._qdrant_cache[cache_key] = False
                        use_rag = False
                except Exception as e:
                    Logger.log(f"[RAG] Qdrant unreachable: {e}.", level="WARN")
                    run_analysis_pipeline._qdrant_cache[cache_key] = False
                    use_rag = False

    # Initialize directories (Production Entry point) (5. Done)
    initialize_directories(settings.LLM_MODEL)

    # Initialize Components (Directly)
    llm_service = LLMService(model=model_name)

    # Determine executor and dialect based on DB_TYPE or instance_id prefix
    db_type_env = os.getenv("DB_TYPE", "sqlite").lower()
    if (instance_id and instance_id.startswith("bq")) or db_type_env == "bigquery":
        executor = BigQueryExecutorAgent()
        dialect = "bigquery"
    elif (instance_id and instance_id.startswith("sf")) or db_type_env == "snowflake":
        executor = SnowflakeExecutorAgent()
        dialect = "snowflake"
    elif db_type_env in ["postgres", "postgresql"]:
        executor = PostgresExecutorAgent()
        dialect = "postgres"
    else:
        executor = SQLiteExecutorAgent()
        dialect = "sqlite"

    # Instantiate fixed set of agents
    context_agent = ContextEnrichmentAgent()
    refinement_loop = RefinementLoopAgent(llm_service, executor=executor)

    # Initial State
    state = AgentState(
        user_query=question,
        db_path=db_path_absolute,
        db_name=db_name,  # pass raw db name for RAG collection routing
        instance_id=instance_id,
        rag_source=rag_source,
        use_rag=use_rag,
        rag_limit=rag_limit,
        model_name=model_name,
        external_knowledge=external_knowledge,
        dialect=dialect,
    )

    start_time = time.time()

    try:
        Logger.log_stage_header("📥 INPUT LAYER")

        # --- SUB-QUESTION EXECUTION LOOP ---
        questions_to_process = (
            state.sub_questions if state.sub_questions else [question]
        )
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
                query_intent=state.query_intent,
                external_knowledge=state.external_knowledge,
                dialect=state.dialect,
            )

            # --- Fixed Lean Flow Sequence ---
            if stop_checker and stop_checker():
                return None, 0, True, output_handler.captured_text

            # 1. System Setup (Context Enrichment)
            current_state = context_agent.run(current_state)

            # --- Strict 4-Stage Lean Sequence ---
            if stop_checker and stop_checker():
                return None, 0, True, output_handler.captured_text

            # Step 1: Query Planner
            Logger.log_call("Step 1: Query Planner")
            planner_agent = StepByStepPlannerAgent(llm_service)
            current_state = planner_agent.run(current_state)

            # Step 2: Table Selector
            Logger.log_call("Step 2: Table Selector")
            table_selector = TableSelectorAgent(llm_service)
            current_state = table_selector.run(current_state)

            # Step 3: Builder-Critic Loop
            Logger.log_call("Step 3: Builder-Critic Loop")
            if stop_checker and stop_checker():
                current_state.stop_requested = True
            current_state = refinement_loop.run(current_state)

            # Step 4: Final Executor
            Logger.log_call("Step 4: Final Executor")
            current_state = executor.run(current_state)

            # Stage 8: Final Execution Result
            # (Execution is handled within RefinementLoopAgent to enable iteration)
            if not current_state.execution_result:
                Logger.log(f"No execution result found for {instance_id}")

            # Check fatal errors
            if (
                current_state.chosen_query and "ERROR:" in current_state.chosen_query
            ) or (
                current_state.error_message and "ERROR:" in current_state.error_message
            ):
                is_any_fatal = True

            final_states.append(current_state)

        elapsed = time.time() - start_time
        Logger.log(f"Analysis completed in {elapsed:.2f} seconds.")
        last_state = final_states[-1] if final_states else state

        # Comprehensive Fatal Error Check
        if not is_any_fatal:
            for s in final_states:
                if (
                    (s.execution_result and s.execution_result.error_message)
                    or (s.error_message and "ERROR:" in s.error_message.upper())
                    or (s.chosen_query and "ERROR:" in s.chosen_query.upper())
                ):
                    is_any_fatal = True
                    break

        # Check Fatal Errors
        if is_any_fatal:
            output_handler.error("Errors occurred in one or more sub-questions.")

        return last_state, 0, is_any_fatal, output_handler.captured_text

    except Exception as e:
        output_handler.error(f"Critical Pipeline Error: {str(e)}")
        Logger.log(f"Critical Pipeline Error: {str(e)}", level="ERROR")
        return None, 0, True, output_handler.captured_text
