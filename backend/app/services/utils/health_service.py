import os
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.registry.paths import InstancePaths

class HealthService:
    """
    Service layer for checking system health.
    """
    
    @staticmethod
    def check_db_connection(db_name: str = None) -> bool:
        from app.repositories.config import settings
        
        target_db = db_name or settings.SCHEMA
        db_type = settings.DB_TYPE
        
        # Resolve path only if it's SQLite
        db_path = None
        if db_type.lower() == "sqlite":
             from app.repositories.registry.paths import InstancePaths
             db_path = str(InstancePaths.database(target_db))
        
        return DBRepository.check_connection(
            db_type=db_type,
            db_name=target_db,
            db_path=db_path
        )
