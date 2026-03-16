import os
import sys
import queue
import threading
import json
import time
from typing import Optional, Dict, Any, List
from app.services.schemas.schemas import QueryRequest, QueryResponse
from app.services.engines.pipeline_service import run_analysis_pipeline
from app.services.schemas.agent_state import AgentState
from app.services.utils.logger import Logger

class QueryService:
    """
    Service layer for Text-to-SQL operations.
    Applies business logic and orchestrates the agent pipeline.
    """
    def __init__(self):
        self.logger = Logger
        self.model_name = os.getenv("LLM_MODEL", "gpt-default")
    
    def stream_query(self, request: QueryRequest):
        """
        Stream the Text-to-SQL pipeline progress using SSE.
        """
        log_queue = queue.Queue()

        def log_listener(message, msg_type, level):
            log_queue.put({
                "type": msg_type,
                "message": message,
                "level": level
            })

        print(f"DEBUG: Starting stream for query: {request.query[:30]}")
        self.logger.register_listener(log_listener)

        from app.repositories.registry.paths import get_next_instance_id
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(self.model_name)

        # Immediate feedback events
        log_queue.put({"type": "id", "instance_id": request.instance_id})
        log_queue.put({"type": "section", "message": "Establishing Connection", "level": "INFO"})

        # Pass listeners to worker thread
        listeners = list(self.logger._get_listeners())

        def run_pipeline():
            for l in listeners:
                self.logger.register_listener(l)
            try:
                run_analysis_pipeline(
                    question=request.query,
                    db_name=request.db_name,
                    dataset_name=request.dataset_name,
                    instance_id=request.instance_id,
                    model_name=self.model_name,
                    use_rag=request.use_rag,
                    verbose=True,
                    on_token=lambda t: log_queue.put({"type": "token", "token": t})
                )
                print("DEBUG: Pipeline thread finished.")
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"ERROR in pipeline: {e}\n{error_detail}")
                log_queue.put({"type": "error", "message": f"Backend Error: {str(e)}"})
            finally:
                log_queue.put(None)
                self.logger.clear_listeners()

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        def event_generator():
            try:
                while True:
                    try:
                        item = log_queue.get(timeout=10)
                        if item is None:
                            break
                        yield f"data: {json.dumps(item)}\n\n"
                    except queue.Empty:
                        yield f"data: {json.dumps({'type': 'keep-alive'})}\n\n"
            except Exception as e:
                print(f"ERROR in generator: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Stream interrupted'})}\n\n"

        return event_generator()

    def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Standard non-streaming Text-to-SQL logic.
        """
        from app.repositories.registry.paths import get_next_instance_id
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(self.model_name)
            
        final_state = run_analysis_pipeline(
            question=request.query,
            db_name=request.db_name,
            dataset_name=request.dataset_name,
            instance_id=request.instance_id,
            model_name=self.model_name,
            use_rag=request.use_rag,
            verbose=True
        )
        
        sql = final_state.chosen_query
        results = []
        columns = []
        total_count = 0
        
        if final_state.execution_result:
            columns = final_state.execution_result.columns
            total_count = final_state.execution_result.row_count
            from decimal import Decimal
            
            frontend_rows = final_state.execution_result.rows[:100]
            for row in frontend_rows:
                json_row = {}
                for col, val in zip(columns, row):
                    if hasattr(val, 'isoformat'):
                        json_row[col] = val.isoformat()
                    elif isinstance(val, Decimal):
                        json_row[col] = float(val)
                    else:
                        json_row[col] = val
                results.append(json_row)
                
        return QueryResponse(
            instance_id=final_state.instance_id,
            sql=sql,
            results=results,
            columns=columns,
            total_count=total_count,
            logs=final_state.logs,
            critic_feedback=final_state.critic_feedback,
            business_summary=final_state.business_summary
        )

    def resolve_instance_context(self, instance_id: str, input_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves question and DB name from an instance ID by searching JSONL datasets.
        """
        from app.repositories.registry.paths import INPUT_QUERIES_DIR
        candidates = []
        if input_file:
            candidates.append(os.path.abspath(input_file))
        else:
            for cand in ["spider2-lite.jsonl", "sample.jsonl", "user_questions.jsonl"]:
                candidates.append(str(INPUT_QUERIES_DIR / cand))

        for path in candidates:
            if not os.path.exists(path):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        if str(data.get("instance_id")).strip() == str(instance_id).strip():
                            return {
                                "question": data.get("question"),
                                "db": data.get("db"),
                                "instance_id": instance_id
                            }
                    except: continue
        return {}

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Standalone Text-to-SQL Query Tool")
    parser.add_argument("--query", type=str, help="Natural language question")
    parser.add_argument("--db", type=str, default="chinook", help="Database name")
    parser.add_argument("--id", type=str, help="Instance ID to resolve context for")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG")
    args = parser.parse_args()
    
    service = QueryService()
    
    q_text = args.query
    db_name = args.db
    instance_id = "standalone-test"
    
    if args.id:
        ctx = service.resolve_instance_context(args.id)
        if ctx:
            q_text = ctx["question"]
            db_name = ctx["db"]
            instance_id = ctx["instance_id"]
        else:
            print(f"Error: Could not resolve instance ID {args.id}")
            exit(1)
            
    if not q_text:
        print("Error: --query or --id required.")
        exit(1)
        
    request = QueryRequest(query=q_text, db_name=db_name, instance_id=instance_id, use_rag=not args.no_rag)
    response = service.process_query(request)
    
    print("\n--- QUERY RESULTS ---")
    print(f"SQL: {response.sql}")
    print(f"Rows: {response.total_count}")
    print("\nPROMPT LOGS SUMMARY:")
    for log in response.logs:
        print(f"[{log.agent_name}] {log.message[:100]}...")
    print("\nBUSINESS SUMMARY:")
    print(response.business_summary)
