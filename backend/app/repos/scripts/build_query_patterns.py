"""
Component 4: Query Pattern Chunks
Reads data/query_patterns.json and upserts each pattern as a 
chunk_type="query_pattern" vector into Qdrant for Stage 1 retrieval.
"""
import json
import os
import argparse
from app.services.rag_service import query_qdrant
from app.services.logger import Logger
from app.models.config import settings

def raw_socket_request(url_str, api_key, payload_dict=None, path="", method="GET"):
    import requests
    full_url = url_str.rstrip('/') + path
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    try:
        if method == "PUT":
            response = requests.put(full_url, headers=headers, json=payload_dict, timeout=30)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, json=payload_dict, timeout=30)
        return True, response.json()
    except Exception as e:
        return False, str(e)

def build_query_patterns(collection_name=settings.COLLECTION_NAME, patterns_path=None):
    if patterns_path is None:
        patterns_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'query_patterns.json')

    if not os.path.exists(patterns_path):
        print(f"Error: {patterns_path} not found.")
        return

    with open(patterns_path, 'r', encoding='utf-8') as f:
        patterns = json.load(f)

    qdrant_url = settings.QDRANT_URL
    qdrant_api = settings.QDRANT_API_KEY

    # Fetch current number of points to generate safe IDs
    count_res = requests.get(
        f"{qdrant_url}/collections/{collection_name}/points/count",
        headers={"api-key": qdrant_api},
        json={"exact": True},
        timeout=30
    ).json()
    # Start IDs at a safe offset (100000+) to avoid clashing with metadata IDs
    id_offset = 100000

    points = []
    for i, pattern in enumerate(patterns):
        doc_text = pattern["query"]
        points.append({
            "id": id_offset + i,
            "vector": {
                "text_embedding": {
                    "model": settings.EMBEDDING_MODEL,
                    "text": doc_text
                }
            },
            "payload": {
                "chunk_type": "query_pattern",
                "pattern_id": pattern["pattern_id"],
                "query": doc_text,
                "linked_tables": pattern.get("linked_tables", [])
            }
        })

    upsert_payload = {"points": points}
    success, res = raw_socket_request(
        qdrant_url,
        qdrant_api,
        payload_dict=upsert_payload,
        path=f"/collections/{collection_name}/points?wait=true",
        method="PUT"
    )
    print(f"Upserted {len(points)} query pattern chunks. Result: {res}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upsert query pattern chunks into Qdrant.")
    parser.add_argument("--collection-name", type=str, default=settings.COLLECTION_NAME, help=f"Qdrant collection name (default: {settings.COLLECTION_NAME})")
    parser.add_argument("--patterns-path", type=str, default=None)
    args = parser.parse_args()
    build_query_patterns(collection_name=args.collection_name, patterns_path=args.patterns_path)
