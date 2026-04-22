import json
import os
from pathlib import Path
from typing import Dict, Any

class SettingsRepository:
    """
    Repository for managing global application settings.
    Persists to results/global/registry/settings.json
    
    This decentralizes configuration by moving LLM and RAG settings 
    from .env to a user-editable JSON file managed via the UI.
    """
    
    @staticmethod
    def get_settings_file() -> Path:
        # Resolve results/global/registry/settings.json directly to avoid circular imports with paths.py
        data_dir = Path(__file__).resolve().parent / "data"
        path = data_dir / "results" / "global" / "registry" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        """Loads global settings from disk."""
        file_path = cls.get_settings_file()
        if not file_path.exists():
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save_settings(cls, settings_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves global settings to disk and clears relevant caches."""
        file_path = cls.get_settings_file()
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2)
            
            # Apply to in-memory settings immediately
            from app.core.settings import settings
            settings.apply_global_settings(settings_data)
            
            return settings_data
        except Exception as e:
            raise IOError(f"Failed to save global settings: {e}")

    @classmethod
    def delete_settings(cls):
        """Deletes the global settings file and resets the in-memory settings."""
        file_path = cls.get_settings_file()
        if file_path.exists():
            os.remove(file_path)
        
        # Reset in-memory settings to env defaults
        from app.core.settings import settings
        settings.reset()
