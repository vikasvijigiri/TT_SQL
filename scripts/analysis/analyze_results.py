import os
import sys
import json
import logging
import argparse
import csv
import re
from pathlib import Path
from tqdm import tqdm

# New standard project root calculation relative to scripts/analysis/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "src")) # Keeping it for now as these are external scripts

from tt_sql.core.paths import get_model_results_dir

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_ids_with_status(csv_path: str) -> list:
    """Load instance IDs and their status from CSV."""
    instances = []
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            iid = row.get('instance_id') or row.get('id')
            # If status column missing, assume FAILED if we are in analysis script
            status = row.get('status', 'FAILED').upper()
            if iid:
                instances.append({"iid": iid, "status": status})
    return instances

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

def parse_category_from_md(md_path: Path) -> str:
    """Parse the **Category** line from a failure analysis Markdown file."""
    if not md_path.exists():
        return "Report Missing"
    
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Match "**Category**: hallucination, logic" etc.
        match = re.search(r"\*\*Category\*\*:\s*(.*)", content, re.IGNORECASE)
        if match:
            return match.group(1).strip().strip('\\')
        return "Category Not Found"
    except Exception as e:
        logger.error(f"Error reading {md_path}: {e}")
        return "Error Reading Report"

def main():
    parser = argparse.ArgumentParser(description="Consolidated Classified Analysis Runner (Parsing from MD)")
    parser.add_argument("--csv", help="Path to CSV file with instance IDs and status")
    parser.add_argument("--model", required=True, help="Model name used for the run")
    parser.add_argument("--dataset", default=str(PROJECT_ROOT / "data" / "spider2-lite.jsonl"), help="Path to original dataset")
    parser.add_argument("--output", help="Path to output CSV (default: results/<model>/analysis_classification.csv)")
    
    args = parser.parse_args()

    # Load Dataset
    dataset = load_dataset_map(args.dataset)

    # Paths
    results_dir = get_model_results_dir(args.model)
    failed_dir = results_dir / "failed_reasons"
    success_dir = results_dir / "success_reasons"
    output_path = Path(args.output) if args.output else results_dir / "analysis_classification.csv"

    # Load Data
    instances = []
    if args.csv and os.path.exists(args.csv):
        instances = load_ids_with_status(args.csv)
        logger.info(f"Loaded {len(instances)} instances from {args.csv}.")
    else:
        logger.info(f"No valid CSV provided. Scanning result directories for {args.model}...")
        # Scan success_reasons
        if success_dir.exists():
            for f in success_dir.glob("*.md"):
                instances.append({"iid": f.stem, "status": "SUCCESS"})
        # Scan failed_reasons
        if failed_dir.exists():
            for f in failed_dir.glob("*.md"):
                instances.append({"iid": f.stem, "status": "FAILED"})
        logger.info(f"Found {len(instances)} reported instances in directories.")
    
    if not instances:
        logger.error("No instances found to analyze.")
        return

    results = []
    
    for item in tqdm(instances, desc="Parsing"):
        raw_iid = item["iid"]
        status = item["status"]
        
        # Strip prefixes like 'sf_' if present
        iid = re.sub(r'^sf_', '', raw_iid)
        
        if iid not in dataset:
            logger.warning(f"Instance ID {iid} (from {raw_iid}) not found in dataset. Skipping.")
            continue
            
        instance_data = dataset[iid]
        question = instance_data.get('question', '')

        classification = "Unknown"
        
        # Check success reasons first
        success_md = success_dir / f"{iid}.md"
        failed_md = failed_dir / f"{iid}.md"
        
        if success_md.exists():
            classification = "Success"
        elif failed_md.exists():
            classification = parse_category_from_md(failed_md)
        else:
            classification = "Report Missing"

        if classification != "Success":
            results.append({
                "instance_ID": raw_iid, # Keep original ID (with sf_ prefix if it was there)
                "user_query": question,
                "failed reason as only classification": classification
            })
        
    # Write to CSV
    fieldnames = ["instance_ID", "user_query", "failed reason as only classification"]
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
            
    logger.info(f"Consolidation complete. Results saved to {output_path}")

if __name__ == "__main__":
    main()
