from fastapi import APIRouter, HTTPException
from app.models.schemas import QueryRequest, QueryResponse
from app.services.sql_service import SQLService

router = APIRouter(prefix="/api", tags=["Query"])
sql_service = SQLService()

@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    Standard blocking endpoint.
    """
    try:
        response = sql_service.process_query(request)
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
        sql_service.stream_query(request),
        media_type="text/event-stream"
    )
