import os
import sys
import queue
import threading
import json
import time
import asyncio
from fastapi import Request
from typing import Optional, Dict, Any, List
from app.schemas.api_schemas import QueryRequest, QueryResponse
from app.services.pipeline_service import run_analysis_pipeline
from app.schemas.agent_state import AgentState
from app.core.logger import Logger

class QueryService:
    """
    Service layer for Text-to-SQL operations.
    Applies business logic and orchestrates the agent pipeline.
    """
    def __init__(self, user_slug: str = None, project_slug: str = None):
        from app.core.settings import settings
        self.model_name = settings.LLM_MODEL or "gpt-default"
        self.logger = Logger
    
    def stream_query(self, request: QueryRequest, raw_request: Request = None):
        """
        Stream the Text-to-SQL pipeline progress using SSE.
        """
        if not request.db_name:
            from app.core.settings import settings
            request.db_name = settings.COLLECTION_NAME

        log_queue = queue.Queue()

        def log_listener(message, msg_type, level):
            log_queue.put({
                "type": msg_type,
                "message": message,
                "level": level
            })

        print(f"DEBUG: Starting stream for query: {request.query[:30]}")
        self.logger.register_listener(log_listener)

        from app.repositories.paths import get_next_instance_id, initialize_directories, get_user_slug
        user_slug = get_user_slug(user_email=request.user_email)
        
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(self.model_name, user_slug=user_slug)

        # Lazy initialize user/session directory
        initialize_directories(user_slug=user_slug)

        # Immediate feedback events
        log_queue.put({"type": "id", "instance_id": request.instance_id})
        log_queue.put({"type": "section", "message": "Establishing Connection", "level": "INFO"})

        # Pass listeners to worker thread
        listeners = list(self.logger._get_listeners())
        
        # Initialize state early to allow cross-thread signaling
        from app.schemas.agent_state import AgentState
        state = AgentState(
            user_query=request.query,
            db_path="", # Will be resolved in pipeline
            instance_id=request.instance_id,
            use_rag=request.use_rag,
            model_name=self.model_name
        )

        def run_pipeline():
            for l in listeners:
                self.logger.register_listener(l)
            try:
                final_state = run_analysis_pipeline(
                    question=request.query,
                    db_name=request.db_name,
                    dataset_name=request.dataset_name,
                    instance_id=request.instance_id,
                    model_name=self.model_name,
                    use_rag=request.use_rag,
                    user_email=request.user_email,
                    session_id=request.session_id,
                    verbose=True,
                    on_token=lambda t: log_queue.put({"type": "token", "token": t}),
                    on_result=lambda s: log_queue.put({**self._format_final_result(s), "type": "result", "status": "Finalizing Analysis..."}),
                    existing_state=state
                )
                
                # Emit the final structured result for UI termination and rendering
                final_payload = self._format_final_result(final_state)
                final_payload["type"] = "result"
                log_queue.put(final_payload)
                
                print(f"DEBUG: Pipeline thread finished for {request.instance_id}.")
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

        async def event_generator():
            try:
                while True:
                    # Check for client disconnection
                    if raw_request and await raw_request.is_disconnected():
                        print(f"DEBUG: Client disconnected for {request.instance_id}. Stopping pipeline.")
                        state.stop_requested = True
                        break

                    try:
                        item = log_queue.get_nowait()
                        if item is None:
                            break
                        yield f"data: {json.dumps(item)}\n\n"
                    except queue.Empty:
                        await asyncio.sleep(0.2)
                        yield f"data: {json.dumps({'type': 'keep-alive'})}\n\n"
            except Exception as e:
                print(f"ERROR in generator: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'Stream interrupted: {str(e)}'})}\n\n"
            finally:
                state.stop_requested = True # Safety halt

        return event_generator()

    def _format_final_result(self, final_state: AgentState) -> Dict[str, Any]:
        """Helper to extract and format results from the agent state for the frontend."""
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
                
        return {
            "instance_id": final_state.instance_id,
            "sql": sql,
            "results": results,
            "columns": columns,
            "total_count": total_count,
            "logs": final_state.logs,
            "critic_feedback": final_state.critic_feedback,
            "business_summary": final_state.business_summary,
            "chart_config": final_state.chart_config,
            "token_usage": final_state.token_usage,
            "total_time": final_state.total_duration
        }

    def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Standard non-streaming Text-to-SQL logic.
        """
        if not request.db_name:
            from app.core.settings import settings
            request.db_name = settings.COLLECTION_NAME

        from app.repositories.paths import get_next_instance_id, initialize_directories, get_user_slug
        user_slug = get_user_slug(user_email=request.user_email)
        
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(self.model_name, user_slug=user_slug)
            
        initialize_directories(user_slug=user_slug)
            
        final_state = run_analysis_pipeline(
            question=request.query,
            db_name=request.db_name,
            dataset_name=request.dataset_name,
            instance_id=request.instance_id,
            model_name=self.model_name,
            use_rag=request.use_rag,
            user_email=request.user_email,
            session_id=request.session_id,
            verbose=True
        )
        
        result_content = self._format_final_result(final_state)
        return QueryResponse(**result_content)

    # resolve_instance_context strictly removed (relied on deleted input_queries directory).


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
        print(log[:100] + "...")
    print("\nBUSINESS SUMMARY:")
    print(response.business_summary)
