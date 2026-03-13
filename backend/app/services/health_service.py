import os
from app.repos.sql_repo import DBRepository
from app.models.paths import InstancePaths

class HealthService:
    """
    Service layer for checking system health.
    """
    
    @staticmethod
    def check_db_connection(db_name: str = None) -> bool:
        if not db_name:
            from app.models.config import settings
            db_name = settings.COLLECTION_NAME or settings.DB_NAME
        db_type = os.getenv("DB_TYPE", "sqlite")
        db_path = str(InstancePaths.database(db_name))
        
        return DBRepository.check_connection(
            db_type=db_type,
            db_name=db_name,
            db_path=db_path
        )
