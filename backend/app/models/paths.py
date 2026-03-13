"""
Centralized Path Configuration
Defines all file and directory paths used throughout the application
"""
from pathlib import Path
import os
from app.models.config import settings

# Project root - go up from app/models/paths.py
# .parent -> app/models
# .parent.parent -> app
# .parent.parent.parent -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Source directories
SRC_DIR = PROJECT_ROOT / "app"
PACKAGE_DIR = SRC_DIR  # In the new structure, app is the package

# Configuration
CONFIG_DIR = PACKAGE_DIR / "models" / "config"
PIPELINE_CONFIG = CONFIG_DIR / "pipeline_config.yaml"

# Prompts
PROMPTS_DIR = PACKAGE_DIR / "services" / "prompts"

QUERY_PLANNING_PROMPT = PROMPTS_DIR / "query_planner.yaml"
CONTEXT_ENRICHMENT_PROMPT = PROMPTS_DIR / "table_selector.yaml"
SQLITE_GENERATION_PROMPT = PROMPTS_DIR / "sql_builder.yaml"
CRITIC_CRITIQUE_PROMPT = PROMPTS_DIR / "sql_critic.yaml"

# Results and Data (Storage & Repositories inside app/repos/data)
DATA_DIR = PACKAGE_DIR / "repos" / "data"

def get_repo_dir() -> Path:
    """Returns the base data storage directory (app/repos/data)"""
    return DATA_DIR

def get_results_base_dir() -> Path:
    """Returns the directory for query results"""
    base = settings.RESULTS_DIR or str(DATA_DIR / "results")
    return Path(base)

def get_metadata_dir() -> Path:
    """Returns the directory for database schemas"""
    base = settings.METADATA_DIR or str(DATA_DIR / "metadata_extracts")
    return Path(base)

def get_resources_dir() -> Path:
    """Returns the directory for shared resources"""
    return DATA_DIR / "resources"

def get_databases_dir() -> Path:
    """Returns the directory for SQLite databases"""
    # Prefer .env setting if provided, otherwise default to internal
    base_dir_str = settings.SQLITE_DB_PATH or str(DATA_DIR / "sqlite")
    return Path(base_dir_str)

def get_input_queries_dir() -> Path:
    """Returns the directory for evaluation sets"""
    return DATA_DIR / "input_queries"

def get_spider_dataset() -> Path:
    """Returns the main Spider dataset path"""
    return get_input_queries_dir() / "spider2-lite.jsonl"

# Constants for backwards compatibility
REPO_DIR = DATA_DIR
RESOURCES_DIR = get_resources_dir()
METADATA_DIR = get_metadata_dir()
INPUT_QUERIES_DIR = get_input_queries_dir()
SPIDER_DATASET = get_spider_dataset()
DATABASES_DIR = get_databases_dir()

def get_model_results_dir(model_name: str) -> Path:
    """Get the results directory for a specific model."""
    safe_name = model_name.replace("/", "_").replace(":", "_")
    return get_results_base_dir() / safe_name


def get_next_instance_id(model_name: str = None) -> str:
    """
    Find the next available qXXX instance ID by scanning the model-specific log directory.
    This ensures that instance IDs are incremental based on the actual number of queries run.
    """
    import re
    if not model_name:
        model_name = settings.LLM_MODEL or "gpt-default"
    
    log_dir = get_model_results_dir(model_name) / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    existing_nums = []
    # Regex to match q followed by digits (e.g., q001, q123)
    q_pattern = re.compile(r'^q(\d+)')
    
    # Scan model-specific results (sql, csv, log) to find the highest ID
    search_dirs = [
        log_dir,
        get_model_results_dir(model_name) / "sql",
        get_model_results_dir(model_name) / "csv"
    ]
    
    for d in search_dirs:
        if not d.exists(): continue
        for f in d.iterdir():
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

# Initialize directories for a specific model
def initialize_directories(model_name: str = None):
    """Create all required directories if they don't exist"""
    
    # Always create base results and config
    directories = [
        get_results_base_dir(),
        get_metadata_dir(),
    ]
    
    # If model provided, create model-specific structure
    if model_name:
        model_dir = get_model_results_dir(model_name)
        directories.extend([
            model_dir / "sql",
            model_dir / "csv",
            model_dir / "log",
        ])
        
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# File path generators for instance-specific files
class InstancePaths:
    """Generate paths for instance-specific files"""
    
    @staticmethod
    def sql(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None) -> Path:
        """Path to SQL file for an instance"""
        root = base_dir or get_model_results_dir(model_name)
        filename = f"{run_id or instance_id}.sql"
        return root / "sql" / filename
    
    @staticmethod
    def csv(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None) -> Path:
        """Path to CSV results file for an instance"""
        root = base_dir or get_model_results_dir(model_name)
        filename = f"{run_id or instance_id}.csv"
        return root / "csv" / filename
    
    @staticmethod
    def log(instance_id: str, model_name: str = "default_model", base_dir: Path = None, run_id: str = None) -> Path:
        """Path to markdown log file for an instance"""
        filename = f"{run_id or instance_id}.md"
        if base_dir:
            return base_dir / filename
        
        root = get_model_results_dir(model_name) / "log"
        return root / filename
    
    @staticmethod
    def metadata(run_id: str) -> Path:
        """Path to unique metadata JSON for a run"""
        return get_metadata_dir() / f"{run_id}.json"

    @staticmethod
    def database(db_name: str) -> Path:
        """
        Path to SQLite database file.
        Uses SQLITE_DB_PATH from settings as the base directory.
        """
        base_dir_str = settings.SQLITE_DB_PATH
        
        # Check if it's absolute, otherwise relative to project root
        base_path = Path(base_dir_str)
        if not base_path.is_absolute():
            base_path = PROJECT_ROOT / base_path
            
        # SAFETY FIX: If user accidentally put file path in .env, strip filename
        if base_path.suffix == '.sqlite':
            base_path = base_path.parent
            
        # Ensure extension
        filename = f"{db_name}.sqlite" if not db_name.endswith(".sqlite") else db_name
        
        return base_path / filename
