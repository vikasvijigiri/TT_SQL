import queue
import threading
import json
import asyncio
from typing import Dict, Any, Generator
from fastapi import Request

from app.schemas.api_schemas import QueryRequest
from app.schemas.agent_state import AgentState
from app.core.config.settings import settings
from app.core.logging.logger import Logger
from app.infrastructure.storage.path_manager import StorageManager
from .pipeline import AnalysisPipeline
from .formatter import AnalysisFormatter

class AnalysisOrchestrator:
    """
    Top-level orchestrator for Text-to-SQL analysis.
    Manages streaming responses, async execution, and session state.
    """
    
    def __init__(self, user_slug: str, project_slug: str, model_name: str = None):
        self.user_slug = user_slug
        self.project_slug = project_slug
        self.model_name = model_name or settings.LLM_MODEL
        self.pipeline = AnalysisPipeline(self.model_name, user_slug, project_slug)

    def stream_analysis(self, query_request: QueryRequest, raw_request: Request = None):
        """Streams the analysis progress via SSE."""
        log_queue = queue.Queue()
        
        # Setup Logger listener for this thread
        def log_listener(msg, mtype, level):
            log_queue.put({"type": mtype, "message": msg, "level": level})
        Logger.register_listener(log_listener)

        # Initialize State
        instance_id = query_request.instance_id or StorageManager.get_instance_id()
        if instance_id == "unknown": instance_id = StorageManager.get_instance_id()
        
        state = AgentState(
            user_query=query_request.query,
            instance_id=instance_id,
            use_rag=query_request.use_rag,
            model_name=self.model_name,
            project_slug=self.project_slug
        )

        def worker():
            try:
                # Immediate ID notification
                log_queue.put({"type": "id", "instance_id": instance_id})
                
                # Execute Pipeline
                final_state = self.pipeline.run(
                    state, 
                    on_token=lambda t: log_queue.put({"type": "token", "token": t})
                )
                
                # Emit formatted result
                result = AnalysisFormatter.format_final_result(final_state)
                log_queue.put({**result, "type": "result", "status": "Finished"})
                
            except Exception as e:
                log_queue.put({"type": "error", "message": str(e)})
            finally:
                log_queue.put(None) # Signal termination
                Logger.clear_listeners()

        threading.Thread(target=worker, daemon=True).start()

        async def generator():
            while True:
                if raw_request and await raw_request.is_disconnected():
                    state.stop_requested = True
                    break
                
                try:
                    item = log_queue.get_nowait()
                    if item is None: break
                    yield f"data: {json.dumps(item)}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    yield f"data: {json.dumps({'type': 'keep-alive'})}\n\n"

        return generator()
