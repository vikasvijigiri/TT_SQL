import json
import os
import argparse
import sys
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.repositories.config import settings
from app.repositories.registry.paths import METADATA_DIR, RESOURCES_DIR, INPUT_QUERIES_DIR
from app.services.metadata.ingestion_service import IngestService

def main():
    parser = argparse.ArgumentParser(
        description="CLI Wrapper for Ingesting Metadata into Qdrant"
    )
    parser.add_argument(
        "--path", "--metadata-file",
        type=str,
        default=None,
        help="Path to the metadata JSON file"
    )
    parser.add_argument(
        "--input-jsonl",
        type=str,
        default=None,
        help="Path to the JSONL file to detect collection name from"
    )
    args = parser.parse_args()
    ingestion_service = IngestService()
    
    collection_name = None
    # Detect collection name
    if args.input_jsonl and os.path.exists(args.input_jsonl):
        try:
            with open(args.input_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("db"):
                        collection_name = data["db"]
                        print(f"[Info] Detected collection name '{collection_name}' from {args.input_jsonl}")
                        break
        except Exception as e:
            print(f"[Warning] Failed to parse {args.input_jsonl}: {e}")

    if not collection_name:
        collection_name = settings.COLLECTION_NAME

    # Resolve metadata path
    json_path = args.path
    if not json_path:
        candidates = [
            METADATA_DIR / f"{collection_name}.json",
            RESOURCES_DIR / f"{collection_name}.json",
            INPUT_QUERIES_DIR / f"{collection_name}.json",
            METADATA_DIR / 'metadata_injestion_files.json'
        ]
        for cand in candidates:
            if cand.exists():
                json_path = str(cand)
                print(f"[Info] Auto-detected metadata file: {json_path}")
                break

    if not json_path or not os.path.exists(json_path):
        print(f"Error: Could not resolve metadata JSON path.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Use Service
    ingestion_service.ingest_to_vector_store(metadata, collection_name)
    print(f"\n[OK] Ingestion complete for {collection_name}")

if __name__ == "__main__":
    main()
