import os
import json
import psycopg2
import argparse
import sys
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv

# Ensure PYTHONPATH includes project root when running from this script
sys.path.append(os.getcwd())

from app.repositories.registry.paths import METADATA_DIR
from app.services.engines.llm_service import LLMService
from app.repositories.config import settings

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def get_db_connection():
    load_dotenv()
    try:
        conn = psycopg2.connect(
            user=os.getenv("RDS_USER"),
            password=os.getenv("RDS_PASSWORD"),
            host=os.getenv("RDS_HOST"),
            port=os.getenv("RDS_PORT"),
            database=os.getenv("RDS_DATABASE"),
            connect_timeout=30
        )
        return conn
    except Exception as e:
        print(f"[Error] Database Connection Error: {e}")
        sys.exit(1)

def extract_raw_metadata(schema_name: str) -> Dict[str, Any]:
    print(f" Extracting raw schema from database: {schema_name}")
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE';
        """, (schema_name,))
        tables = [r[0] for r in cur.fetchall()]
        total_tables = len(tables)
        print(f" [DB]: Detected {total_tables} tables in schema '{schema_name}'")
        
        metadata = {"schema": schema_name, "tables": {}}
        
        for idx, table_name in enumerate(tables, 1):
            print(f" [{idx}/{total_tables}] Extracting columns: {table_name}...", flush=True)
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema_name, table_name))
            columns = cur.fetchall()
            
            col_meta = []
            for col_name, data_type in columns:
                # Samples
                samples = []
                try:
                    cur.execute(f'SELECT "{col_name}" FROM "{schema_name}"."{table_name}" WHERE "{col_name}" IS NOT NULL LIMIT 3;')
                    samples = [str(r[0]) for r in cur.fetchall()]
                except:
                    conn.rollback()
                
                col_meta.append({
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": data_type,
                    "sample_values": samples
                })
            
            metadata["tables"][table_name] = {"columns": col_meta}
            
        return metadata
    finally:
        print(f" [OK] Raw extraction complete.", flush=True)
        cur.close()
        conn.close()

def enrich_table_worker(table_name: str, columns: List[Dict[str, Any]]) -> Dict[str, str]:
    """Worker function for parallel enrichment of a single table."""
    llm = LLMService()
    print(f" [Enriching]: {table_name}...")
    
    col_list_str = "\n".join([
        f"- {c['column_name']} ({c['type']}). Samples: {c['sample_values']}" 
        for c in columns
    ])
    
    system_prompt = (
        "You are a Senior Data Analyst. Provide concise (1-2 lines), business-oriented descriptions "
        "for the following database columns. Expand abbreviations and use sample values for context."
        "\n\nOutput ONLY a valid JSON object: {\"column_name\": \"description\"}"
    )
    
    user_prompt = f"Table: {table_name}\nColumns:\n{col_list_str}"
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return llm.get_json_completion(messages)
    except Exception as e:
        print(f"  [Warning] Failed to enrich {table_name}: {e}")
        return {}

def parallel_enrichment(metadata: Dict[str, Any], max_workers: int) -> Dict[str, Any]:
    print(f"\n[Extraction & Enrichment]: Starting with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_table = {
            executor.submit(enrich_table_worker, t_name, t_info["columns"]): t_name
            for t_name, t_info in metadata["tables"].items()
        }
        
        for future in as_completed(future_to_table):
            table_name = future_to_table[future]
            try:
                descriptions = future.result()
                if descriptions:
                    for col in metadata["tables"][table_name]["columns"]:
                        name = col["column_name"]
                        col["description"] = descriptions.get(name, f"Data for {name}")
                print(f"  [Finished]: {table_name}", flush=True)
            except Exception as e:
                print(f"  [Error] processing {table_name}: {e}", flush=True)
                
    return metadata

def main():
    parser = argparse.ArgumentParser(description="Parallel Metadata Extraction & Enrichment")
    parser.add_argument("--instance-id", type=str, help="Instance ID to detect schema from JSONL")
    parser.add_argument("--input-jsonl", type=str, help="Path to JSONL file for instance detection")
    parser.add_argument("--enrich", action="store_true", help="Enable LLM enrichment")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers for enrichment")
    parser.add_argument("--output", help="Optional output filename (default: <schema>.json)")
    
    args = parser.parse_args()
    
    schema_name = None
    
    # Instance-based schema detection
    if args.instance_id:
        from app.repositories.registry.paths import INPUT_QUERIES_DIR
        jsonl_path = args.input_jsonl
        if not jsonl_path:
            # Try standard locations
            for cand in ["spider2-lite.jsonl", "sample.jsonl", "user_questions.jsonl"]:
                p = INPUT_QUERIES_DIR / cand
                if p.exists():
                    jsonl_path = str(p)
                    break
        
        if jsonl_path and os.path.exists(jsonl_path):
            print(f"ðŸ” Detecting schema for instance '{args.instance_id}' from {jsonl_path}...")
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
            else:
                print(f"[Warning] Could not find instance '{args.instance_id}' in {jsonl_path}")
        else:
            print(f"[Warning] Input JSONL not found for detection.")

    if not schema_name:
        schema_name = settings.SCHEMA or "public"
        print(f"[Info] No schema detected/specified, defaulting to: {schema_name}")

    metadata = extract_raw_metadata(schema_name)
    
    if args.enrich:
        metadata = parallel_enrichment(metadata, args.workers)
        
    output_filename = args.output or f"{schema_name}.json"
    output_path = METADATA_DIR / output_filename
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"\n[OK] Metadata saved to: {output_path}")

if __name__ == "__main__":
    main()
