import os
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import logging

# Configure basic logging for FastAPI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nQuire")

# Import settings to trigger .env loading early and paths to ensure project structure
from app.repositories.config import settings
from app.repositories.registry.paths import PROJECT_ROOT, initialize_directories
initialize_directories()

# Ensure the project root is in sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.controllers.query_controller import router as query_router
from app.controllers.health_controller import router as health_router
from app.controllers.prep_controller import router as prep_router
from app.controllers.data_controller import router as data_router
from app.services.utils.health_service import HealthService

app = FastAPI(
    title="nQuire",
    description="Layered API for Text-to-SQL logic following Controller-Service-Repository pattern.",
    version="1.0.0"
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error caught: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if os.getenv("DEBUG") == "true" else "An unexpected error occurred."
        }
    )

# Request Logging Middleware
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root status endpoint
@app.get("/")
async def root():
    return {
        "message": "nQuire Agentic API is running",
        "architecture": "Controller-Service-Repository",
        "status": "online"
    }

@app.get("/health/deep")
def deep_health():
    """Enriched health check verifying system connectivity."""
    db_ok = HealthService.check_db_connection()
    # Note: Vector store check could be added here as well
    return {
        "status": "healthy" if db_ok else "degraded",
        "components": {
            "database": "connected" if db_ok else "disconnected",
            "api": "running"
        },
        "timestamp": time.time()
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Include Modular Routers
app.include_router(query_router)
app.include_router(health_router)
app.include_router(prep_router)
app.include_router(data_router)

if __name__ == "__main__":
    import uvicorn
    # Use app.controllers.main:app since we are now in app/controllers
    uvicorn.run("app.controllers.main:app", host="0.0.0.0", port=8000, reload=True)
