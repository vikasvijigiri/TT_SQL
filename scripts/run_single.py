import sys
import os
import json
from dotenv import load_dotenv

# Ensure src is in path (scripts/ -> project root -> src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.state import AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.logger import Logger
from tt_sql.core.paths import initialize_directories, InstancePaths, SPIDER_DATASET, get_model_results_dir
from tt_sql.core.file_coordinator import FileCoordinator

from tt_sql.agents.input_layer import (
    ContextEnrichmentAgent
)
from tt_sql.agents.planning_layer import (
    StepByStepPlannerAgent
)
from tt_sql.agents.loop_layer import RefinementLoopAgent
from tt_sql.agents.execution_layer import SQLiteExecutorAgent

import argparse

def main():
    parser = argparse.ArgumentParser(description="Run single text-to-SQL instance")
    parser.add_argument("--use-rag", action="store_true", help="Bypass LLM and use Vector Store similarity for table selection")
    parser.add_argument("--id", type=str, required=True, help="Task ID to run")
    parser.add_argument("--dataset", type=str, default=str(SPIDER_DATASET), help="Dataset JSONL file")
    parser.add_argument("--model", type=str, default=os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b"), help="Model name to use")
    args = parser.parse_args()

    load_dotenv()
    model_name = args.model
    target_id = args.id
    
    print(f"Running single instance: {target_id} with model {model_name}. RAG bypass: {args.use_rag}")
    
    initialize_directories(model_name)
    Logger.set_log_file(f"{target_id}.md") # Just filename, let Logger handle path or use InstancePaths logic?
    # Logger implementation likely writes to CWD if not configured or to a specific path.
    # But batch_runner uses: Logger.set_log_file(f"batch_run_{model_name...}.md")
    # InstancePaths.log() returns the FULL path.
    # UI/Orchestrator usually handles this differently.
    
    # Actually, InstancePaths.log(target_id, model_name) returns the path. 
    # But Logger might expect just a filename if it manages the dir, or full path?
    # Let's check Logger? 
    # Assuming Logger writes to where we tell it.
    log_full_path = InstancePaths.log(target_id, model_name)
    Logger.set_log_file(str(log_full_path))

    llm_service = LLMService(model=model_name)
    file_coordinator = FileCoordinator()
    
    agents = [
        ContextEnrichmentAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service),
        SQLiteExecutorAgent() 
    ]
    
    orchestrator = Orchestrator(agents)
    print(f"Orchestrator loaded agents: {[a.name for a in orchestrator.agents]}")
    
    task_data = None
    with open(args.dataset, 'r', encoding='utf-8') as f:
        for line in f:
            t = json.loads(line)
            if t.get("instance_id") == target_id:
                task_data = t
                break
                
    if not task_data:
        print(f"Task {target_id} not found in {args.dataset}")
        return

    db_path = str(InstancePaths.database(task_data['db']))
    
    initial_state = AgentState(
        user_query=task_data['question'],
        db_path=db_path,
        instance_id=target_id,
        use_rag=args.use_rag,
        model_name=model_name
    )
    
    print("Starting pipeline...")
    final_state = orchestrator.run_pipeline(initial_state)
    print("Pipeline finished.")
    
    # Check if log has content-length (ResponseMetadata)
    log_path = get_model_results_dir(model_name) / "log" / f"{target_id}.md"
    print(f"Checking log at {log_path}")
    
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "content-length" in content:
                print("SUCCESS: 'content-length' found in log.")
                # print(content.split("content-length")[1][:100])
            else:
                print("FAILURE: 'content-length' NOT found in log.")
    else:
        print("Log file not found.")

if __name__ == "__main__":
    main()
