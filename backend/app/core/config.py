import os
from pathlib import Path
from typing import Optional

# Base directory (absolute path to the backend folder)
# This config is in backend/app/core/config.py
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Backend Source Directory
APP_DIR = BACKEND_DIR / "app"

# Resource Directories
RESOURCES_DIR = BACKEND_DIR / "resources"
DATABASES_DIR = RESOURCES_DIR / "databases"
DIALECTS_DIR  = RESOURCES_DIR / "dialects"
MEMORY_DIR    = RESOURCES_DIR / "memory"
LOGS_DIR      = RESOURCES_DIR / "logs"
GOLD_DIR      = RESOURCES_DIR / "gold"
INPUT_DIR     = RESOURCES_DIR / "input_data"

# Prompt Directory
PROMPTS_DIR = APP_DIR / "prompts"

# Config Directory
CONFIG_DIR = BACKEND_DIR / "config"

# Result Directory
RESULTS_DIR = BACKEND_DIR / "results"

def get_prompt_path(filename: str) -> str:
    return str(PROMPTS_DIR / filename)

def get_dialect_path(dialect: str) -> str:
    return str(DIALECTS_DIR / f"{dialect.lower()}.yaml")

def get_sqlite_db_path(db_name: str) -> str:
    return str(DATABASES_DIR / "sqlite" / f"{db_name.lower()}.sqlite")

def get_db_path(db_name: str, dialect: str = "snowflake") -> str:
    """Finds the deepest directory containing JSON metadata files for a given DB."""
    db_root = DATABASES_DIR / dialect.lower() / db_name.upper()
    if not db_root.exists():
        # Try case-insensitive or mixed case if exact upper fails
        db_root = DATABASES_DIR / dialect.lower() / db_name
        if not db_root.exists():
            raise ValueError(f"Database directory not found: {db_root}")
            
    for root, dirs, files in os.walk(str(db_root)):
        if any(f.endswith('.json') for f in files):
            return root
    raise ValueError(f"No JSON metadata files found in {db_root}")

def ensure_dirs():
    """Ensure all required directories exist."""
    dirs = [
        RESOURCES_DIR, DATABASES_DIR, DIALECTS_DIR, 
        MEMORY_DIR, MEMORY_DIR / "dialects", MEMORY_DIR / "reasoning",
        LOGS_DIR, PROMPTS_DIR, RESULTS_DIR, GOLD_DIR, INPUT_DIR
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

ensure_dirs()
