import os
from app.db.sql_repo import DBRepository
from app.repositories.paths import InstancePaths

class HealthService:
    """
    Service layer for checking system health.
    """
    
    @staticmethod
    def check_db_connection(user_slug: str = None) -> bool:
        """
        Verify database connectivity, scoped by user if provided.
        """
        return DBRepository.check_connection(user_slug=user_slug)
