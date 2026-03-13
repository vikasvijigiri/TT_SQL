import os
import sys
import queue
import threading
import json
import time
from typing import Optional
from app.services.schemas.schemas import QueryRequest, QueryResponse
from app.services.engines.pipeline_service import run_analysis_pipeline
from app.services.schemas.agent_state import AgentState
from app.services.utils.logger import Logger

class QueryService:
    """
    Service layer for Text-to-SQL operations.
    Applies business logic and orchestrates the agent pipeline.
    """
    
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
        Logger.register_listener(log_listener)

        model_name = os.getenv("LLM_MODEL", "gpt-default")
        from app.repositories.registry.paths import get_next_instance_id
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(model_name)

        # Immediate feedback events
        log_queue.put({"type": "id", "instance_id": request.instance_id})
        log_queue.put({"type": "section", "message": "Establishing Connection", "level": "INFO"})

        # Pass listeners to worker thread
        listeners = list(Logger._get_listeners())

        def run_pipeline():
            for l in listeners:
                Logger.register_listener(l)
            try:
                run_analysis_pipeline(
                    question=request.query,
                    db_name=request.db_name,
                    dataset_name=request.dataset_name,
                    instance_id=request.instance_id,
                    model_name=model_name,
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
                Logger.clear_listeners()

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
        model_name = os.getenv("LLM_MODEL", "gpt-default")
        from app.repositories.registry.paths import get_next_instance_id
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(model_name)
            
        final_state = run_analysis_pipeline(
            question=request.query,
            db_name=request.db_name,
            dataset_name=request.dataset_name,
            instance_id=request.instance_id,
            model_name=model_name,
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
