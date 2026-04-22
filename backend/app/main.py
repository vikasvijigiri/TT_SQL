import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.settings import settings
from app.core.logging.logger import Logger
from app.infrastructure.storage.path_manager import StorageManager
from app.api.v1.router import api_router

# 1. Initialize Infrastructure
print(f"Initializing {settings.PROJECT_NAME} Infrastructure...")
# Global data dir check
StorageManager.get_data_dir().mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=f"{settings.PRODUCT_NAME} - Modern AI Text-to-SQL Analysis Core",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    error_detail = traceback.format_exc()
    Logger.log(f"Unhandled Exception: {exc}\n{error_detail}", level="ERROR")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": str(exc)}
    )

# Root Endpoints
@app.get("/")
async def root():
    return {
        "status": "online",
        "version": "2.0.0",
        "architecture": "Domain-Driven Design (Refactored)"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}

# 2. Register Modern Versioned API
app.include_router(api_router, prefix="/api/v1")

# 3. Register Legacy Routes (Optional - depends on frontend readiness)
# For this refactor, we are moving to v1 exclusively. 
# Legacy routes can be shimmed here if needed.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
