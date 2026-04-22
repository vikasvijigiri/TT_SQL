import json
import os
import uuid
import socket
import ssl
import argparse
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# Absolute imports from the package
from tt_sql.core.paths import DATA_DIR, PROJECT_ROOT

def get_qdrant_creds():
    url = os.environ.get("QDRANT_URL", "").strip()
    api_key = (os.environ.get("QDRANT_API") or os.environ.get("QDRANT_API_KEY", "")).strip()
    if not url:
        raise EnvironmentError("QDRANT_URL is not set in .env")
    if not api_key:
        raise EnvironmentError("QDRANT_API / QDRANT_API_KEY is not set in .env")
    return url, api_key

def raw_socket_request(url_str, api_key, payload_dict=None, path="", method="GET"):
    parsed = urlparse(url_str)
    host = parsed.hostname
    port = parsed.port or 443
    
    payload_bytes = b""
    if payload_dict is not None:
        payload_bytes = json.dumps(payload_dict).encode('utf-8')
    
    headers = [
        f"{method} {path} HTTP/1.1",
        f"Host: {host}:{port}",
        f"api-key: {api_key}",
        f"Connection: close"
    ]
    if payload_bytes:
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(payload_bytes)}")
        
    request = ("\r\n".join(headers) + "\r\n\r\n").encode('utf-8') + payload_bytes

    print(f"  -> Connecting to {host}:{port}...")
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                print(f"  -> Sending {method} request...")
                ssock.sendall(request)
                response = b""
                print(f"  -> Waiting for response...")
                while True:
                    chunk = ssock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
    except socket.timeout:
        print(f"  [!] ERROR: Connection to Qdrant Cloud timed out after 10 seconds!")
        return False, "TIMEOUT"
    except Exception as e:
        print(f"  [!] ERROR: Network failure: {str(e)}")
        return False, str(e)
                
    resp_str = response.decode('utf-8')
    body_start = resp_str.find("\r\n\r\n")
    if body_start != -1:
        body = resp_str[body_start + 4:]
        try:
            return True, json.loads(body)
        except:
            if "status" in body: 
                return True, body
    return False, resp_str

def format_column_document(table_name, column_name, data_type, is_pk):
    pk_str = "Yes" if is_pk else "No"
    return f"Table: {table_name}, Column: {column_name}, Type: {data_type}, Primary Key: {pk_str}"

def populate_cloud_inference(json_file_path=None, collection_name="database_schemas_cloud"):
    print("Preparing Raw Documents for Cloud Inference...")
    if json_file_path is None:
        json_file_path = DATA_DIR / 'metadata_injestion_files.json'
    else:
        json_file_path = Path(json_file_path)
        
    if not json_file_path.exists():
        print(f"Error: {json_file_path} not found.")
        return

    with open(json_file_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    schema_name = metadata.get("schema", "public")
    tables = metadata.get("tables", {})
    
    qdrant_url, qdrant_api = get_qdrant_creds()

    print(f"Dropping old collection...")
    raw_socket_request(qdrant_url, qdrant_api, path=f"/collections/{collection_name}", method="DELETE")

    print(f"Creating collection {collection_name} configured for FastEmbed Inference...")
    create_payload = {
        "vectors": {
            "text_embedding": {
                "size": 384,
                "distance": "Cosine"
            }
        }
    }
    
    success, res = raw_socket_request(qdrant_url, qdrant_api, payload_dict=create_payload, path=f"/collections/{collection_name}", method="PUT")
    print(f"Collection created: {res}")
    
    print("Uploading Document strings Cloud Inference...")
    
    points = []
    global_id = 1
    
    for table_name, table_info in tables.items():
        for col in table_info.get("columns", []):
            col_name = col.get("name")
            data_type = col.get("type")
            is_pk = col.get("pk", False)
            
            doc_text = format_column_document(table_name, col_name, data_type, is_pk)
            
            points.append({
                "id": global_id,
                "vector": {
                    "text_embedding": {
                        "model": "sentence-transformers/all-MiniLM-L6-v2",
                        "text": doc_text
                    }
                },
                "payload": {
                    "table_name": table_name,
                    "column_name": col_name,
                    "type": data_type,
                    "description": doc_text,
                    "pk": is_pk
                }
            })
            global_id += 1
        
    upsert_payload = {"points": points}
    
    success, upsert_res = raw_socket_request(
        qdrant_url, 
        qdrant_api, 
        payload_dict=upsert_payload, 
        path=f"/collections/{collection_name}/points?wait=true", 
        method="PUT"
    )
    
    print(f"Upsert Complete. Result: {upsert_res}")
    
    # Save retrieval information to a text file
    retrieval_info_path = DATA_DIR / 'retrieval_info.txt'
    print(f"Saving retrieval info summary to {retrieval_info_path}...")
    with open(retrieval_info_path, 'w', encoding='utf-8') as f:
        f.write("=== Qdrant Vector DB Retrieval Info ===\n")
        f.write(f"Collection Name: {collection_name}\n")
        f.write(f"Embedding Model: sentence-transformers/all-MiniLM-L6-v2\n")
        f.write(f"Schema: {schema_name}\n")
        f.write(f"Total Columns Vectorized: {len(points)}\n\n")
        
        f.write("=== Indexed Documents (Semantic Search Targets) ===\n")
        for pt in points:
            f.write(f"\n--- Point ID: {pt['id']} | Table: {pt['payload']['table_name']} | Column: {pt['payload']['column_name']} ---\n")
            f.write(f"Type: {pt['payload']['type']}\n")
            f.write(f"Description: {pt['payload']['description']}\n")
            
    print("Done!")

def main():
    load_dotenv()
    _default_collection = os.environ.get("QDRANT_COLLECTION", "database_schemas_cloud")
    parser = argparse.ArgumentParser(
        description="Push database schema metadata to Qdrant Cloud using Server-Side Inference."
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to the metadata JSON file (default: data/metadata_injestion_files.json)"
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=_default_collection,
        help=f"The Qdrant collection name to push to (default from .env: {_default_collection})"
    )
    args = parser.parse_args()
    populate_cloud_inference(json_file_path=args.path, collection_name=args.collection_name)

if __name__ == "__main__":
    main()
