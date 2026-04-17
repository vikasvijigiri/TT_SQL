import os
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.registry.paths import InstancePaths

class HealthService:
    """
    Service layer for checking system health.
    """
    
    @staticmethod
    def check_db_connection() -> bool:
        from app.repositories.config import settings
        
        # If no project is active, we consider the "managed" DB offline
        if not settings.ACTIVE_PROJECT_ID:
            return False
            
        return DBRepository.check_connection()
