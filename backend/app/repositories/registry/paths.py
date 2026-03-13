"""
Centralized Path Configuration
Defines all file and directory paths used throughout the application
"""
from pathlib import Path
import os
from app.repositories.config import settings

# Project root - go up from app/repositories/registry/paths.py
# .parent -> app/repositories/registry
# .parent.parent -> app/repositories
# .parent.parent.parent -> app
# .parent.parent.parent.parent -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

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

# Results and Data (Storage & Repositories inside app/repositories/data)
DATA_DIR = PACKAGE_DIR / "repositories" / "data"

def get_repo_dir() -> Path:
    """Returns the base data storage directory (app/repositories/data)"""
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
    fname = filename or settings.BATCH_INPUT_PATH or "sample.jsonl"
    # If it's already an absolute path or has subdirectories, handle accordingly
    if os.path.isabs(fname):
        return Path(fname)
    return get_input_queries_dir() / os.path.basename(fname)

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
        Uses the centralized get_databases_dir.
        """
        base_path = get_databases_dir()
            
        # Ensure extension
        filename = f"{db_name}.sqlite" if not db_name.endswith(".sqlite") else db_name
        
        return base_path / filename
