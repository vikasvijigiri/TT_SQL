import os
import sys
import json
import logging
import argparse
from pathlib import Path
import csv

# Add src to python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from tt_sql.core.llm_service import LLMService
from tt_sql.agents.success_analysis_agent import SuccessAnalysisAgent
from tt_sql.core.paths import InstancePaths, get_model_results_dir
from tt_sql.core.pipeline_config import PipelineConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_ids(csv_path: str) -> list:
    ids = []
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            iid = row.get('instance_id') or row.get('id')
            if iid:
                ids.append(iid)
    return ids

def load_dataset_map(jsonl_path: str) -> dict:
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
    parser = argparse.ArgumentParser(description="Success Analysis Runner")
    parser.add_argument("--csv", required=True, help="Path to CSV file with successful IDs")
    parser.add_argument("--model", required=True, help="Model name used for the run")
    parser.add_argument("--dataset", default=str(PROJECT_ROOT / "data" / "spider2-lite.jsonl"), help="Path to original dataset")
    
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        logger.error(f"Success CSV path does not exist: {os.path.abspath(args.csv)}")
        return

    # Initialize Services
    try:
        pipeline_cfg = PipelineConfig()
        agent_cfg = pipeline_cfg.get_agent_prompt_config("Analyst")
        
        llm = LLMService(model=args.model) 
        agent = SuccessAnalysisAgent(llm, config=agent_cfg)
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return

    # Load Data
    success_ids = load_ids(args.csv)
    dataset = load_dataset_map(args.dataset)
    
    logger.info(f"Loaded {len(success_ids)} successful instances to analyze.")

    # Output directory
    results_dir = get_model_results_dir(args.model)
    analysis_dir = results_dir / "success_reasons"
    analysis_dir.mkdir(exist_ok=True, parents=True)

    count = 0
    for iid in success_ids:
        if iid not in dataset:
            logger.warning(f"Instance ID {iid} not found in dataset. Skipping.")
            continue
            
        instance_data = dataset[iid]
        question = instance_data.get('question')
        
        # Load artifacts
        log_path = InstancePaths.log(iid, args.model)
        sql_path = InstancePaths.sql(iid, args.model)
        schema_path = InstancePaths.schema(iid, args.model)
        
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
        logger.info(f"[{count+1}/{len(success_ids)}] Analyzing success for {iid}...")
        report = agent.analyze_success(
            question=question,
            schema_info=schema_content,
            plan=plan_content,
            generated_sql=sql_content
        )
        
        # Save Report
        output_file = analysis_dir / f"{iid}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
            
        count += 1
        
    logger.info(f"Analysis complete. Reports saved to {analysis_dir}")

if __name__ == "__main__":
    main()
