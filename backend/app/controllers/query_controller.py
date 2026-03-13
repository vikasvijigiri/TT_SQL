from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import shutil
from pathlib import Path
from app.services.schemas.schemas import QueryRequest, QueryResponse
from app.services.engines.query_service import QueryService

router = APIRouter(prefix="/api", tags=["Query"])
query_service = QueryService()

@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Standard blocking endpoint.
    """
    try:
        response = query_service.process_query(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def handle_stream(request: QueryRequest):
    """
    Streaming endpoint using Server-Sent Events (SSE).
    """
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        query_service.stream_query(request),
        media_type="text/event-stream"
    )
