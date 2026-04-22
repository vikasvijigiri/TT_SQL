import requests
from typing import Dict, Any
from sentence_transformers import SentenceTransformer
from app.core.settings import settings
from app.core.logger import Logger

class IngestService:
    def __init__(self, embedding_model=None):
        self._model_name = embedding_model or settings.EMBEDDING_MODEL
        self._model = None
        self.logger = Logger

    @property
    def model(self):
        if self._model is None:
            self.logger.log(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def delete_collection(self, collection_name: str, qdrant_url: str = None, qdrant_api_key: str = None):
        """Deletes a collection from Qdrant."""
        q_url = qdrant_url or settings.QDRANT_URL
        q_api = qdrant_api_key or settings.QDRANT_API_KEY
        headers = {"api-key": q_api, "Content-Type": "application/json"}
        
        try:
            resp = requests.delete(f"{q_url.rstrip('/')}/collections/{collection_name}", headers=headers, timeout=10)
            if resp.status_code not in [200, 404]:
                resp.raise_for_status()
        except Exception as e:
            self.logger.log(f"Warning: Failed to delete collection {collection_name}: {e}", level="WARNING")
        return resp.status_code in [200, 404]

    def ingest_to_vector_store(self, metadata: Dict[str, Any], collection_name: str, qdrant_url: str = None, qdrant_api_key: str = None):
        """Populates Qdrant with table and column embeddings."""
        q_url = qdrant_url or settings.QDRANT_URL
        q_api = qdrant_api_key or settings.QDRANT_API_KEY
        headers = {"api-key": q_api, "Content-Type": "application/json"}

        # Reset collection
        self.delete_collection(collection_name, q_url, q_api)
        
        create_payload = {
            "vectors": {
                "text_embedding": {
                    "size": settings.EMBEDDING_SIZE,
                    "distance": "Cosine"
                }
            }
        }
        try:
            resp = requests.put(f"{q_url.rstrip('/')}/collections/{collection_name}", headers=headers, json=create_payload)
            resp.raise_for_status()
        except Exception as e:
            self.logger.log(f"Critical: Failed to create collection {collection_name}: {e}", level="ERROR")
            raise ConnectionError(f"Vector Store creation failed: {e}")
        
        # Indexes for filtering
        for field in ["chunk_type", "table_name"]:
            resp = requests.put(
                f"{q_url.rstrip('/')}/collections/{collection_name}/index",
                headers=headers,
                json={"field_name": field, "field_schema": "keyword"}
            )
            resp.raise_for_status()

        self.logger.log("Encoding and upserting chunks...")
        points = []
        global_id = 1
        
        for table_name, table_info in metadata.get("tables", {}).items():
            columns = table_info.get("columns", [])
            
            # Table-level chunk
            table_text = f"TABLE: {table_name}. COLUMNS: {', '.join(c['column_name'] for c in columns)}."
            points.append({
                "id": global_id,
                "vector": {"text_embedding": self.model.encode(table_text).tolist()},
                "payload": {
                    "chunk_type": "table",
                    "table_name": table_name,
                    "column_names": [c["column_name"] for c in columns],
                    "document_text": table_text
                }
            })
            global_id += 1
            
            # Column-level chunks
            for col in columns:
                col_name = col["column_name"]
                desc = col.get("description", "")
                doc_text = f"TABLE: {table_name}\nCOLUMN: {col_name}\nDESCRIPTION: {desc}"
                points.append({
                    "id": global_id,
                    "vector": {"text_embedding": self.model.encode(doc_text).tolist()},
                    "payload": {
                        "chunk_type": "column",
                        "table_name": table_name,
                        "column_name": col_name,
                        "type": col.get("type"),
                        "description": desc,
                        "sample_values": col.get("sample_values", []),
                        "document_text": doc_text
                    }
                })
                global_id += 1

        # Batch upsert
        batch_size = 50
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            resp = requests.put(
                f"{q_url.rstrip('/')}/collections/{collection_name}/points?wait=true",
                headers=headers,
                json={"points": batch}
            )
            resp.raise_for_status()
        self.logger.log(f"Ingestion complete for {collection_name}")

    def build_query_patterns(self, patterns_path: str, collection_name: str = None):
        """
        Upserts query pattern chunks into Qdrant for Stage 1 retrieval.
        """
        coll = collection_name or settings.COLLECTION_NAME
        if not os.path.exists(patterns_path):
            self.logger.log(f"Error: {patterns_path} not found.", level="ERROR")
            return

        with open(patterns_path, 'r', encoding='utf-8') as f:
            patterns = json.load(f)

        q_url = settings.QDRANT_URL.rstrip('/')
        q_key = settings.QDRANT_API_KEY
        headers = {"api-key": q_key, "Content-Type": "application/json"}

        # Start IDs at a safe offset (100000+) to avoid clashing with metadata IDs
        id_offset = 100000
        points = []
        for i, pattern in enumerate(patterns):
            doc_text = pattern["query"]
            points.append({
                "id": id_offset + i,
                "vector": {"text_embedding": self.model.encode(doc_text).tolist()},
                "payload": {
                    "chunk_type": "query_pattern",
                    "pattern_id": pattern["pattern_id"],
                    "query": doc_text,
                    "linked_tables": pattern.get("linked_tables", [])
                }
            })

        resp = requests.put(f"{q_url}/collections/{coll}/points?wait=true", headers=headers, json={"points": points})
        self.logger.log(f"Upserted {len(points)} query patterns to {coll}. Status: {resp.status_code}")

    def export_retrieval_info(self, collection_name: str = None, user_slug: str = None) -> str:
        """
        Exports a summary of indexed metadata to a text file.
        """
        from app.repositories.paths import get_metadata_dir, get_active_project_slug
        coll = collection_name or settings.COLLECTION_NAME
        project_slug = get_active_project_slug(user_slug=user_slug)
        metadata_registry = get_metadata_dir(user_slug, project_slug)
        metadata_path = metadata_registry / f"{coll}.json"
        output_path = metadata_registry / f"{coll}_retrieval_info.txt"

        if not metadata_path.exists():
            return f"Error: {metadata_path} not found."

        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        tables = metadata.get("tables", {})
        with open(output_path, 'w', encoding='utf-8') as out:
            out.write("=== Qdrant Vector DB Retrieval Info ===\n")
            out.write(f"Collection: {coll}\n")
            out.write(f"Model: {settings.EMBEDDING_MODEL}\n")
            out.write(f"Tables: {len(tables)}\n\n")

            for i, (t_name, t_info) in enumerate(tables.items()):
                cols = t_info.get("columns", [])
                out.write(f"Table: {t_name} | Columns: {len(cols)}\n")
                for c in cols:
                    out.write(f"  - {c['column_name']} ({c['type']})\n")
                out.write("\n")

        self.logger.log(f"Retrieval info exported to {output_path}")
        return str(output_path)

if __name__ == "__main__":
    import argparse
    import json
    import os
    
    parser = argparse.ArgumentParser(description="Standalone Knowledge Ingestion Tool")
    parser.add_argument("--mode", choices=["ingest", "patterns", "info"], required=True)
    parser.add_argument("--input", type=str, help="Path to metadata JSON or patterns JSON")
    parser.add_argument("--collection", type=str, default=settings.COLLECTION_NAME, help="Qdrant collection name")
    args = parser.parse_args()
    
    service = IngestService()
    
    if args.mode == "ingest":
        if not args.input or not os.path.exists(args.input):
             print("Error: Valid --input metadata JSON required for ingest mode.")
             exit(1)
        with open(args.input, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        service.ingest_to_vector_store(metadata, args.collection)
    elif args.mode == "patterns":
        if not args.input or not os.path.exists(args.input):
             print("Error: Valid --input patterns JSON required for patterns mode.")
             exit(1)
        service.build_query_patterns(args.input, args.collection)
    elif args.mode == "info":
        path = service.export_retrieval_info(args.collection)
        print(f"Info exported to: {path}")
