import os
import sys
import subprocess
import json
import queue
import threading
from pathlib import Path
from typing import Generator
from app.repositories.config import settings
from app.repositories.registry.paths import METADATA_DIR, PROJECT_ROOT
import requests

class PrepService:
    """
    Service to orchestrate knowledge preparation: Extract -> Enrich -> Ingest.
    Includes efficiency logic to skip completed steps.
    """

    def __init__(self):
        self.log_queue = queue.Queue()

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
            skip_extract = not force and metadata_path.exists() and metadata_path.stat().st_size > 0
            if skip_extract:
                self._log("Ready")
            else:
                self._log("Extracting")
                # Using --enrich means it does both extraction and enrichment
                cmd = [sys.executable, "scripts/run_extract_enrich.py", "--enrich"]
                if not self._run_subprocess(cmd):
                    self._log("Error", "ERROR")
                    return
                self._log("Enriching") # Secondary status for visual progress

            # --- Step 2: Ingestion ---
            # Check if collection has points already
            has_points = False
            if not force:
                try:
                    q_url = settings.QDRANT_URL.rstrip("/")
                    q_key = settings.QDRANT_API_KEY
                    resp = requests.get(f"{q_url}/collections/{collection_name}", headers={"api-key": q_key}, timeout=5)
                    if resp.status_code == 200:
                        count = resp.json().get("result", {}).get("points_count", 0)
                        if count > 0:
                            has_points = True
                except Exception as e:
                    self._log(f"Warning checking Qdrant: {e}")

            if has_points and not force:
                self._log("Ready")
            else:
                self._log("Ingesting")
                cmd = [sys.executable, "scripts/populate_vector_store.py", "--metadata-file", str(metadata_path)]
                if not self._run_subprocess(cmd):
                    self._log("Error", "ERROR")
                    return

            self._log("Complete", "SUCCESS")
        except Exception as e:
            self._log("Error", "ERROR")
        finally:
            self.log_queue.put(None)

    def _run_subprocess(self, cmd: list) -> bool:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=env,
                bufsize=1
            )
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    self._log(clean_line)
            process.wait()
            return process.returncode == 0
        except Exception as e:
            self._log(f"Subprocess Error: {e}", "ERROR")
            return False
