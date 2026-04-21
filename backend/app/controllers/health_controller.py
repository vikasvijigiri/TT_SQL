from fastapi import APIRouter
from app.services.utils.health_service import HealthService

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("/db")
def get_db_status(user_email: str = None, user_name: str = None):
    """
    Check if the database/datalake is connected.
    """
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    is_connected = HealthService.check_db_connection(user_slug=user_slug)
    return {
        "status": "connected" if is_connected else "disconnected",
        "connected": is_connected
    }

@router.get("/paths")
def get_path_structure():
    """
    Returns the complete folder structure configuration.
    Frontend uses this to verify all paths are accessible.
    
    PRODUCTION STANDARD: Single source of truth for all paths.
    Frontend should query this endpoint instead of assuming folder structure.
    """
    from app.repositories.registry.path_config import get_path_structure
    path_structure = get_path_structure()
    
    return {
        "status": "ok",
        "paths": path_structure.get_all_paths(),
        "structure": {
            "description": "Canonical folder hierarchy - DO NOT HARDCODE PATHS IN FRONTEND",
            "data_dir": "app/repositories/data (root for all application data)",
            "results_dir": "results/ (multi-user, multi-project)",
            "user_dir": "results/{user_slug}/",
            "global_registry": "results/{user_slug}/global/registry/",
            "project_dir": "results/{user_slug}/{project_slug}/",
            "project_registry": "results/{user_slug}/{project_slug}/registry/project.json",
            "metadata": "results/{user_slug}/{project_slug}/metadata_extracts/",
            "note": "All paths are relative to PROJECT_ROOT unless overridden by environment variables"
        }
    }

@router.get("/startup")
def startup_validation():
    """
    Validates the application's folder structure on startup.
    Called by frontend on load to ensure all systems are ready.
    
    Returns:
        - status: 'ok' if all paths valid, 'error' if problems found
        - errors: List of critical issues
        - warnings: List of recoverable issues
        - paths: All validated paths
    """
    from app.repositories.registry.path_config import get_path_structure
    path_structure = get_path_structure()
    
    return path_structure.validate_and_initialize()
