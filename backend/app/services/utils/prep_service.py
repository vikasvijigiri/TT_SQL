import os
import json
import queue
import threading
from pathlib import Path
from typing import Generator
import requests

from app.repositories.config import settings
from app.repositories.registry.paths import METADATA_DIR
from app.services.metadata.extraction_service import ExtractionService
from app.services.metadata.enrichment_service import EnrichmentService
from app.services.metadata.ingestion_service import IngestService

class PrepService:
    """
    Service to orchestrate knowledge preparation: Extract -> Enrich -> Ingest.
    Uses direct service calls instead of internal subprocesses.
    """

    def __init__(self, extraction_service=None, enrichment_service=None, ingestion_service=None):
        self.log_queue = queue.Queue()
        self.extraction_service = extraction_service or ExtractionService()
        self.enrichment_service = enrichment_service or EnrichmentService()
        self.ingestion_service = ingestion_service or IngestService()

    def run_pipeline(self, force: bool = False) -> Generator[str, None, None]:
        """
        Runs the prep pipeline and yields log messages.
        """
        thread = threading.Thread(target=self._execute_pipeline, args=(force,))
        thread.start()

        while True:
            msg = self.log_queue.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    def _log(self, message: str, level: str = "INFO"):
        self.log_queue.put({"message": message, "level": level})

    def _execute_pipeline(self, force: bool):
        try:
            schema_name = settings.SCHEMA or "public"
            collection_name = settings.COLLECTION_NAME or schema_name
            metadata_path = METADATA_DIR / f"{schema_name}.json"

            self._log("Starting", "START")

            # --- Step 1: Extraction & Enrichment ---
            metadata = None
            if not force and metadata_path.exists() and metadata_path.stat().st_size > 0:
                self._log("Ready")
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                self._log("Extracting")
                metadata = self.extraction_service.extract_metadata(schema_name)
                
                self._log("Enriching")
                metadata = self.enrichment_service.enrich_metadata(metadata)
                
                # Save metadata
                METADATA_DIR.mkdir(parents=True, exist_ok=True)
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=4)
                self._log(f"Metadata saved to {metadata_path}")

            # --- Step 2: Ingestion ---
            collection_exists = False
            if not force:
                try:
                    q_url = settings.QDRANT_URL.rstrip("/")
                    q_api = settings.QDRANT_API_KEY
                    resp = requests.get(f"{q_url}/collections/{collection_name}", headers={"api-key": q_api}, timeout=5)
                    if resp.status_code == 200:
                        collection_exists = True
                except Exception as e:
                    self._log(f"Warning checking Qdrant: {e}")

            if collection_exists and not force:
                self._log("Ready")
            else:
                self._log("Ingesting")
                self.ingestion_service.ingest_to_vector_store(metadata, collection_name)

            self._log("Complete", "SUCCESS")
        except Exception as e:
            self._log(f"Error: {str(e)}", "ERROR")
        finally:
            self.log_queue.put(None)

if __name__ == "__main__":
    import argparse
    import time
    
    parser = argparse.ArgumentParser(description="Full Knowledge Pipeline Preparation Tool")
    parser.add_argument("--force", action="store_true", help="Force re-extraction and re-ingestion")
    args = parser.parse_args()
    
    service = PrepService()
    print(f"Starting Knowledge Prep Pipeline (Force: {args.force})...")
    
    # We consume the generator directly since we are in CLI
    for msg in service.run_pipeline(force=args.force):
        data = json.loads(msg.replace("data: ", "").strip())
        lvl = data.get("level", "INFO")
        txt = data.get("message", "")
        print(f"[{lvl}] {txt}")
        if txt == "Complete":
            break
