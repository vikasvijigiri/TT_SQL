import os
import time
from typing import Callable

from core.agent_base import AgentState
from core.llm_service import LLMService
from core.logger import Logger
from core.metrics_tracker import extract_and_write
from core.paths import InstancePaths, initialize_directories


def reset_pipeline_infrastructure(include_heavy_models: bool = False):
    """
    Resets all global and thread-local state in the pipeline components.
    Useful for ensuring strict isolation between tasks in batch runs.
    """
    LLMService.clear_cache()
    Logger.reset()

    # Cloud Services Reset
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
    log_file_path = str(InstancePaths.log(instance_id, db_name, model_name))
    
    # Initialize directories (Production Entry point)
    initialize_directories(model_name, db_name)
    
    Logger.set_log_file(log_file_path)
    Logger.log("💎" * 30)
    Logger.log(f"# ANALYSIS START: {instance_id}")
    Logger.log("💎" * 30 + "\n")
    
    Logger.log_section("Question and context")
    Logger.log(f"**Question**: {question}  \n")
    Logger.log(f"**Database**: {db_name}  \n")
    Logger.log(f"**Model**: {model_name}  \n")

    # Initialize Logger Global Verbose
    Logger._verbose = verbose

    if output_handler is None:
        output_handler = OutputHandler()

    # Register listener to capture logs in output_handler
    Logger.register_listener(lambda msg, lvl: output_handler.info(msg) if lvl == "INFO" else output_handler.error(msg))

    # Paths
    db_path_absolute = str(InstancePaths.database(db_name))

    is_bigquery = (
        instance_id.startswith("bq") or os.getenv("DB_TYPE", "").lower() == "bigquery"
    )
    is_snowflake = (
        instance_id.startswith("sf") or os.getenv("DB_TYPE", "").lower() == "snowflake"
    )

    if (
        not is_bigquery
        and not is_snowflake
        and not InstancePaths.database(db_name).exists()
    ):
        output_handler.error(f"Database not found at {db_path_absolute}")
        return None, 0, True, output_handler.captured_text

    # Initialize Components (Directly)
    llm_service = LLMService(model=model_name)

    # Determine dialect based on DB_TYPE or instance_id prefix
    db_type_env = os.getenv("DB_TYPE", "sqlite").lower()
    if (instance_id and instance_id.startswith("bq")) or db_type_env == "bigquery":
        dialect = "bigquery"
    elif (instance_id and instance_id.startswith("sf")) or db_type_env == "snowflake":
        dialect = "snowflake"
    elif db_type_env in ["postgres", "postgresql"]:
        dialect = "postgres"
    else:
        dialect = "sqlite"

    # 1. Instantiate Workflow Engine
    from core.workflow_engine import WorkflowEngine
    from core.paths import CONFIG_DIR
    workflow_path = CONFIG_DIR / "workflow.yaml"
    engine = WorkflowEngine(str(workflow_path), llm_service)

    # Initial State (Aligning with run_single constructor)
    state = AgentState(
        user_query=question,
        db_path=db_path_absolute,
        db_name=db_name,
        instance_id=instance_id,
        model_name=model_name,
        external_knowledge=external_knowledge,
        dialect=dialect,
    )
    
    # Bootstrap: Load previous 'best' SQL from disk if it exists
    sql_path = InstancePaths.sql(instance_id, db_name, model_name)
    if sql_path.exists():
        try:
            prev_sql = sql_path.read_text(encoding="utf-8").strip()
            if prev_sql:
                state.previous_run_sql = prev_sql
                Logger.log(f"🔄 Bootstrapping with previous SQL from disk: {instance_id}\n", to_file=False)
        except Exception as e:
            Logger.log(f"⚠️ Failed to load previous SQL: {e}", "WARN")

    start_time = time.time()
    is_any_fatal = False

    try:
        # Run entire pipeline via Workflow Engine
        state = engine.run(state)

        elapsed = time.time() - start_time
        Logger.log(f"Analysis completed in {elapsed:.2f} seconds.")

        # Determine if is_fatal (Same logic as run_single success check)
        is_any_fatal = False
        if (state.execution_result and state.execution_result.error_message) or \
           (state.error_message and "ERROR:" in state.error_message.upper()):
            is_any_fatal = True

        # --- Determine has_data for metrics (mirrors batch_runner logic) ---
        has_data = False
        db_name = state.db_name or "unknown"
        csv_path = InstancePaths.csv(instance_id, db_name, model_name)
        if csv_path.exists():
            with open(csv_path, encoding="utf-8") as f:
                meaningless = ["", '""', "none", "null", "[]", "{}", "nan", "undefined"]
                valid_rows = [r for r in f if any(p.strip().lower() not in meaningless for p in r.split(","))]
                has_data = len(valid_rows) >= 2

        pipeline_status = "SUCCESS" if (not is_any_fatal and has_data) else "FAILED"
        
        Logger.log_final_results(state.chosen_query, str(csv_path), result=state.execution_result)
        Logger.log_metrics(elapsed, getattr(state, "llm_call_count", 0))
        Logger.log_completion(pipeline_status)

        extract_and_write(
            state, is_any_fatal, pipeline_status, has_data,
            pipeline_duration_s=elapsed,
            error_message=state.error_message if state else None,
        )
        # 4. Final Logs (Task 12)
        Logger.log("Analysis Complete. No hardcoded logic used.")

        return state, 0, is_any_fatal, output_handler.captured_text

    except Exception as e:
        elapsed_on_error = time.time() - start_time
        output_handler.error(f"Critical Pipeline Error: {str(e)}")
        Logger.log(f"Critical Pipeline Error: {str(e)}", level="ERROR")
        _state = state if 'state' in dir() else None
        extract_and_write(
            _state, True, "ERROR", False,
            pipeline_duration_s=elapsed_on_error,
            error_message=str(e),
        )
        return None, 0, True, output_handler.captured_text
