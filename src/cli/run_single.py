import sys
import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Absolute imports from the package
# Agent Imports (Consolidated)
from agents.planner import ContextEnrichmentAgent, StepByStepPlannerAgent
from agents.selector import TableSelectorAgent
from agents.builder import RefinementLoopAgent
from agents.executor import SQLiteExecutorAgent, PostgresExecutorAgent, BigQueryExecutorAgent, SnowflakeExecutorAgent

from core.state import AgentState
from core.llm_service import LLMService
from core.logger import Logger
from core.paths import (
    initialize_directories, 
    InstancePaths, 
    DATA_DIR, 
    get_model_results_dir
)
from core.file_coordinator import FileCoordinator

def run_single(target_id: str, model_name: str, use_rag: bool = False, args=None):
    """Run a single Text-to-SQL instance logic."""
    print(f"Running single instance: {target_id} with model {model_name}. Use RAG: {use_rag}")
    
    initialize_directories(model_name)
    
    log_full_path = InstancePaths.log(target_id, model_name)
    Logger.set_log_file(str(log_full_path))

    llm_service = LLMService(model=model_name)
    file_coordinator = FileCoordinator()
    
    # (Removed Orchestrator setup)
    
    # Find task
    task_data = None
    dataset_files = []
    
    # 1. If a specific dataset is provided, check that first
    if hasattr(args, 'dataset') and args.dataset:
        dataset_files.append(Path(args.dataset))
    
    # 2. Otherwise/also check known spider datasets
    dataset_files.extend([
        DATA_DIR / "spider2-lite-bigquery.jsonl",
        DATA_DIR / "spider2-lite-snowflake.jsonl",
        DATA_DIR / "spider2-lite-sqlite.jsonl",
        DATA_DIR / "spider2-lite.jsonl"
    ])
    
    # deduplicate while preserving order
    seen = set()
    dataset_files = [f for f in dataset_files if f.exists() and not (f in seen or seen.add(f))]

    for ds_path in dataset_files:
        with open(ds_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
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

    db_path = str(InstancePaths.database(task_data['db']))
    
    initial_state = AgentState(
        user_query=task_data['question'],
        db_path=db_path,
        db_name=task_data['db'],
        external_knowledge=task_data.get('external_knowledge'),
        instance_id=target_id,
        use_rag=use_rag,
        model_name=model_name
    )
    
    print("Starting lean execution...")
    Logger.set_log_file(str(log_full_path))
    Logger.log_call("run_single", {"target_id": target_id, "model_name": model_name})
    
    # 1. Determine executor based on DB_TYPE or target_id prefix
    db_type = os.getenv("DB_TYPE", "sqlite").lower()
    if (target_id and target_id.startswith("bq")) or db_type == "bigquery":
        executor = BigQueryExecutorAgent()
    elif (target_id and target_id.startswith("sf")) or db_type == "snowflake":
        executor = SnowflakeExecutorAgent()
    elif db_type in ["postgres", "postgresql"]:
        executor = PostgresExecutorAgent()
    else:
        executor = SQLiteExecutorAgent()

    # 2. Instantiate and Run Agents (Strict 4-Stage Sequence)
    # Simplified imports already handled at top level if needed, 
    # but keeping them here for local scope if preferred, updated to new paths:
    from agents.planner import StepByStepPlannerAgent
    from agents.selector import TableSelectorAgent
    
    context_agent = ContextEnrichmentAgent()
    refinement_loop = RefinementLoopAgent(llm_service, executor=executor)

    # Stage 0: Context Enrichment
    initial_state = context_agent.run(initial_state)

    # Step 1: Query Planner
    Logger.log_call("Step 1: Query Planner")
    planner_agent = StepByStepPlannerAgent(llm_service)
    initial_state = planner_agent.run(initial_state)

    # Step 2: Table Selector
    Logger.log_call("Step 2: Table Selector")
    table_selector = TableSelectorAgent(llm_service)
    initial_state = table_selector.run(initial_state)

    # Step 3: Builder-Critic Loop
    Logger.log_call("Step 3: Builder-Critic Loop")
    initial_state = refinement_loop.run(initial_state)

    # Step 4: Final Executor
    Logger.log_call("Step 4: Final Executor")
    final_state = executor.run(initial_state)
    
    print("Execution finished.")
    
    # Check if log has content-length (ResponseMetadata)
    log_path = get_model_results_dir(model_name) / "log" / f"{target_id}.md"
    print(f"Checking log at {log_path}")
    
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "content-length" in content:
                print("SUCCESS: 'content-length' found in log.")
            else:
                print("FAILURE: 'content-length' NOT found in log.")
    else:
        print("Log file not found.")

def main():
    parser = argparse.ArgumentParser(description="Run single text-to-SQL instance")
    parser.add_argument("--id", type=str, default="local020", help="Instance ID to run")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b"), help="Model name")
    parser.add_argument("--dataset", type=str, help="Specific dataset file to search")
    parser.add_argument("--use-rag", type=bool, default=False, help="Bypass LLM and use Vector Store similarity for table selection")
    args = parser.parse_args()

    load_dotenv()
    # Pass args object so run_single can access args.dataset
    def run_wrapper():
        run_single(args.id, args.model, args.use_rag, args=args)
    
    run_wrapper()

if __name__ == "__main__":
    main()
