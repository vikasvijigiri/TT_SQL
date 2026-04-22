import requests
from typing import Dict, Any
from sentence_transformers import SentenceTransformer
from app.core.config.settings import settings
from app.core.logging.logger import Logger

class MetadataIngestor:
    """
    Encodes metadata into vector embeddings and populates the Knowledge Base (Qdrant).
    Supports keyword indexing and batch upserts for performance.
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def ingest(self, metadata: Dict[str, Any], collection_name: str):
        """Main entry point for populating the vector store."""
        q_url = settings.QDRANT_URL.rstrip('/')
        q_api = settings.QDRANT_API_KEY
        headers = {"api-key": q_api, "Content-Type": "application/json"}

        # 1. Reset Collection
        requests.delete(f"{q_url}/collections/{collection_name}", headers=headers)
        
        # 2. Create with Vector config
        create_payload = {
            "vectors": {"text_embedding": {"size": settings.EMBEDDING_SIZE, "distance": "Cosine"}}
        }
        requests.put(f"{q_url}/collections/{collection_name}", headers=headers, json=create_payload)

        # 3. Process and Upsert
        points = []
        gid = 1
        for tname, tinfo in metadata.get("tables", {}).items():
            cols = tinfo.get("columns", [])
            # Table level
            text = f"TABLE: {tname}. COLS: {', '.join(c['column_name'] for c in cols)}."
            points.append(self._make_point(gid, text, {"chunk_type": "table", "table_name": tname}))
            gid += 1
            
            # Column level
            for c in cols:
                txt = f"TABLE: {tname}\nCOLUMN: {c['column_name']}\nDESC: {c.get('description','')}"
                points.append(self._make_point(gid, txt, {"chunk_type": "column", "table_name": tname, **c}))
                gid += 1

        # Batch upload
        for i in range(0, len(points), 50):
            requests.put(f"{q_url}/collections/{collection_name}/points?wait=true", headers=headers, json={"points": points[i:i+50]})
        
        Logger.log(f"Ingestion complete: {collection_name} ({len(points)} points)")

    def _make_point(self, id: int, text: str, payload: dict) -> dict:
        return {
            "id": id,
            "vector": {"text_embedding": self.model.encode(text).tolist()},
            "payload": {**payload, "document_text": text}
        }
