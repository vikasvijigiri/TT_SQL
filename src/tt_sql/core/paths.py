"""
Centralized Path Configuration
Defines all file and directory paths used throughout the application
"""
from pathlib import Path

# Project root - go up from core/ to project root
# current: src/tt_sql/core/paths.py
# .parent -> src/tt_sql/core
# .parent.parent -> src/tt_sql
# .parent.parent.parent -> src
# .parent.parent.parent.parent -> project_root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Source directories
SRC_DIR = PROJECT_ROOT / "src"
PACKAGE_DIR = SRC_DIR / "tt_sql"

# Configuration
CONFIG_DIR = PACKAGE_DIR / "config"
PIPELINE_CONFIG = CONFIG_DIR / "pipeline_config.yaml"

# Prompts
PROMPTS_DIR = PACKAGE_DIR / "prompts"

QUERY_PLANNING_PROMPT = PROMPTS_DIR / "query_planning.yaml"
CONTEXT_ENRICHMENT_PROMPT = PROMPTS_DIR / "context_enrichment.yaml"
SQLITE_GENERATION_PROMPT = PROMPTS_DIR / "sqlite_generation.yaml"
CRITIC_CRITIQUE_PROMPT = PROMPTS_DIR / "critic_critique.yaml"

# Workspace directories
WORKSPACE = PROJECT_ROOT / "workspace"
INPUT_DIR = WORKSPACE / "input"
OUTPUT_DIR = WORKSPACE / "output"
WORKSPACE_LOGS_DIR = WORKSPACE / "logs"

# Results directories (base)
RESULTS_BASE_DIR = PROJECT_ROOT / "results"

def get_model_results_dir(model_name: str) -> Path:
    """Get the results directory for a specific model."""
    safe_name = model_name.replace("/", "_").replace(":", "_")
    return RESULTS_BASE_DIR / safe_name

# Resources
RESOURCES_DIR = PROJECT_ROOT / "resources"
DATABASES_DIR = RESOURCES_DIR

# Evaluation
EVAL_DIR = PROJECT_ROOT  # Dataset is in root
SPIDER_DATASET = EVAL_DIR / "spider2-lite.jsonl"

# Vector store (RAG)
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
VECTOR_STORE_DB = VECTOR_STORE_DIR / "examples.db"

# Initialize directories for a specific model
def initialize_directories(model_name: str = None):
    """Create all required directories if they don't exist"""
    
    # Always create workspace and base results
    directories = [
        # Workspace
        INPUT_DIR,
        OUTPUT_DIR,
        WORKSPACE_LOGS_DIR,
        # Vector store
        VECTOR_STORE_DIR,
        # Config
        CONFIG_DIR,
    ]
    
    # If model provided, create model-specific structure
    if model_name:
        model_dir = get_model_results_dir(model_name)
        directories.extend([
            model_dir / "sql",
            model_dir / "csv",
            model_dir / "log",
            model_dir / "schema",
            model_dir / "plan",
        ])
        
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# File path generators for instance-specific files
class InstancePaths:
    """Generate paths for instance-specific files"""
    
    @staticmethod
    def sql(instance_id: str, model_name: str = "default_model") -> Path:
        """Path to SQL file for an instance"""
        return get_model_results_dir(model_name) / "sql" / f"{instance_id}.sql"
    
    @staticmethod
    def csv(instance_id: str, model_name: str = "default_model") -> Path:
        """Path to CSV results file for an instance"""
        return get_model_results_dir(model_name) / "csv" / f"{instance_id}.csv"
    
    @staticmethod
    def log(instance_id: str, model_name: str = "default_model") -> Path:
        """Path to markdown log file for an instance"""
        return get_model_results_dir(model_name) / "log" / f"{instance_id}.md"

    @staticmethod
    def schema(instance_id: str, model_name: str = "default_model") -> Path:
        """Path to schema JSON file for an instance"""
        return get_model_results_dir(model_name) / "schema" / f"{instance_id}.json"
    
    @staticmethod
    def plan(instance_id: str, model_name: str = "default_model") -> Path:
        """Path to plan markdown file for an instance"""
        return get_model_results_dir(model_name) / "plan" / f"{instance_id}.md"
    

    

    
    @staticmethod
    def database(db_name: str) -> Path:
        """
        Path to SQLite database file.
        Uses SQLITE_DB_PATH from env as the base directory.
        """
        import os
        # Get base directory from env or default to internal resources
        base_dir_str = os.getenv("SQLITE_DB_PATH", "resources/spider2-localdb")
        
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


# Initialize directories on import
initialize_directories()
