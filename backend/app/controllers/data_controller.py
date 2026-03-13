from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import shutil
from app.repositories.registry.paths import INPUT_QUERIES_DIR, PROJECT_ROOT

router = APIRouter(prefix="/api/data", tags=["Data"])

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
    # Path to the backend .env
    env_path = PROJECT_ROOT / "backend" / ".env"
    
    # If PROJECT_ROOT is already backend
    if not env_path.parent.exists():
         env_path = PROJECT_ROOT / ".env"

    try:
        with open(env_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"status": "success", "message": ".env updated. Server should reload automatically."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .env: {e}")
