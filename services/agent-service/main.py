"""
TT_SQL_PLATFORM -- agent-service entry point
============================================
Start:      uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Via script: ./scripts/start.sh

Package layout:
  services/agent-service/core/        AI engine (agents, validators, orchestration, learning...)
  services/agent-service/api/         HTTP layer (FastAPI, routes, auth, db)
  services/agent-service/workers/     Background workers (DAB evaluator, benchmark runner)
  services/agent-service/config/      Static config + system_params.yaml
"""
import sys
from pathlib import Path

# Ensure services/agent-service/ is the package root
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# -- Load the canonical API application --------------------------
try:
    from api.api import app  # new canonical location
except ImportError:
    try:
        from agent.app.api import app  # legacy fallback (still running)
    except ImportError:
        app = FastAPI(title="TT_SQL_PLATFORM", version="1.0.0")
        app.add_middleware(GZipMiddleware, minimum_size=1024)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:8080"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


@app.get("/health", tags=["ops"], include_in_schema=False)
def root_health():
    """Root health endpoint -- confirms the backend is running."""
    return {"status": "ok", "version": "1.0.0", "service": "agent-service"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
