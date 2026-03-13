import os
import json
import argparse
import sys
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.services.metadata.extraction_service import ExtractionService
from app.services.metadata.enrichment_service import EnrichmentService
from app.repositories.registry.paths import METADATA_DIR, INPUT_QUERIES_DIR
from app.repositories.config import settings

def main():
    parser = argparse.ArgumentParser(description="CLI Wrapper for Metadata Extraction & Enrichment")
    parser.add_argument("--instance-id", type=str, help="Instance ID to detect schema from JSONL")
    parser.add_argument("--input-jsonl", type=str, help="Path to JSONL file for instance detection")
    parser.add_argument("--enrich", action="store_true", help="Enable LLM enrichment")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers for enrichment")
    parser.add_argument("--output", help="Optional output filename (default: <schema>.json)")
    
    args = parser.parse_args()
    extraction_service = ExtractionService()
    enrichment_service = EnrichmentService()
    schema_name = None
    
    # Instance-based schema detection
    if args.instance_id:
        jsonl_path = args.input_jsonl
        if not jsonl_path:
            for cand in ["spider2-lite.jsonl", "sample.jsonl", "user_questions.jsonl"]:
                p = INPUT_QUERIES_DIR / cand
                if p.exists():
                    jsonl_path = str(p)
                    break
        
        if jsonl_path and os.path.exists(jsonl_path):
            print(f"Detecting schema for instance '{args.instance_id}' from {jsonl_path}...")
            detected = None
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if str(data.get("instance_id")) == str(args.instance_id):
                            detected = data.get("db")
                            break
                    except: continue
            if detected:
                print(f"[Detected schema]: {detected}")
                schema_name = detected
    
    if not schema_name:
        schema_name = settings.SCHEMA or "public"
        print(f"[Info] No schema detected/specified, defaulting to: {schema_name}")

    # Use Services
    metadata = extraction_service.extract_metadata(schema_name)
    
    if args.enrich:
        metadata = enrichment_service.enrich_metadata(metadata, args.workers)
        
    output_filename = args.output or f"{schema_name}.json"
    output_path = METADATA_DIR / output_filename
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"\n[OK] Metadata saved to: {output_path}")

if __name__ == "__main__":
    main()
