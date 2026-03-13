from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import shutil
from pathlib import Path
from app.services.schemas.schemas import QueryRequest, QueryResponse
from app.services.engines.sql_service import SQLService
from app.repositories.registry.paths import INPUT_QUERIES_DIR

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

@router.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a JSONL dataset file.
    """
    if not file.filename.endswith(('.jsonl', '.json')):
        raise HTTPException(status_code=400, detail="Only .jsonl or .json files are allowed")
    
    # Ensure directory exists
    os.makedirs(INPUT_QUERIES_DIR, exist_ok=True)
    
    # Sanitize and resolve path
    filename = os.path.basename(file.filename)
    dest_path = INPUT_QUERIES_DIR / filename
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"filename": filename, "path": str(dest_path), "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
@router.post("/upload-env")
async def upload_env(file: UploadFile = File(...)):
    """
    Upload and overwrite the .env file.
    """
    if not file.filename.endswith('.env') and file.filename != '.env':
        # Accept both ".env" and "something.env" but we'll save it as ".env"
        pass
    
    # Path to the backend .env
    from app.repositories.registry.paths import PROJECT_ROOT
    env_path = PROJECT_ROOT / "backend" / ".env"
    
    # If PROJECT_ROOT is already backend (which it is for this process)
    if not env_path.parent.exists():
         env_path = PROJECT_ROOT / ".env"

    try:
        with open(env_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"status": "success", "message": ".env updated. Server should reload automatically."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .env: {e}")
