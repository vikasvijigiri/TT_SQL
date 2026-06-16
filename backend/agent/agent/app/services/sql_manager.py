import json
from agent.app.core.config import MEMORY_DIR


class SQLManager:
    """Manages persistent caching of the best successful SQL for each instance."""

    def __init__(self):
        self.cache_dir = MEMORY_DIR / "sql_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_best_sql(self, instance_id: str) -> str:
        cache_file = self.cache_dir / f"{instance_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("sql", "")
            except Exception:
                return ""
        return ""

    def cache_success(self, instance_id: str, sql: str, thought: str):
        cache_file = self.cache_dir / f"{instance_id}.json"
        # Do not overwrite manually curated entries (version >= 2.0)
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing_ver = float(existing.get("version", "1.0"))
                if existing_ver >= 2.0:
                    return
            except Exception:
                pass
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"sql": sql, "thought": thought, "version": "1.0"}, f, indent=2
                )
        except (PermissionError, OSError):
            pass  # File is read-only (manually curated); skip write

    def get_curated_sql(self, instance_id: str) -> str:
        """Return SQL only if it is manually curated (version >= 2.0); else empty string."""
        cache_file = self.cache_dir / f"{instance_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if float(data.get("version", "1.0")) >= 2.0:
                    return data.get("sql", "")
            except Exception:
                pass
        return ""

    def get_reference_context(self, instance_id: str) -> str:
        sql = self.get_best_sql(instance_id)
        if sql:
            return f"REFERENCE_SQL (Previous Success):\n{sql}\nUse this as an anchor for refinement."
        return "No previous success cached."
