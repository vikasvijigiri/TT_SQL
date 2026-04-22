import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.config.settings import settings

# Project root - go up from app/infrastructure/storage/path_manager.py
# path_manager.py (0) -> storage (1) -> infrastructure (2) -> app (3) -> backend (4)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class StorageManager:
    """
    Industry-standard storage and path manager.
    Enforces the minimalist 4-folder project policy and handles all path resolution.
    """
    
    STRUCTURE = {
        "data": "data",
        "results": "results",
        "metadata": "metadata_extracts",
        "sql": "sql",
        "csv": "csv",
        "logs": "logs"
    }

    @classmethod
    def get_data_dir(cls) -> Path:
        """Base directory for all persistent data."""
        return PROJECT_ROOT / cls.STRUCTURE["data"]

    @classmethod
    def get_results_root(cls) -> Path:
        """Base directory for all user/project analytical results."""
        return cls.get_data_dir() / cls.STRUCTURE["results"]

    @classmethod
    def get_user_slug(cls, email: str = None, name: str = None) -> str:
        """Generates a filesystem-safe user identifier."""
        if email: return email.split('@')[0].lower()
        if name: return cls.get_safe_slug(name)
        return "default_user"

    @classmethod
    def get_safe_slug(cls, text: str) -> str:
        """Sanitizes text for use in file paths."""
        if not text: return "default"
        return re.sub(r'[^a-zA-Z0-9]', '_', text).lower().strip('_')

    @classmethod
    def get_project_dir(cls, user_slug: str, project_slug: str) -> Path:
        """Path to results/{user}/{project}."""
        return cls.get_results_root() / user_slug / project_slug

    @classmethod
    def resolve_sqlite_path(cls, path: str, db_name: str = "") -> str:
        """Resolves raw SQLite paths into absolute project-scoped paths."""
        if path and os.path.isabs(path): return path
        
        # Default to data/sqlite/{name}.sqlite if no absolute path provided
        sqlite_dir = cls.get_data_dir() / "sqlite"
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        
        name = path or db_name or "default"
        if not name.endswith(".sqlite"): name += ".sqlite"
        return str(sqlite_dir / name)

    @classmethod
    def initialize_project(cls, user_slug: str, project_slug: str):
        """Provision the mandatory 4-folder structure for a project."""
        base = cls.get_project_dir(user_slug, project_slug)
        for folder in [cls.STRUCTURE["metadata"], cls.STRUCTURE["sql"], cls.STRUCTURE["csv"], cls.STRUCTURE["logs"]]:
            (base / folder).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance_id(cls) -> str:
        """Generates a unique timestamped identifier for an execution instance."""
        import time, uuid
        return f"{int(time.time())}_{str(uuid.uuid4())[:8]}"

    @classmethod
    def get_file_path(cls, category: str, instance_id: str, user_slug: str, project_slug: str, extension: str = "") -> Path:
        """Helper to get a specific file path within a project category."""
        folder = cls.STRUCTURE.get(category, category)
        filename = f"{instance_id}{extension}"
        return cls.get_project_dir(user_slug, project_slug) / folder / filename
