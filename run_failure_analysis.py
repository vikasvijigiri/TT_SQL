import os
import sys
import json
import logging
import argparse
from pathlib import Path
import csv

# Add src to python path if running from root
sys.path.append(str(Path(__file__).parent / "src"))

from tt_sql.core.llm_service import LLMService
from tt_sql.agents.failure_analysis_agent import FailureAnalysisAgent
from tt_sql.core.logger import Logger
from tt_sql.core.paths import InstancePaths, get_model_results_dir

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_failed_ids(csv_path: str) -> list:
    """Load list of instance IDs from CSV."""
    ids = []
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Assuming 'instance_id' or 'id' column
            iid = row.get('instance_id') or row.get('id')
            if iid:
                ids.append(iid)
    return ids

def load_dataset_map(jsonl_path: str) -> dict:
    """Load dataset into a dict mapping instance_id to instance data."""
    data_map = {}
    if not os.path.exists(jsonl_path):
        logger.error(f"Dataset file not found: {jsonl_path}")
        return {}
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                data_map[item.get('instance_id')] = item
    return data_map

def main():
    parser = argparse.ArgumentParser(description="Failure Analysis Runner")
    parser.add_argument("--csv", required=True, help="Path to CSV file with failed IDs")
    parser.add_argument("--model", required=True, help="Model name used for the run")
    parser.add_argument("--dataset", default="spider2-lite.jsonl", help="Path to original dataset")
    
    args = parser.parse_args()

    # validate paths
    if not os.path.exists(args.csv):
        x = os.path.abspath(args.csv)
        logger.error(f"Failed CSV path does not exist: {x}")
        return

    # Initialize Services
    try:
        llm = LLMService(model=args.model) # Use same model or a stronger one? Usually same for now.
        agent = FailureAnalysisAgent(llm)
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return

    # Load Data
    failed_ids = load_failed_ids(args.csv)
    dataset = load_dataset_map(args.dataset)
    
    logger.info(f"Loaded {len(failed_ids)} failed instances to analyze.")

    # Output directory
    results_dir = get_model_results_dir(args.model)
    analysis_dir = results_dir / "failed_reasons"
    analysis_dir.mkdir(exist_ok=True, parents=True)

    count = 0
    for iid in failed_ids:
        if iid not in dataset:
            logger.warning(f"Instance ID {iid} not found in dataset. Skipping.")
            continue
            
        instance_data = dataset[iid]
        question = instance_data.get('question')
        gold_sql = instance_data.get('query') # Assuming standard spider format? or 'query'?
        
        # Load artifacts from the run
        # We need: Plan, SQL, Schema, Log
        # Best source for context is the log file or plan file.
        
        log_path = InstancePaths.log(iid, args.model)
        sql_path = InstancePaths.sql(iid, args.model)
        schema_path = InstancePaths.schema(iid, args.model)
        
        # Read content
        plan_content = "Plan not found."
        if log_path.exists():
             with open(log_path, 'r', encoding='utf-8') as f:
                 plan_content = f.read()
        
        sql_content = "SQL not found."
        if sql_path.exists():
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                
        schema_content = {}
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_content = json.load(f)

        # Run Analysis
        logger.info(f"[{count+1}/{len(failed_ids)}] Analyzing {iid}...")
        report = agent.analyze_failure(
            question=question,
            schema_info=schema_content,
            plan=plan_content, # Using the full log as context for the plan/execution
            generated_sql=sql_content,
            gold_sql=gold_sql
        )
        
        # Save Report
        output_file = analysis_dir / f"{iid}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
            
        count += 1
        
    logger.info(f"Analysis complete. Reports saved to {analysis_dir}")

if __name__ == "__main__":
    main()
