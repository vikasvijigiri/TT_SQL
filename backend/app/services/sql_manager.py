import os
import json
from pathlib import Path
from backend.app.core.config import MEMORY_DIR

class SQLManager:
    """Manages persistent caching of the best successful SQL for each instance."""
    def __init__(self):
        self.cache_dir = MEMORY_DIR / "sql_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_best_sql(self, instance_id: str) -> str:
        cache_file = self.cache_dir / f"{instance_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("sql", "")
            except: return ""
        return ""

    def cache_success(self, instance_id: str, sql: str, thought: str):
        cache_file = self.cache_dir / f"{instance_id}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                "sql": sql,
                "thought": thought,
                "version": "1.0"
            }, f, indent=2)

    def get_reference_context(self, instance_id: str) -> str:
        sql = self.get_best_sql(instance_id)
        if sql:
            return f"REFERENCE_SQL (Previous Success):\n{sql}\nUse this as an anchor for refinement."
        return "No previous success cached."
