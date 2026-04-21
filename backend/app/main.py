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

# === STARTUP: VALIDATE PATH STRUCTURE ===
# This must run FIRST before any path operations
print("\n" + "="*70)
print("INITIALIZATION: VALIDATING PATH STRUCTURE")
print("="*70)

try:
    from app.repositories.registry.path_config import get_path_structure
    path_structure = get_path_structure()
    validation_report = path_structure.validate_and_initialize()
    
    if validation_report['status'] != 'ok':
        print(f"⚠ Warning: Path validation has issues:")
        for error in validation_report.get('errors', []):
            print(f"  ✗ {error}")
        for warning in validation_report.get('warnings', []):
            print(f"  ⚠ {warning}")
    else:
        print("✓ Path structure validated successfully")
        print(f"  Results DIR: {validation_report['paths'].get('results_dir')}")
        print(f"  Data DIR: {validation_report['paths'].get('data_dir')}")
except Exception as e:
    print(f"⚠ Path structure validation error: {e}")
    # Continue anyway - app can still run with defaults

print("="*70 + "\n")

# Import settings to trigger .env loading early and paths to ensure project structure
# Ensure the backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Ensure the backend/app directory is in sys.path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from app.repositories.config import settings
from app.repositories.registry.paths import PROJECT_ROOT, initialize_directories
initialize_directories()

from controllers.query_controller import router as query_router
from controllers.health_controller import router as health_router
from controllers.prep_controller import router as prep_router
from controllers.data_controller import router as data_router
from controllers.project_controller import router as project_router
from controllers.discovery_controller import router as discovery_router
from controllers.insight_controller import router as insight_router
from controllers.auth_controller import router as auth_router
from controllers.user_controller import router as user_router
from controllers.logs_controller import router as logs_router
from services.utils.health_service import HealthService

app = FastAPI(
    title="nQuire",
    description="Layered API for Text-to-SQL logic following Controller-Service-Repository pattern.",
    version="1.0.0"
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_detail = traceback.format_exc()
    logger.error(f"Global error caught: {exc}\n{error_detail}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": error_detail if os.getenv("DEBUG") == "true" else "An unexpected error occurred."
        }
    )

# Request Logging Middleware
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(project_router)
app.include_router(discovery_router)
app.include_router(insight_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(logs_router)

if __name__ == "__main__":
    import uvicorn
    # Now running from app.main
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
