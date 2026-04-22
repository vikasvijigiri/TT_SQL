"""
Centralized Path Resolution Wrapper
===================================
Wraps PathStructure singleton to provide a clean, functional interface for 
directory resolution throughout the application.

DATA PERSISTENCE POLICY:
Analytical results are stored permanently in the root data/ folder.
"""
from pathlib import Path
import os
import re
from app.repositories.path_config import PROJECT_ROOT, get_path_structure

# Global Singleton Access
struct = get_path_structure()

# --- Core Directories ---
DATA_DIR = struct.get_data_dir()
SRC_DIR = PROJECT_ROOT / "app"
PROMPTS_DIR = struct.get_prompts_dir()

# Evaluation Paths 

def get_data_dir() -> Path:
    """Alias for structural data directory."""
    return struct.get_data_dir()

def get_results_base_dir(user_slug: str = None) -> Path:
    """Returns the base results directory for a user or global."""
    return struct.get_user_dir(user_slug or get_user_slug())

def get_safe_slug(text: str) -> str:
    """Creates a filesystem-safe slug from input text."""
    if not text: return "default"
    return re.sub(r'[^a-zA-Z0-9]', '_', text).lower().strip('_')

def get_user_slug(user_email: str = None, user_name: str = None) -> str:
    """Derives a safe slug from user identity (Email prefix preferred)."""
    if user_email: return user_email.split('@')[0].lower()
    if user_name: return get_safe_slug(user_name)
    return "default_user"

def get_active_project_id(user_slug: str = None) -> str:
    """Resolves active project ID via user state or global settings."""
    from app.repositories.user_repo import UserRepository
    user_slug = user_slug or get_user_slug()
    try:
        user_state = UserRepository.get_state(user_slug)
        active_id = user_state.get("activeProjectId")
        if active_id: return active_id
    except: pass
    
    try:
        from app.repositories.project_repo import ProjectRepository
        projects = ProjectRepository.get_all_projects(user_slug)
        if projects: return projects[0].get("id")
    except: pass
    
    from app.core.settings import settings
    return getattr(settings, "ACTIVE_PROJECT_ID", None)

def get_active_project_slug(user_slug: str = None) -> str:
    """Resolves active project SLUG (folder name) from active project ID."""
    from app.repositories.project_repo import ProjectRepository
    user_slug = user_slug or get_user_slug()
    project_id = get_active_project_id(user_slug)
    
    if not project_id:
        return "default"
    
    try:
        project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
        if project and project.get("_slug"):
            return project["_slug"]
    except:
        pass
    
    return "default"

def get_model_results_dir(model_name: str = None, user_slug: str = None, project_slug: str = None) -> Path:
    """Get results/{user}/{project}/{model}/ directory."""
    from app.core.settings import settings
    model_name = model_name or settings.LLM_MODEL or "default"
    if not user_slug: user_slug = get_user_slug()
    if not project_slug: project_slug = get_active_project_id() or "default"
    return struct.get_model_scoped_dir(user_slug, project_slug, model_name)

def get_metadata_dir(user_slug: str = None, project_slug: str = None, model_name: str = None) -> Path:
    """Get results/{user}/{project}/metadata_extracts/ directory (Model-agnostic)."""
    from app.core.settings import settings
    model_name = model_name or settings.LLM_MODEL or "default"
    if not user_slug: user_slug = get_user_slug()
    if not project_slug: project_slug = get_active_project_id() or "default"
    return struct.get_metadata_dir(user_slug, project_slug, model_name=model_name)

def get_project_dir(user_slug: str, project_slug: str) -> Path:
    """Get results/{user}/{project}/ directory."""
    return struct.get_project_dir(user_slug, project_slug)

def get_project_registry_dir(user_slug: str, project_slug: str) -> Path:
    """Canonical path to results/{user}/{project}/registry - where project.json lives."""
    return struct.get_project_registry_dir(user_slug, project_slug)

def get_user_registry_dir(user_slug: str) -> Path:
    """Get results/{user}/global/registry/ directory."""
    return struct.get_user_global_registry_dir(user_slug)

def get_databases_dir() -> Path:
    """Returns resolved SQLite directory."""
    return struct.get_databases_dir()

def get_next_instance_id(model_name: str = "default", user_slug: str = None) -> str:
    """Generates a unique instance ID for a query."""
    import time
    import uuid
    ts = int(time.time())
    short_uuid = str(uuid.uuid4())[:8]
    return f"{ts}_{short_uuid}"

def initialize_directories(model_name: str = None, user_slug: str = None, project_slug: str = "default"):
    """Ensures structure exists for the current context (STRICT: 4 folders only)."""
    user_slug = user_slug or get_user_slug()
    
    directories = [
        struct.get_user_dir(user_slug),
        struct.get_project_dir(user_slug, project_slug),
        struct.get_metadata_dir(user_slug, project_slug),
        struct.get_sql_outputs_dir(user_slug, project_slug),
        struct.get_csv_outputs_dir(user_slug, project_slug),
        struct.get_logs_dir(user_slug, project_slug),
    ]
    for d in directories: d.mkdir(parents=True, exist_ok=True)

class InstancePaths:
    """Helpers for instance-specific files (Directly in project subfolders)."""
    @staticmethod
    def sql(instance_id: str, project_dir: Path) -> Path: return project_dir / "sql" / f"{instance_id}.sql"
    
    @staticmethod
    def csv(instance_id: str, project_dir: Path) -> Path: return project_dir / "csv" / f"{instance_id}.csv"
    
    @staticmethod
    def log(instance_id: str, project_dir: Path) -> Path: return project_dir / "logs" / f"{instance_id}.md"

    @staticmethod
    def database(db_name: str) -> Path:
        base = get_databases_dir()
        name = db_name if db_name.endswith(".sqlite") else f"{db_name}.sqlite"
        return base / name
