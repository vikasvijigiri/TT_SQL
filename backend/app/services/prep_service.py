import os
import json
import queue
import threading
from pathlib import Path
from typing import Generator
import requests

from app.core.settings import settings
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

    def run_pipeline(self, force: bool = False, user_slug: str = None) -> Generator[str, None, None]:
        """
        Runs the prep pipeline and yields log messages.
        """
        thread = threading.Thread(target=self._execute_pipeline, args=(force, user_slug))
        thread.start()

        while True:
            msg = self.log_queue.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    def _log(self, message: str, level: str = "INFO"):
        self.log_queue.put({"message": message, "level": level})

    def _execute_pipeline(self, force: bool, user_slug: str = None):
        try:
            from app.repositories.paths import get_metadata_dir
            from app.db.sql_repo import DBRepository
            from app.repositories.project_repo import ProjectRepository
            import re
            
            # Resolve current project and database context
            active = DBRepository._get_active_connection(user_slug=user_slug)
            
            # FIX: Validate that an active project is selected
            if not active or not active.get("db_type"):
                self._log("ERROR: No active project selected. Please select a database project first.", "ERROR")
                self.log_queue.put(None)  # Signal end of stream
                return
            
            schema_name = active.get("schema") or "public"
            
            # Use standardized collection name resolution
            collection_name = DBRepository.get_collection_name(active, schema_name)
            
            # CRITICAL FIX: Derive project_slug from active project to ensure consistent metadata paths
            from app.repositories.paths import get_safe_slug, get_active_project_id
            project_id = get_active_project_id(user_slug=user_slug)
            project_slug = "default"
            
            if project_id:
                project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
                if project: project_slug = project.get("_slug") or get_safe_slug(project.get("name"))
            
            # Resolve metadata directory using correct project context
            # Path: results/{user}/{project}/{model}/metadata_extracts/{collection}.json
            metadata_registry = get_metadata_dir(user_slug, project_slug)
            metadata_path = metadata_registry / f"{collection_name}.json"

            self._log("Starting", "START")
            print(f"DEBUG [PrepService]: Using collection='{collection_name}', schema='{schema_name}', path={metadata_path}")

            # --- Step 1: Extraction & Enrichment ---
            metadata = None
            if not force and metadata_path.exists() and metadata_path.stat().st_size > 0:
                self._log("Ready")
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                self._log("Extracting")
                metadata = self.extraction_service.extract_metadata(schema_name, user_slug=user_slug)
                
                self._log("Enriching")
                metadata = self.enrichment_service.enrich_metadata(metadata)
                
                # Save metadata to user-scoped registry
                self._log("Saving metadata")
                metadata_registry.mkdir(parents=True, exist_ok=True)
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=4)
                self._log(f"Metadata saved successfully")
                print(f"DEBUG [PrepService]: Metadata saved to {metadata_path}")

            # --- Step 2: Ingestion ---
            collection_exists = False
            q_url = (active.get("qdrant_url") or settings.QDRANT_URL).rstrip("/")
            q_api = active.get("qdrant_api_key") or settings.QDRANT_API_KEY
            
            if not force:
                try:
                    resp = requests.get(f"{q_url}/collections/{collection_name}", headers={"api-key": q_api}, timeout=5)
                    if resp.status_code == 200:
                        collection_exists = True
                except Exception as e:
                    self._log(f"Warning checking Qdrant: {e}")

            if collection_exists and not force:
                self._log("Ready")
            else:
                self._log("Ingesting")
                try:
                    self.ingestion_service.ingest_to_vector_store(metadata, collection_name, qdrant_url=q_url, qdrant_api_key=q_api)
                except Exception as e:
                    self._log(f"Ingestion Failed: {e}", "FAILURE")
                    return

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
