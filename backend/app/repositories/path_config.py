"""
PATH CONFIGURATION & STRUCTURE DEFINITION
=========================================
Single source of truth for the entire application's folder structure.

This document defines the canonical folder hierarchy. Any changes to the folder 
structure should be reflected ONLY in this file, and all paths throughout the 
application automatically adapt.

FOLDER STRUCTURE (CANONICAL):
=============================
PROJECT_ROOT/
├── backend/
│   ├── app/
│   │   ├── repositories/
│   │   │   ├── data/                          (DATA_DIR - All application data)
│   │   │   │   ├── results/                   (RESULTS_DIR - Multi-user, multi-project)
│   │   │   │   │   └── {user_slug}/           (USER_DIR - Per-user workspace)
│   │   │   │   │       ├── global/            (Global user config)
│   │   │   │   │       │   └── registry/
│   │   │   │   │       │       ├── project.json
│   │   │   │   │       │       └── user_state.json
│   │   │   │   │       └── {project_slug}/    (Per-project workspace)
│   │   │   │   │           └── registry/
│   │   │   │   │               └── project.json
│   │   │   │   ├── resources/                 (Shared resources)
│   │   │   │   ├── input_queries/             (Evaluation datasets)
│   │   │   │   └── sqlite/                    (SQLite database files)
│   │   │   └── config/
│   │   │       └── pipeline_config.yaml
│   │   └── services/
│   │       └── utils/
│   │           └── prompts/
│   │               ├── query_planner.yaml
│   │               ├── table_selector.yaml
│   │               ├── sql_builder.yaml
│   │               └── sql_critic.yaml
│   └── new_venv/
└── frontend/

ENVIRONMENT OVERRIDES:
======================
These environment variables can override the default structure:
- RESULTS_DIR: Custom location for results/ folder (default: app/repositories/data/results)
- DATA_DIR: Custom location for data/ folder (default: app/repositories/data)
- SQLITE_DB_PATH: Custom location for SQLite databases
- METADATA_DIR: Custom metadata location

PRODUCTION DEPLOYMENT:
======================
To change folder structure in production:
1. Modify ONLY the environment variables in your deployment config
2. All paths automatically route through this configuration
3. No code changes required
4. Backward compatible - missing env vars use defaults
"""

from pathlib import Path
import os
from typing import Dict, Any

