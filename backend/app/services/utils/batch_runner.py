import os
import json
import threading
from pathlib import Path
from typing import List, Dict, Any, Generator

from app.repositories.config import settings
from app.repositories.registry.project_repo import ProjectRepository
from app.repositories.registry.user_repo import UserRepository
from app.repositories.registry.paths import get_user_slug, initialize_directories
from app.services.utils.prep_service import PrepService
from app.services.engines.query_service import QueryService
from app.services.schemas.schemas import QueryRequest

class BatchRunner:
    """
    Automated Batch Runner for benchmark datasets (e.g., Spider2-lite).
    Handles auto-project creation, auto-knowledge-injection, and query execution.
    """
    def __init__(self):
        self.query_service = QueryService()
        self.prep_service = PrepService()

    def run_batch(self, file_path: str, user_email: str = None, user_name: str = None) -> Generator[str, None, None]:
        """
        Orchestrates the batch run sequentially. Yields SSE-formatted logs.
        """
        user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        
        def _execute():
            try:
                yield_log("Starting Batch Processing Mode", "START")
                
                if not os.path.exists(file_path):
                    yield_log(f"Error: Dataset {file_path} not found.", "ERROR")
                    return

                # 1. Parse dataset to identify unique DBs
                records = []
                unique_dbs = set()
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        data = json.loads(line)
                        records.append(data)
                        if data.get("db"):
                            unique_dbs.add(data["db"])
                
                yield_log(f"Dataset loaded: {len(records)} questions across {len(unique_dbs)} databases.")

                # 2. Sequential Discovery & Preparation
                # Store project mappings {db_name: project_id}
                db_to_project = {}
                
                for db_name in sorted(list(unique_dbs)):
                    yield_log(f"--- Processing Workspace: {db_name} ---", "SECTION")
                    
                    # Check if project exists for this user
                    existing_projects = ProjectRepository.get_all_projects(user_slug=user_slug)
                    project_id = None
                    for p in existing_projects:
                        # Match by name or dataset name
                        if p.get("name") == db_name or (p.get("connection") and p["connection"].get("db_name") == db_name):
                            project_id = p["id"]
                            break
                    
                    if not project_id:
                        yield_log(f"Auto-creating project for '{db_name}' using .env defaults.")
                        conn_data = {
                            "db_type": settings.DB_TYPE or "bigquery",
                            "db_name": db_name,
                            "database": os.getenv("BQ_PROJECT_ID") or os.getenv("RDS_DATABASE") or "default",
                            "bq_credentials_path": settings.BQ_CREDENTIALS_PATH,
                            "qdrant_url": settings.QDRANT_URL,
                            "qdrant_api_key": settings.QDRANT_API_KEY
                        }
                        
                        p_data = {
                            "name": db_name,
                            "connection": conn_data
                        }
                        saved_p = ProjectRepository.save_project(p_data, user_slug=user_slug)
                        project_id = saved_p["id"]
                    
                    db_to_project[db_name] = project_id
                    
                    # Activate project for this thread
                    user_repo = UserRepository()
                    user_repo.update_state(user_slug, {"activeProjectId": project_id})
                    
                    # Trigger knowledge injection if needed
                    yield_log(f"Checking Knowledge Base for '{db_name}'...")
                    # We use the generator internally
                    for msg in self.prep_service.run_pipeline(force=False, user_slug=user_slug):
                        # msg is a SSE string, need to parse to get text
                        try:
                            # data: {"message": "...", "level": "..."}
                            content = json.loads(msg.replace("data: ", "").strip())
                            if content.get("level") in ["INFO", "ERROR"]:
                                yield_log(f"  > {content['message']}", content.get("level"))
                            if content.get("message") == "Complete":
                                break
                        except: pass

                # 3. Question Execution
                yield_log("--- Beginning Question Execution ---", "SECTION")
                results_file = Path(file_path).parent / f"batch_results_{user_slug}.jsonl"
                
                count = 0
                for record in records:
                    db_name = record.get("db")
                    question = record.get("question")
                    instance_id = record.get("instance_id") or f"batch_{count:03d}"
                    
                    yield_log(f"[{count+1}/{len(records)}] Running: {instance_id}")
                    
                    # Ensure correct project is active
                    pid = db_to_project.get(db_name)
                    if pid:
                        user_repo.update_state(user_slug, {"activeProjectId": pid})
                    
                    request = QueryRequest(
                        query=question,
                        db_name=db_name,
                        instance_id=instance_id,
                        use_rag=True,
                        user_email=user_email
                    )
                    
                    try:
                        # process_query is synchronous
                        response = self.query_service.process_query(request)
                        
                        # Save result
                        result_entry = {
                            "instance_id": instance_id,
                            "db": db_name,
                            "sql": response.sql,
                            "status": "success" if not response.error_message else "error"
                        }
                        with open(results_file, 'a', encoding='utf-8') as rf:
                            rf.write(json.dumps(result_entry) + "\n")
                        
                        count += 1
                    except Exception as e:
                        yield_log(f"Error processing {instance_id}: {e}", "ERROR")

                yield_log(f"Batch Complete. Results saved to {results_file}", "SUCCESS")

            except Exception as e:
                yield_log(f"Batch Execution Failed: {str(e)}", "ERROR")
            finally:
                self.log_queue.put(None)

        self.log_queue = queue.Queue()
        def yield_log(message, level="INFO"):
            self.log_queue.put({"message": message, "level": level})

        import queue
        threading.Thread(target=_execute, daemon=True).start()

        while True:
            msg = self.log_queue.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"
