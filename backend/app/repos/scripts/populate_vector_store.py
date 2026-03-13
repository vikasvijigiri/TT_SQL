import json
import os
import requests
import argparse
from sentence_transformers import SentenceTransformer

import sys
from pathlib import Path

from app.models.config import settings
from app.models.paths import REPO_DIR

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def raw_socket_request(url_str, api_key, payload_dict=None, path="", method="GET"):
    """HTTP helper using requests library for robustness."""
    full_url = url_str.rstrip('/') + path
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    try:
        if method == "GET":
            response = requests.get(full_url, headers=headers, timeout=30)
        elif method == "PUT":
            response = requests.put(full_url, headers=headers, json=payload_dict, timeout=30)
        elif method == "DELETE":
            response = requests.delete(full_url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, json=payload_dict, timeout=30)
        return True, response.json()
    except Exception as e:
        return False, str(e)

# -------------------------------------------------------------------
# Component 1: Table-Level Chunking
# Generates a single summary vector per table for Stage 1 retrieval.
# -------------------------------------------------------------------
def format_table_document(table_name, columns):
    col_names = ", ".join(c.get("column_name", "") for c in columns)
    return f"TABLE: {table_name}. COLUMNS: {col_names}."

def format_column_document(table_name, column_name, description=""):
    doc = (
        f"TABLE: {table_name}\n"
        f"COLUMN: {column_name}"
    )
    if description:
        doc += f"\nDESCRIPTION: {description}"
    return doc


def populate_cloud_inference(json_file_path=None, collection_name=None, input_jsonl=None):
    print("Preparing Raw Documents for Cloud Ingestion...")
    
    # If input_jsonl is provided, try to detect collection_name from it if not specified
    if input_jsonl and os.path.exists(input_jsonl) and not collection_name:
        try:
            with open(input_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    collection_name = data.get("db")
                    if collection_name:
                        print(f"[Info] Detected collection name '{collection_name}' from {input_jsonl}")
                        break
        except Exception as e:
            print(f"[Warning] Failed to parse {input_jsonl}: {e}")

    # Fallback to setting if still None
    if not collection_name:
        collection_name = settings.COLLECTION_NAME

    if json_file_path is None:
        # 1. New repository locations
        from app.models.paths import METADATA_DIR, RESOURCES_DIR, INPUT_QUERIES_DIR
        
        candidates = [
            METADATA_DIR / f"{collection_name}.json",
            RESOURCES_DIR / f"{collection_name}.json",
            INPUT_QUERIES_DIR / f"{collection_name}.json",
            METADATA_DIR / 'metadata_injestion_files.json'
        ]
        
        for cand in candidates:
            if cand.exists():
                json_file_path = str(cand)
                print(f"[Info] Auto-detected schema specific metadata file: {json_file_path}")
                break

    if json_file_path and not os.path.exists(json_file_path):
        print(f"Error: Metadata file not found at {json_file_path}")
        return

    if not json_file_path:
        print("Error: Could not resolve metadata JSON path.")
        return

    with open(json_file_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    schema_name = metadata.get("schema", "public")
    tables = metadata.get("tables", {})

    qdrant_url = settings.QDRANT_URL
    qdrant_api = settings.QDRANT_API_KEY

    print("Dropping old collection...")
    raw_socket_request(qdrant_url, qdrant_api, path=f"/collections/{collection_name}", method="DELETE")

    print(f"Creating collection '{collection_name}' for local embeddings (size {settings.EMBEDDING_SIZE})...")
    create_payload = {
        "vectors": {
            "text_embedding": {
                "size": settings.EMBEDDING_SIZE,
                "distance": "Cosine"
            }
        }
    }
    success, res = raw_socket_request(qdrant_url, qdrant_api, payload_dict=create_payload, path=f"/collections/{collection_name}", method="PUT")
    print(f"Collection created: {res}")

    # Create payload indexes so chunk_type and table_name can be used for filtering
    print("Creating payload indexes for filtering...")
    for field, schema in [("chunk_type", "keyword"), ("table_name", "keyword")]:
        r = requests.put(
            f"{qdrant_url.rstrip('/')}/collections/{collection_name}/index",
            headers={"api-key": qdrant_api, "Content-Type": "application/json"},
            json={"field_name": field, "field_schema": schema},
            timeout=30
        )
        print(f"  Index '{field}': {r.json().get('status', r.json())}")

    print(f"Loading local embedding model: {settings.EMBEDDING_MODEL}...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)

    print("Building and uploading document chunks...")
    points = []
    global_id = 1

    for table_name, table_info in tables.items():
        columns = table_info.get("columns", [])

        # --- Component 1: One table-level chunk per table ---
        table_doc_text = format_table_document(table_name, columns)
        table_vector = model.encode(table_doc_text).tolist()
        
        points.append({
            "id": global_id,
            "vector": {
                "text_embedding": table_vector
            },
            "payload": {
                "chunk_type": "table",
                "table_name": table_name,
                "column_names": [c.get("column_name") for c in columns],
                "document_text": table_doc_text
            }
        })
        global_id += 1

        # --- Component 2: One column-level chunk per column ---
        for col in columns:
            col_name = col.get("column_name")
            
            # Simple Traditional format (Pure names + description if available)
            col_desc = col.get("description", "")
            doc_text = format_column_document(table_name, col_name, col_desc)
            col_vector = model.encode(doc_text).tolist()

            points.append({
                "id": global_id,
                "vector": {
                    "text_embedding": col_vector
                },
                "payload": {
                    "chunk_type": "column",
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": col.get("type"),
                    "description": col_desc,
                    "sample_values": col.get("sample_values", []),
                    "document_text": doc_text
                }
            })
            global_id += 1

    col_count = sum(1 for p in points if p["payload"].get("chunk_type") == "column")
    tbl_count = sum(1 for p in points if p["payload"].get("chunk_type") == "table")
    print(f"DEBUG: Processing {tbl_count} table points and {col_count} column points.")

    # Batching to avoid payload size limits with high-dimensional vectors (BGE 768)
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        print(f"  Upserting batch {i//batch_size + 1} ({len(batch)} points)...")
        upsert_payload = {"points": batch}
        success, upsert_res = raw_socket_request(
            qdrant_url,
            qdrant_api,
            payload_dict=upsert_payload,
            path=f"/collections/{collection_name}/points?wait=true",
            method="PUT"
        )
        if not success:
            print(f"CRITICAL: Batch upsert failed: {upsert_res}")
            return

    print("Upsert Complete.")

    print("Done!", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Push database schema metadata to Qdrant Cloud using Server-Side Inference."
    )
    parser.add_argument(
        "--path",
        "--metadata-file",
        type=str,
        default=None,
        help="Path to the metadata JSON file (default: app/repos/data/metadata_extracts/<schema>.json)"
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=settings.COLLECTION_NAME,
        help=f"The Qdrant collection name to push to (default: {settings.COLLECTION_NAME})"
    )
    parser.add_argument(
        "--input-jsonl",
        type=str,
        default=None,
        help="Path to the JSONL file to detect collection name from"
    )
    args = parser.parse_args()
    populate_cloud_inference(json_file_path=args.path, collection_name=args.collection_name, input_jsonl=args.input_jsonl)