# Project root - go up from app/repositories/path_config.py
# path_config.py (0) -> repositories (1) -> app (2) -> backend (3)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class PathStructure:
    """
    Production-standard path configuration manager.
    
    Single source of truth for all folder structure decisions.
    All paths in the application route through these functions.
    
    INDUSTRY STANDARDS IMPLEMENTED:
    ✅ Centralized configuration (no scattered path logic)
    ✅ Environment override capability (deployment flexibility)
    ✅ Validation on startup
    ✅ Automatic folder creation
    ✅ Fallback to sensible defaults
    ✅ Type-safe Path objects (cross-platform)
    ✅ Immutable structure documentation
    """
    
    STRUCTURE = {
        "data": "data",
        "results": "results",                    # Relative to DATA_DIR
        
        # Per project structure (relative to results/{user}/{project})
        "metadata_extracts": "metadata_extracts",
        "sql_outputs": "sql",
        "csv_outputs": "csv",
        "logs": "logs",
        
        # Registries are now at the root of their respective scopes
        "project_registry": "", 
        "global_registry": ""
    }
    
    def __init__(self, project_root: Path):
        """Initialize PathStructure with a project root."""
        self.project_root = project_root.resolve()
        
    def validate_and_initialize(self) -> Dict[str, Any]:
        """
        Validates the path structure and creates missing directories.
        Called at application startup.
        
        Returns:
            Dict with validation results and all key paths
        """
        report = {
            "status": "ok",
            "errors": [],
            "warnings": [],
            "paths": {}
        }
        
        try:
            # Validate and create essential directories
            essential_dirs = [
                self.get_data_dir(),
                self.get_results_dir(),
            ]
            
            for dir_path in essential_dirs:
                if not dir_path.exists():
                    try:
                        dir_path.mkdir(parents=True, exist_ok=True)
                        report["warnings"].append(f"Created missing directory: {dir_path}")
                    except Exception as e:
                        report["status"] = "error"
                        report["errors"].append(f"Failed to create {dir_path}: {e}")
            
            # Populate paths in report
            report["paths"] = {
                "project_root": str(self.project_root),
                "data_dir": str(self.get_data_dir()),
                "results_dir": str(self.get_results_dir()),
            }
            
            return report
            
        except Exception as e:
            report["status"] = "error"
            report["errors"].append(f"Validation failed: {str(e)}")
            return report
    
    # === GETTERS (all paths route through here) ===
    
    def get_data_dir(self) -> Path:
        """Get DATA_DIR: app/repositories/data (or override from settings)"""
        try:
            from app.core.settings import settings
            data_override = getattr(settings, "DATA_DIR", None)
            if data_override:
                path = Path(data_override)
                return path if path.is_absolute() else self.project_root / path
        except ImportError:
            pass
        return self.project_root / self.STRUCTURE["data"]
    
    def get_results_dir(self) -> Path:
        """Get RESULTS_DIR: results/ (or override from settings)"""
        try:
            from app.core.settings import settings
            results_override = getattr(settings, "RESULTS_DIR", None)
            if results_override:
                path = Path(results_override)
                return path if path.is_absolute() else self.project_root / path
        except ImportError:
            pass
        return self.get_data_dir() / self.STRUCTURE["results"]
    
    # Legacy resource getters removed to comply with strict folder policy.

    
    def get_prompts_dir(self) -> Path:
        """Get prompts/ directory"""
        return self.project_root / "app/services/prompts"
    
    def get_user_dir(self, user_slug: str) -> Path:
        """Get results/{user}/ directory"""
        return self.get_results_dir() / user_slug
    
    def get_user_global_registry_dir(self, user_slug: str) -> Path:
        """Get results/{user}/ directory (Registry at root)"""
        return self.get_user_dir(user_slug)
    
    def get_project_dir(self, user_slug: str, project_slug: str) -> Path:
        """Get results/{user}/{project}/ directory"""
        return self.get_user_dir(user_slug) / project_slug
    
    def get_model_scoped_dir(self, user_slug: str, project_slug: str, model_name: str = "default") -> Path:
        """Get the model-scoped directory (Flattened to Project Root)."""
        return self.get_project_dir(user_slug, project_slug)

    def get_project_registry_dir(self, user_slug: str, project_slug: str) -> Path:
        """Get results/{user}/{project}/ directory (Registry moved to root)"""
        return self.get_project_dir(user_slug, project_slug)
    
    def get_metadata_dir(self, user_slug: str, project_slug: str, model_name: str = "default") -> Path:
        """Get results/{user}/{project}/metadata_extracts/ directory (Model-agnostic)"""
        return self.get_project_dir(user_slug, project_slug) / self.STRUCTURE["metadata_extracts"]
    
    def get_sql_outputs_dir(self, user_slug: str, project_slug: str, model_name: str = "default") -> Path:
        """Get results/{user}/{project}/sql/ directory (Model-agnostic)"""
        return self.get_model_scoped_dir(user_slug, project_slug, model_name) / self.STRUCTURE["sql_outputs"]
    
    def get_csv_outputs_dir(self, user_slug: str, project_slug: str, model_name: str = "default") -> Path:
        """Get results/{user}/{project}/csv/ directory (Model-agnostic)"""
        return self.get_model_scoped_dir(user_slug, project_slug, model_name) / self.STRUCTURE["csv_outputs"]
    
    def get_logs_dir(self, user_slug: str, project_slug: str, model_name: str = "default") -> Path:
        """Get results/{user}/{project}/logs/ directory (Model-agnostic)"""
        return self.get_model_scoped_dir(user_slug, project_slug, model_name) / self.STRUCTURE["logs"]
    
    def get_all_paths(self) -> Dict[str, str]:
        """
        Returns a dictionary of all key paths.
        Used by frontend health check to verify structure.
        """
        return {
            "data_dir": str(self.get_data_dir()),
            "results_dir": str(self.get_results_dir()),
            "prompts_dir": str(self.get_prompts_dir()),
        }


# Global singleton instance
_path_structure_instance = None


def get_path_structure() -> PathStructure:
    """Get the global PathStructure instance."""
    global _path_structure_instance
    if _path_structure_instance is None:
        _path_structure_instance = PathStructure(PROJECT_ROOT)
    return _path_structure_instance
