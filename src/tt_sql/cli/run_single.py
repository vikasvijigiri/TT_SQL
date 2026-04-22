import sys
import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Absolute imports from the package
from tt_sql.core.pipeline_runner import get_agents
from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.state import AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.logger import Logger
from tt_sql.core.paths import initialize_directories, InstancePaths, SPIDER_DATASET, get_model_results_dir
from tt_sql.core.file_coordinator import FileCoordinator

def run_single(target_id: str, model_name: str, use_rag: bool = False):
    """Run a single Text-to-SQL instance logic."""
    print(f"Running single instance: {target_id} with model {model_name}. RAG bypass: {use_rag}")
    
    initialize_directories(model_name)
    
    log_full_path = InstancePaths.log(target_id, model_name)
    Logger.set_log_file(str(log_full_path))

    llm_service = LLMService(model=model_name)
    file_coordinator = FileCoordinator()
    
    # Use get_agents factory to ensure consistency
    agents = get_agents(llm_service, instance_id=target_id)
    
    orchestrator = Orchestrator(agents)
    
    # Find task
    task_data = None
    if not SPIDER_DATASET.exists():
        print(f"Dataset not found at {SPIDER_DATASET}")
        return

    with open(SPIDER_DATASET, 'r', encoding='utf-8') as f:
        for line in f:
            t = json.loads(line)
            if t.get("instance_id") == target_id:
                task_data = t
                break
                
    if not task_data:
        print(f"Task {target_id} not found in {SPIDER_DATASET}")
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
    
    print("Starting pipeline...")
    final_state = orchestrator.run_pipeline(initial_state)
    print("Pipeline finished.")
    
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
    parser.add_argument("--use-rag", action="store_true", help="Bypass LLM and use Vector Store similarity for table selection")
    args = parser.parse_args()

    load_dotenv()
    run_single(args.id, args.model, args.use_rag)

if __name__ == "__main__":
    main()
