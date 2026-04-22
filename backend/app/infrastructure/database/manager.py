import os
from typing import Dict, Any, Optional
from .base import DatabaseConnector, QueryResult
from .postgres import PostgresConnector
from .sqlite import SQLiteConnector
from app.core.config.settings import settings

class DatabaseManager:
    """
    Factory and resolver for active database connections.
    Centralizes project-scoped and user-scoped database resolution.
    """
    
    @staticmethod
    def get_active_config(user_slug: str = None) -> Dict[str, Any]:
        """Resolve the active database connection details from registries."""
        active_id = None
        if user_slug:
            from app.repositories.user_repo import UserRepository
            user_state = UserRepository().get_state(user_slug)
            active_id = user_state.get("activeProjectId")

        active_id = active_id or settings.ACTIVE_PROJECT_ID
        if not active_id: return {}

        from app.repositories.project_repo import ProjectRepository
        project = ProjectRepository.get_project_by_id(active_id, user_slug=user_slug)
        if not project: return {}
        
        return project.get("connection", {})

    @classmethod
    def get_connector(cls, user_slug: str = None, connection_override: Dict[str, Any] = None) -> DatabaseConnector:
        """Returns the appropriate DatabaseConnector instance based on active config."""
        config = connection_override or cls.get_active_config(user_slug)
        db_type = (config.get("db_type") or "").lower()
        
        if db_type in ["postgres", "postgresql"]:
            return PostgresConnector(config)
        elif db_type == "sqlite":
            path = config.get("sqlite_path")
            if not path or not os.path.isabs(path):
                # Resolve relative paths against storage logic (to be refactored)
                from app.infrastructure.storage.path_manager import StorageManager
                path = StorageManager.resolve_sqlite_path(path, config.get("db_name", ""))
            return SQLiteConnector(path)
        
        raise ValueError(f"Unsupported or unconfigured database type: {db_type}")

    @classmethod
    def execute(cls, query: str, user_slug: str = None) -> QueryResult:
        """Convenience method to execute a query on the active connector."""
        connector = cls.get_connector(user_slug)
        return connector.execute(query)
