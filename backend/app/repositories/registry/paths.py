"""
Centralized Path Configuration
Defines all file and directory paths used throughout the application
"""
from pathlib import Path
import os
import re
# import from app.repositories.config import settings # Removed to prevent circular import

# Project root - go up from app/repositories/registry/paths.py
# .parent -> app/repositories/registry
# .parent.parent -> app/repositories
# .parent.parent.parent -> app
# .parent.parent.parent.parent -> project_root
from app.repositories.registry.path_config import PROJECT_ROOT, get_path_structure

# Source directories
SRC_DIR = PROJECT_ROOT / "app"
PACKAGE_DIR = SRC_DIR

# Configuration
CONFIG_DIR = PACKAGE_DIR / "repositories" / "config"
PIPELINE_CONFIG = CONFIG_DIR / "pipeline_config.yaml"

# Prompts
PROMPTS_DIR = PACKAGE_DIR / "services" / "utils" / "prompts" 

QUERY_PLANNING_PROMPT = PROMPTS_DIR / "query_planner.yaml"
CONTEXT_ENRICHMENT_PROMPT = PROMPTS_DIR / "table_selector.yaml"
SQLITE_GENERATION_PROMPT = PROMPTS_DIR / "sql_builder.yaml"
CRITIC_CRITIQUE_PROMPT = PROMPTS_DIR / "sql_critic.yaml"

def get_user_slug(user_email: str = None, user_name: str = None) -> str:
    """
    Derives a consistent directory-safe slug from user identity.
    Enforces email-based slugs for absolute stability in multi-user mode.
    """
    if user_email:
        # Default to email prefix (most stable identifier)
        return user_email.split('@')[0].lower()
    elif user_name and user_name.strip():
        import re
        slug = user_name.lower().strip().replace(' ', '_')
        return re.sub(r'[^a-z0-9_]', '', slug)
    return "default_user"

# Results and Data (Storage & Repositories inside app/repositories/data)
DATA_DIR = PACKAGE_DIR / "repositories" / "data"

def get_repo_dir() -> Path:
    """Returns the base data storage directory (app/repositories/data)"""
    return DATA_DIR

def get_active_project_slug(user_slug: str = None) -> str:
    """
    Derive a safe filesystem slug from the active project.
    Priority: User's session state > Global settings fallback.
    Avoids high-level repository imports to prevent circular dependencies.
    """
    from app.repositories.config import settings
    active_id = None

    # 1. Try to get from user state manually
    if user_slug:
        # Hierarchical: results/username/global/registry/user_state.json
        state_path = DATA_DIR / "results" / user_slug / "global" / "registry" / "user_state.json"
        if state_path.exists():
            try:
                import json
                with open(state_path, 'r') as f:
                    state = json.load(f)
                    active_id = state.get("activeProjectId")
            except:
                pass

    # 2. Fallback to global setting (legacy/single-user)
    if not active_id:
        active_id = getattr(settings, "ACTIVE_PROJECT_ID", None)

    if not active_id:
        return "default"

    # 3. Resolve project ID to folder name (slug) by scanning
    # Hierarchical: results/{user_slug}/{project_slug}/{model_slug}/registry/project.json
    base_search = DATA_DIR / "results"
    if user_slug:
        user_dir = base_search / user_slug
        if user_dir.exists():
            for p_slug in user_dir.iterdir():
                if not p_slug.is_dir() or p_slug.name == "global":
                    continue
                
                # Check for project registry at project level
                config_path = p_slug / "registry" / "project.json"
                if config_path.exists():
                    try:
                        import json
                        with open(config_path, 'r', encoding='utf-8') as f:
                            p_data = json.load(f)
                            if p_data.get("id") == active_id:
                                return p_slug.name
                    except:
                        pass
                
                # Fallback: Scan model subfolders for legacy structure
                for m_slug in p_slug.iterdir():
                    if not m_slug.is_dir() or m_slug.name == "registry": continue
                    config_path = m_slug / "registry" / "project.json"
                    if config_path.exists():
                        try:
                            import json
                            with open(config_path, 'r', encoding='utf-8') as f:
                                p_data = json.load(f)
                                if p_data.get("id") == active_id:
                                    return p_slug.name
                        except:
                            continue
    else:
        # Scan all user directories for this project ID (fallback)
        for u_dir in base_search.iterdir():
            if not u_dir.is_dir(): continue
            for p_slug in u_dir.iterdir():
                if not p_slug.is_dir() or p_slug.name == "global": continue
                for m_slug in p_slug.iterdir():
                    if not m_slug.is_dir(): continue
                    config_path = m_slug / "registry" / "project.json"
                    if config_path.exists():
                        try:
                            import json
                            with open(config_path, 'r', encoding='utf-8') as f:
                                p_data = json.load(f)
                                if p_data.get("id") == active_id:
                                    return p_slug.name
                        except:
                            continue

    return "default"

