from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
import os

router = APIRouter(prefix="/api/logs", tags=["Logs"])

@router.get("/raw", response_class=PlainTextResponse)
def get_raw_log_file(filename: str = Query(..., description="Log file name")):
    # Adjust this path to your actual logs directory
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "repositories", "logs")
    logs_dir = os.path.abspath(logs_dir)
    file_path = os.path.join(logs_dir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Log file not found")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {e}")
