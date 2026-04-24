import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
 
from agents.sql_builder import RefinementLoopAgent
from agents.executor import (
    BigQueryExecutorAgent,
    PostgresExecutorAgent,
    SnowflakeExecutorAgent,
    SQLiteExecutorAgent,
)
 
# Absolute imports from the package
from agents.query_planner import ContextEnrichmentAgent, StepByStepPlannerAgent
from agents.table_selector import TableSelectorAgent
from core.file_coordinator import FileCoordinator
from core.llm_service import LLMService
from core.logger import Logger
from core.config import get_settings
from core.paths import (
    DATA_DIR,
    InstancePaths,
    get_model_results_dir,
    initialize_directories,
)
from core.state import AgentState


def run_single(target_id: str, model_name: str, use_rag: bool = False, args=None):
    """Run a single Text-to-SQL instance logic."""
    print(
        f"Running single instance: {target_id} with model {model_name}. Use RAG: {use_rag}"
    )

    initialize_directories(model_name)

    log_full_path = InstancePaths.log(target_id, model_name)
    Logger.set_log_file(str(log_full_path))

    llm_service = LLMService(model=model_name)
    file_coordinator = FileCoordinator()

    # Find task
    task_data = None
    dataset_files = []

    if hasattr(args, "dataset") and args.dataset:
        dataset_files.append(Path(args.dataset))

    dataset_files.extend(
        [
            DATA_DIR / "spider2-lite-bigquery.jsonl",
            DATA_DIR / "spider2-lite-snowflake.jsonl",
            DATA_DIR / "spider2-lite-sqlite.jsonl",
            DATA_DIR / "spider2-lite.jsonl",
        ]
    )

    seen = set()
    dataset_files = [
        f for f in dataset_files if f.exists() and not (f in seen or seen.add(f))
    ]

    for ds_path in dataset_files:
        with open(ds_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                t = json.loads(line)
                if t.get("instance_id") == target_id:
                    task_data = t
                    print(f"Found task {target_id} in {ds_path.name}")
                    break
        if task_data:
            break

    if not task_data:
        print(f"Task {target_id} not found in any available datasets.")
        return

    db_path = str(InstancePaths.database(task_data["db"]))

    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    if (target_id and target_id.startswith("bq")) or db_type == "bigquery":
        executor = BigQueryExecutorAgent()
        dialect = "bigquery"
    elif (target_id and target_id.startswith("sf")) or db_type == "snowflake":
        executor = SnowflakeExecutorAgent()
        dialect = "snowflake"
    elif db_type in ["postgres", "postgresql"]:
        executor = PostgresExecutorAgent()
        dialect = "postgres"
    else:
        executor = SQLiteExecutorAgent()
        dialect = "sqlite"

    initial_state = AgentState(
        user_query=task_data["question"],
        db_path=db_path,
        db_name=task_data["db"],
        external_knowledge=task_data.get("external_knowledge"),
        instance_id=target_id,
        use_rag=use_rag,
        model_name=model_name,
        dialect=dialect,
    )

    print("Starting lean execution...")
    Logger.set_log_file(str(log_full_path))
    Logger.log_call("run_single", {"target_id": target_id, "model_name": model_name})

    context_agent = ContextEnrichmentAgent()
    refinement_loop = RefinementLoopAgent(llm_service, executor=executor)

    initial_state = context_agent.run(initial_state)

    Logger.log_call("Step 1: Query Planner")
    planner_agent = StepByStepPlannerAgent(llm_service)
    initial_state = planner_agent.run(initial_state)

    Logger.log_call("Step 2: Table Selector")
    table_selector = TableSelectorAgent(llm_service)
    initial_state = table_selector.run(initial_state)

    Logger.log_call("Step 3: Builder-Critic Loop")
    initial_state = refinement_loop.run(initial_state)

    Logger.log_call("Step 4: Final Executor")
    final_state = executor.run(initial_state)

    print("Execution finished.")

    # --- HIGH-PRECISION SUCCESS CHECK (Reject Ghost Content) ---
    log_path = get_model_results_dir(model_name) / "log" / f"{target_id}.md"
    csv_path = get_model_results_dir(model_name) / "csv" / f"{target_id}.csv"
    
    print(f"Final Validation: Log @ {log_path.name}, CSV @ {csv_path.name}")

    log_success = False
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            if "content-length" in f.read():
                log_success = True
    
    csv_success = False
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            meaningless = ["", '""', "none", "null", "[]", "{}", "nan", "undefined"]
            data_rows = []
            for line in f:
                parts = [p.strip().lower() for p in line.split(",")]
                # A row is meaningful if at least one column has actual content
                if any(p not in meaningless for p in parts):
                    data_rows.append(line)
            
            if len(data_rows) >= 2: # Header + 1 Meaningful Row
                csv_success = True
            else:
                print(f"⚠️ [WARNING]: No meaningful data rows found. (Header only or Empty values).")

    if log_success and csv_success:
        print(f"✅ SUCCESS: Task {target_id} yielded valid SQL and DATA.")
    else:
        status = "FAILED"
        print(f"❌ {status}: Log={log_success}, DataPresence={csv_success}")


def main():
    load_dotenv()
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Run single text-to-SQL instance")
    parser.add_argument("--id", type=str, default="local020", help="Instance ID to run")
    parser.add_argument(
        "--model",
        type=str,
        default=settings.LLM_MODEL,
        help="Model name",
    )
    parser.add_argument("--dataset", type=str, help="Specific dataset file to search")
    parser.add_argument(
        "--use-rag",
        type=bool,
        default=False,
        help="Bypass LLM and use Vector Store similarity for table selection",
    )
    args = parser.parse_args()

    load_dotenv()

    def run_wrapper():
        run_single(args.id, args.model, args.use_rag, args=args)

    run_wrapper()


if __name__ == "__main__":
    main()