def get_results_base_dir(user_slug: str = None, project_slug: str = None, model_name: str = None) -> Path:
    """Returns the project-centric directory for results. If model_name is provided, returns model subfolder."""
    struct = get_path_structure()
    if not user_slug:
        user_slug = get_user_slug()
    if not project_slug:
        project_slug = get_active_project_slug(user_slug)
        
    project_dir = struct.get_project_dir(user_slug, project_slug)
    
    if model_name:
        model_slug = re.sub(r'[^a-zA-Z0-9]', '_', model_name).lower().strip('_')
        return project_dir / model_slug
        
    return project_dir

def get_registry_dir(user_slug: str = None, project_slug: str = None, model_name: str = None) -> Path:
    """Returns the registry directory for the project (results/user/project/model/registry)."""
    return get_results_base_dir(user_slug, project_slug, model_name) / "registry"

def get_user_registry_dir(user_slug: str = None) -> Path:
    """Returns the user-wide global registry directory (results/user/global/registry)."""
    user_slug = user_slug or "default"
    from app.repositories.config import settings
    base = settings.RESULTS_DIR or str(DATA_DIR / "results")
    # Hierarchical structure: results/username/global/registry
    return Path(base) / user_slug / "global" / "registry"

def get_project_registry_dir(user_slug: str = None, project_slug: str = None) -> Path:
    """Returns the project-level registry directory."""
    if not user_slug:
        user_slug = get_user_slug()
    if not project_slug:
        project_slug = get_active_project_slug(user_slug)
    return get_path_structure().get_project_registry_dir(user_slug, project_slug)

def get_metadata_dir(user_slug: str = None, project_slug: str = None, model_name: str = None) -> Path:
    """Returns the metadata_extracts subfolder at the project level (Universal Path Structure)."""
    if not user_slug:
        user_slug = get_user_slug()
    if not project_slug:
        project_slug = get_active_project_slug(user_slug)
    return get_path_structure().get_metadata_dir(user_slug, project_slug)

def get_resources_dir() -> Path:
    """Returns the directory for shared resources"""
    return DATA_DIR / "resources"

def get_databases_dir() -> Path:
    """Returns the directory for SQLite databases"""
    # Prefer .env setting if provided, otherwise default to internal
    from app.repositories.config import settings
    base_dir_str = settings.SQLITE_DB_PATH or str(DATA_DIR / "sqlite")
    base_path = Path(base_dir_str)
    if not base_path.is_absolute():
        base_path = PROJECT_ROOT / base_path
    
    # SAFETY FIX: If user accidentally put file path in .env, strip filename
    if base_path.suffix == '.sqlite':
        base_path = base_path.parent
        
    return base_path

def get_input_queries_dir() -> Path:
    """Returns the directory for evaluation sets"""
    return DATA_DIR / "input_queries"

def get_spider_dataset(filename: str = None) -> Path:
    """Returns the main Spider dataset path, or a custom one if filename is provided."""
    from app.repositories.config import settings
    fname = filename or settings.BATCH_INPUT_PATH or "sample.jsonl"
    # If it's already an absolute path or has subdirectories, handle accordingly
    if os.path.isabs(fname):
        return Path(fname)
    return get_input_queries_dir() / os.path.basename(fname)

# Constants for backwards compatibility (Prefer calling functions with user_slug in multi-user mode)
REPO_DIR = DATA_DIR
RESOURCES_DIR = get_resources_dir()
INPUT_QUERIES_DIR = get_input_queries_dir()
SPIDER_DATASET = get_spider_dataset()
DATABASES_DIR = get_databases_dir()


def get_user_project_model_slugs(user_slug: str = None, user_email: str = None, user_name: str = None, model_name: str = None):
    """
    Returns (user_slug, project_slug, model_slug) for directory naming.
    """
    if not user_slug:
        user_slug = get_user_slug(user_email, user_name)
    
    from app.repositories.config import settings
    project_id = getattr(settings, "ACTIVE_PROJECT_ID", None)
    
    # Check user state if possible to get project ID
    if not project_id and user_slug:
        from app.repositories.registry.user_repo import UserRepository
        state = UserRepository.get_state(user_slug)
        project_id = state.get("activeProjectId")

    project_slug = "default_project"
    if project_id:
        from app.repositories.registry.project_repo import ProjectRepository
        project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
        if project and project.get("name"):
            import re
            project_slug = re.sub(r'[^a-zA-Z0-9]', '_', project["name"]).lower().strip('_')
    
    model_slug = (model_name or getattr(settings, "LLM_MODEL", "default_model")).replace("/", "_").replace(":", "_")
    return user_slug, project_slug, model_slug

