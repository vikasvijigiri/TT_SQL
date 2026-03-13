import os
import sys
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path BEFORE any app.* imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.utils.logger import Logger
from app.services.engines.llm_service import LLMService

# Add src to path
from app.services.engines.rag_service import query_qdrant

def test_rag():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Test RAG retrieval")
    parser.add_argument("--query", type=str, help="Query to test (overridden by --input-jsonl and --id)")
    parser.add_argument("--input-jsonl", type=str, help="Path to JSONL file containing questions")
    parser.add_argument("--id", type=str, help="Instance ID to look up in the JSONL")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--turbo", action="store_true", help="Enable instant retrieval (no LLM)")
    args = parser.parse_args()

    # Always enable verbose logging for this test script
    Logger._verbose = True
    import logging
    logging.getLogger("rag_retrieval").setLevel(logging.INFO)

    query = args.query
    db = None

    # JSONL Lookup logic
    if args.input_jsonl and args.id:
        print(f"[Info] Looking up id '{args.id}' in '{args.input_jsonl}'...")
        jsonl_path = Path(args.input_jsonl)
        if not jsonl_path.exists():
            print(f"[Error] File not found: {args.input_jsonl}")
            return
        
        found = False
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if str(record.get('instance_id')) == str(args.id):
                        query = record.get('question')
                        db = record.get('db')
                        print(f"[Info] Found instance: DB='{db}', Question='{query}'")
                        found = True
                        break
                except json.JSONDecodeError:
                    continue
        
        if not found:
            print(f"[Error] Could not find id '{args.id}' in {args.input_jsonl}")
            return

    if not db:
        db = settings.COLLECTION_NAME
        print(f"[Info] Defaulting to collection: {db}")

    if not query:
        print("[Error] Must provide either --query OR (--input-jsonl and --id)")
        return

    print(f"\nTesting {'Turbo ' if args.turbo else ''}RAG on collection: {db}")
    print(f"Query: {query}")
    
    try:
        results = query_qdrant(query, collection_name=db, turbo=args.turbo, instance_id=args.id)
        if not results:
            print("No results found.")
            return

        for set_name, cols in results.get("final_sets", {}).items():
            print(f"\n--- {set_name} ({len(cols)} columns) ---")
            for col in cols:
                # Handle potential missing keys gracefully
                table = col.get('table_name', 'unknown')
                column = col.get('column_name', 'unknown')
                dtype = col.get('type', 'unknown')
                desc = col.get('description', '')
                desc_str = f" | {desc}" if desc else ""
                print(f" - {table}.{column} ({dtype}){desc_str}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rag()
