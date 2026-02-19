import sys
import os
import json
import csv
import argparse
from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.state import AgentState
from tt_sql.core.llm_service import LLMService
from tt_sql.core.logger import Logger
from tt_sql.core.paths import initialize_directories, InstancePaths, SPIDER_DATASET
from tt_sql.core.file_coordinator import FileCoordinator

# Agents
from tt_sql.agents.input_layer import (
    SQLiteFileLoaderAgent, 
    SchemaAnalyzerAgent, 
    ContextEnrichmentAgent
)
from tt_sql.agents.planning_layer import (
    StepByStepPlannerAgent, 
    RelationshipGraphBuilderAgent
)
from tt_sql.agents.generation_layer import MultiCandidateGeneratorAgent
from tt_sql.agents.loop_layer import RefinementLoopAgent
from tt_sql.agents.execution_layer import SQLiteExecutorAgent

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Run Text2SQL Batch Processing")
    parser.add_argument("--model", type=str, default="bedrock/openai.gpt-oss-safeguard-120b", help="Model name to use")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 for all)")
    args = parser.parse_args()
    
    model_name = args.model
    
    # 1. Initialize Directories using centralized logic
    initialize_directories(model_name)
    
    # Initialize Markdown Logger (Global run log)
    # We might want to store this in results/{model}/logs/batch_run.md?
    # For now, let's keep it in the current directory or use a specific path
    Logger.set_log_file(f"batch_run_{model_name.replace('/', '_')}.md")
    Logger.log_section(f"Batch Runner Started for Model: {model_name}")
    
    # 2. Initialize Services & Agents
    llm_service = LLMService(model=model_name)
    file_coordinator = FileCoordinator()
    
    agents = [
        SQLiteFileLoaderAgent(),
        SchemaAnalyzerAgent(),
        ContextEnrichmentAgent(llm_service),
        RelationshipGraphBuilderAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service),
        # Ensure Executor is included if needed for final execution in pipeline
        # (It interacts with state, but file saving is handled below or by agents)
        SQLiteExecutorAgent() 
    ]
    
    orchestrator = Orchestrator(agents)
    
    # 3. Read JSONL from centralized path
    jsonl_path = SPIDER_DATASET
    Logger.log(f"Reading from {jsonl_path}")
    
    tasks = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tasks.append(json.loads(line))
    else:
        Logger.log(f"Dataset not found at {jsonl_path}", level="ERROR")
        return

    if args.limit > 0:
        tasks = tasks[:args.limit]
        
    Logger.log(f"Found {len(tasks)} tasks to process.")
    
    # 4. Processing Loop
    for i, task in enumerate(tasks):
        instance_id = task.get("instance_id")
        db_name = task.get("db") # e.g., "IPL"
        question = task.get("question")
        
        if not instance_id or not db_name or not question:
            print(f"Skipping invalid task line {i}")
            continue
            
        # Construct DB Path using InstancePaths helper logic
        # (We use InstancePaths.database which handles defaults)
        db_path_obj = InstancePaths.database(db_name)
        db_path = str(db_path_obj)
        
        # Check existence
        if not db_path_obj.exists():
            Logger.log(f"[{i+1}/{len(tasks)}] Skipping: DB not found at {db_path}", level="WARN")
            continue
            
        Logger.log_section(f"[{i+1}/{len(tasks)}] Processing {instance_id} (DB: {db_name})")
        print(f"Processing {instance_id}...")
        
        try:
            # Create Initial State
            initial_state = AgentState(
                user_query=question,
                db_path=db_path,
                instance_id=instance_id,
                model_name=model_name
            )
            
            # Run Pipeline
            final_state = orchestrator.run_pipeline(initial_state)
            
            # Save Results (using FileCoordinator/InstancePaths for consistency)
            
            # 1. SQL File
            generated_sql = final_state.chosen_query or "-- No SQL Generated"
            file_coordinator.write_sql(instance_id, generated_sql, model_name)
            
            Logger.log(f"Final SQL for {instance_id}:")
            Logger.log_code(generated_sql)
            
            # 2. CSV Results File
            if final_state.execution_result and final_state.execution_result.rows:
                Logger.log(f"Execution successful. Rows: {len(final_state.execution_result.rows)}")
                file_coordinator.write_csv(
                    instance_id, 
                    final_state.execution_result.rows, 
                    final_state.execution_result.columns, 
                    model_name
                )
            else:
                 # Create error CSV
                 err_msg = final_state.execution_result.error_message if final_state.execution_result else "No result object"
                 Logger.log(f"Execution failed or empty. Error: {err_msg}", level="WARN")
                 
                 # Manual write for error state since file_coordinator.write_csv expects valid rows/cols
                 # Or we can just write a CSV with a header "Error"
                 csv_path = InstancePaths.csv(instance_id, model_name)
                 with open(csv_path, 'w', newline='', encoding='utf-8') as f_csv:
                     writer = csv.writer(f_csv)
                     writer.writerow(["status", "error"])
                     writer.writerow(["failed", err_msg])

            Logger.log(f"Saved results for {instance_id}")

        except Exception as e:
            Logger.log(f"CRITICAL ERROR processing {instance_id}: {e}", level="ERROR")
            continue

if __name__ == "__main__":
    main()