def get_model_results_dir(model_name: str = None, user_slug: str = None, user_email: str = None, user_name: str = None) -> Path:
    """
    Returns results/{username}/{project_name}/{model_name}
    """
    from app.repositories.config import settings
    base = settings.RESULTS_DIR or str(DATA_DIR / "results")
    path = Path(base)
    u_slug, p_slug, m_slug = get_user_project_model_slugs(user_slug, user_email, user_name, model_name)
    return path / u_slug / p_slug / m_slug


def get_next_instance_id(model_name: str = None, user_slug: str = None) -> str:
    """
    Find the next available qXXX instance ID by scanning the model-specific log directory.
    This ensures that instance IDs are incremental based on the actual number of queries run.
    """
    import re
    from app.repositories.config import settings
    if not model_name:
        model_name = settings.LLM_MODEL or "gpt-default"
    
    existing_nums = []
    # Regex to match q followed by digits (e.g., q001, q123)
    q_pattern = re.compile(r'^q(\d+)')
    
    # Scan model-specific results for any files matching qXXX prefix
    model_dir = get_model_results_dir(model_name, user_slug=user_slug)
    if not model_dir.exists():
        return "q001"
    
    for f in model_dir.iterdir():
        if f.is_dir(): continue
        match = q_pattern.match(f.stem)
        if match:
            try:
                existing_nums.append(int(match.group(1)))
            except ValueError:
                continue
    
    next_num = max(existing_nums, default=0) + 1
    return f"q{next_num:03d}"

def get_unique_run_id(collection_name: str, db_name: str, instance_id: str = None) -> str:
    """
    Generate a unique, context-aware run identifier.
    Format: collection_db_instance_date_time
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%m%d_%H%M")
    safe_coll = collection_name.replace("-", "_").replace(" ", "_").lower()
    safe_db = db_name.replace("-", "_").replace(" ", "_").lower()
    
    parts = [safe_coll, safe_db]
    if instance_id:
        parts.append(instance_id)
    parts.append(timestamp)
    
    return "_".join(parts)

# Initialize directories for a specific project/model context
def initialize_directories(model_name: str = None, user_slug: str = None):
    """Create all required directories if they don't exist"""
    from app.repositories.config import settings
    
    # 1. Project level directories
    base_dir = get_results_base_dir(user_slug)
    directories = [
        base_dir,
        base_dir / "metadata_extracts",
        base_dir / "registry",
        get_user_registry_dir(user_slug)
    ]
    
    # 2. Model level directory (Flattened: no sql/csv/logs subfolders)
    # We always ensure the model result directory exists
    m_name = model_name or getattr(settings, "LLM_MODEL", "default")
    model_dir = get_model_results_dir(m_name, user_slug=user_slug)
    directories.append(model_dir)
        
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# File path generators for instance-specific files
class InstancePaths:
    """
    Generate paths for instance-specific files.
    FLATTENED: Files are stored directly in the model directory.
    """
    
    @staticmethod
    def sql(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None, user_slug: str = None) -> Path:
        """Path to SQL file for an instance (Flat structure)"""
        root = base_dir or get_model_results_dir(model_name, user_slug)
        filename = f"{run_id or instance_id}.sql"
        return root / filename
    
    @staticmethod
    def csv(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None, user_slug: str = None) -> Path:
        """Path to CSV results file for an instance (Flat structure)"""
        root = base_dir or get_model_results_dir(model_name, user_slug)
        filename = f"{run_id or instance_id}.csv"
        return root / filename
    
    @staticmethod
    def log(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None, user_slug: str = None) -> Path:
        """Path to markdown log file for an instance (Flat structure)"""
        root = base_dir or get_model_results_dir(model_name, user_slug)
        filename = f"{run_id or instance_id}.md"
        return root / filename

    @staticmethod
    def metadata(run_id: str, user_slug: str = None, project_slug: str = None) -> Path:
        """Path to unique metadata JSON for a run"""
        return get_metadata_dir(user_slug, project_slug) / f"{run_id}.json"

    @staticmethod
    def database(db_name: str) -> Path:
        """
        Path to SQLite database file.
        Uses the centralized get_databases_dir.
        """
        base_path = get_databases_dir()
            
        # Ensure extension
        filename = f"{db_name}.sqlite" if not db_name.endswith(".sqlite") else db_name
        
        return base_path / filename
