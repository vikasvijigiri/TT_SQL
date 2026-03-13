import os
import sys
from typing import Optional
from app.services.schemas.schemas import QueryRequest, QueryResponse
from app.services.engines.pipeline_service import run_analysis_pipeline
from app.services.schemas.agent_state import AgentState

class SQLService:
    """
    Service layer for Text-to-SQL operations.
    Applies business logic and orchestrates the agent pipeline.
    """
    
    def stream_query(self, request: QueryRequest):
        """
        Stream the Text-to-SQL pipeline progress using SSE.
        """
        import queue
        import threading
        import json
        from app.services.utils.logger import Logger

        log_queue = queue.Queue()

        def log_listener(message, msg_type, level):
            log_queue.put({
                "type": msg_type,
                "message": message,
                "level": level
            })

        Logger.register_listener(log_listener)

        # Get model name from env
        model_name = os.getenv("LLM_MODEL", "gpt-default")

        # Assign standardized qXXX ID if missing
        from app.repositories.registry.paths import get_next_instance_id
        if not request.instance_id or request.instance_id == "unknown":
            request.instance_id = get_next_instance_id(model_name)
            pass

        # Emit the ID immediately so the frontend can track it
        log_queue.put({
            "type": "id",
            "instance_id": request.instance_id
        })

        def token_callback(token: str):
            # print(f"DEBUG: Putting token in queue: {token[:10]}...") # Optional: too spammy
            log_queue.put({
                "type": "token",
                "token": token
            })

        # Capture listeners from request thread to pass to worker thread
        # This fixes the thread-local storage issue
        listeners = list(Logger._get_listeners())

        def run_pipeline():
            # Re-register listeners in the NEW worker thread
            for l in listeners:
                Logger.register_listener(l)
                
            try:
                pass
                final_state = run_analysis_pipeline(
                    question=request.query,
                    db_name=request.db_name,
                    dataset_name=request.dataset_name,
                    instance_id=request.instance_id,
                    model_name=model_name,
                    use_rag=request.use_rag,
                    verbose=True,
                    on_token=token_callback
                )
                
                # Send the final result as a special event
                sql = final_state.chosen_query
                results = []
                columns = []
                total_count = 0
                
                if final_state.execution_result:
                    columns = final_state.execution_result.columns
                    total_count = final_state.execution_result.row_count
                    from decimal import Decimal
                    
                    # ðŸ”´ OPTIMIZATION: Cap frontend payload at 100 rows to prevent network/UI lag
                    # The full CSV write (already backgrounded) still contains all records.
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
                
                log_queue.put({
                    "type": "result",
                    "sql": sql,
                    "results": results,
                    "columns": columns,
                    "total_count": total_count,
                    "critic_feedback": final_state.critic_feedback,
                    "business_summary": final_state.business_summary,
                    "chart_config": final_state.chart_config,
                    "total_time": final_state.total_duration
                })

                print("DEBUG: Final result put in queue.")
            except Exception as e:
                import traceback
                pass
                print(traceback.format_exc())
                log_queue.put({"type": "error", "message": str(e)})
            finally:
                log_queue.put(None) # Sentinel to end the stream
                Logger.clear_listeners()

        thread = threading.Thread(target=run_pipeline)
        thread.start()

        while True:
            item = log_queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Standard non-streaming Text-to-SQL logic.
        """
        # Get model name from env
        model_name = os.getenv("LLM_MODEL", "gpt-default")
            
        # Assign standardized qXXX ID if missing
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
            
            # Cap frontend payload for performance
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
            total_count=total_count,  # Added to QueryResponse if it supports it
            logs=final_state.logs,
            critic_feedback=final_state.critic_feedback,
            business_summary=final_state.business_summary
        )

