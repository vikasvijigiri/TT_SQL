from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.services.query_service import QueryService
from app.schemas.api_schemas import QueryRequest

router = APIRouter(prefix="/api", tags=["Query"])
query_service = QueryService()

@router.post("/query")
async def handle_query(request: QueryRequest):
    """
    Blocking Text-to-SQL query endpoint.
    Processes the request and returns a complete response.
    """
    try:
        return query_service.process_query(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def handle_stream(request: QueryRequest, raw_request: Request):
    """
    Streaming Text-to-SQL query endpoint via SSE.
    Allows real-time monitoring of agent progress and tokens.
    """
    try:
        return StreamingResponse(
            query_service.stream_query(request, raw_request),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
