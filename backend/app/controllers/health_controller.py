from fastapi import APIRouter
from app.services.utils.health_service import HealthService

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("/db")
def get_db_status():
    """
    Check if the database/datalake is connected.
    """
    is_connected = HealthService.check_db_connection()
    return {
        "status": "connected" if is_connected else "disconnected",
        "connected": is_connected
    }
