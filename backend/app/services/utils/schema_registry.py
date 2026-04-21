import json
import functools
from pathlib import Path
from typing import Dict, Any, Optional
from app.services.utils.logger import Logger

class SchemaRegistry:
    """
    Centralized registry for project schema metadata.
    Uses LRU caching to prevent redundant disk I/O when hydrating context.
    """
    
    @staticmethod
    @functools.lru_cache(maxsize=16)
    def get_metadata(file_path: str) -> Dict[str, Any]:
        """
        Loads and caches metadata from a JSON file.
        Returns the 'tables' dictionary from the metadata.
        """
        path = Path(file_path)
        if not path.exists():
            Logger.log(f"Metadata file not found for caching: {file_path}", level="WARNING")
            return {}
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metadata = data.get("tables", {})
                Logger.log(f"Cached metadata for: {path.name} ({len(metadata)} tables)", level="INFO")
                return metadata
        except Exception as e:
            Logger.log(f"Failed to cache metadata {file_path}: {e}", level="ERROR")
            return {}

    @staticmethod
    def clear_cache():
        """Clears the metadata cache if project definitions change."""
        SchemaRegistry.get_metadata.cache_clear()
        Logger.log("Schema Registry cache cleared.", level="INFO")
