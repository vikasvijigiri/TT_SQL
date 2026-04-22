import argparse
import json
import os
import socket
import ssl
from urllib.parse import urlparse

from sentence_transformers import SentenceTransformer

from ..core.logger import Logger


def get_qdrant_creds():
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API") or os.getenv("QDRANT_API_KEY")
    return url, api_key


def raw_socket_request(url_str, api_key, payload_dict=None, path="", method="GET"):
    parsed = urlparse(url_str)
    host = parsed.hostname
    port = parsed.port or 443

    payload_bytes = b""
    if payload_dict is not None:
        payload_bytes = json.dumps(payload_dict).encode("utf-8")

    headers = [
        f"{method} {path} HTTP/1.1",
        f"Host: {host}:{port}",
        f"api-key: {api_key}",
        "Connection: close",
    ]
    if payload_bytes:
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(payload_bytes)}")

    request = ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + payload_bytes

    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=20) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                ssock.sendall(request)
                response = b""
                while True:
                    chunk = ssock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
    except Exception as e:
        return False, str(e)

    resp_str = response.decode("utf-8", errors="ignore")
    body_start = resp_str.find("\r\n\r\n")
    if body_start != -1:
        body = resp_str[body_start + 4 :]
        try:
            return True, json.loads(body)
        except:
            return True, body
    return False, resp_str


def format_table_document(table_name, table_info):
    doc_lines = [
        f"Table Name: {table_name}",
        f"Description: Schema information for table {table_name}. Contains tracking, metrics, and data about {table_name.replace('-', ' ')}.",
        "Columns:",
    ]
    for col in table_info.get("columns", []):
        col_name = col.get("name")
        data_type = col.get("type")
        doc_lines.append(f" - {col_name} ({data_type})")
    return " ".join(doc_lines)


def ingest_metadata(json_file_path, collection_name=None):
    if not os.path.exists(json_file_path):
        Logger.log(f"Error: {json_file_path} not found.", level="ERROR")
        return

    with open(json_file_path, encoding="utf-8") as f:
        metadata = json.load(f)

    schema_name = metadata.get("schema", "public")
    tables = metadata.get("tables", {})

    qdrant_url, qdrant_api = get_qdrant_creds()
    collection_name = collection_name or os.getenv("QDRANT_COLLECTION")

    if not qdrant_url or not qdrant_api or not collection_name:
        Logger.log("Missing Qdrant configuration in .env", level="ERROR")
        return

    # Initialize local model
    Logger.log("Initializing local SentenceTransformer (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    Logger.log(f"Recreating collection: {collection_name}")
    raw_socket_request(
        qdrant_url, qdrant_api, path=f"/collections/{collection_name}", method="DELETE"
    )

    create_payload = {"vectors": {"size": 384, "distance": "Cosine"}}

    success, res = raw_socket_request(
        qdrant_url,
        qdrant_api,
        payload_dict=create_payload,
        path=f"/collections/{collection_name}",
        method="PUT",
    )

    points = []
    for i, (table_name, table_info) in enumerate(tables.items()):
        doc_text = format_table_document(table_name, table_info)
        # Generate vector locally
        vector = model.encode(doc_text).tolist()

        points.append(
            {
                "id": i + 1,
                "vector": vector,
                "payload": {
                    "schema": schema_name,
                    "table_name": table_name,
                    "column_count": len(table_info.get("columns", [])),
                    "columns": table_info.get("columns", []),
                    "document_text": doc_text,
                },
            }
        )

    upsert_payload = {"points": points}
    success, upsert_res = raw_socket_request(
        qdrant_url,
        qdrant_api,
        payload_dict=upsert_payload,
        path=f"/collections/{collection_name}/points?wait=true",
        method="PUT",
    )

    Logger.log(
        f"Ingestion complete for {collection_name} using Local HF Model. Result: {upsert_res}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, required=True)
    parser.add_argument("--collection", type=str, default=None)
    args = parser.parse_args()

    # Load env for standalone run
    from dotenv import load_dotenv

    load_dotenv()

    ingest_metadata(args.path, args.collection)
