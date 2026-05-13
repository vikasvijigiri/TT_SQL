import os
import json
import hashlib
from typing import Dict, Any, Optional
from src.utils.logger import logger

class CacheManager:
    """
    Manages persistent caching of validated plans and SQL results.
    """
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self.index_path = os.path.join(self.cache_dir, "cache_index.json")
        self.index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_index(self):
        with open(self.index_path, "w") as f:
            json.dump(self.index, f, indent=2)

    def _get_key(self, question: str, db_name: str, schema_str: str) -> str:
        # Create a unique key based on question, db, and schema structure
        combined = f"{question}|{db_name}|{schema_str}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_pruned_schema(self, question: str, db_name: str, schema_str: str) -> Optional[tuple]:
        key = self._get_key(question, db_name, schema_str)
        if key in self.index and "pruned_schema" in self.index[key]:
            logger.info(f"[CACHE HIT] Loading pruned schema for: {question[:50]}...")
            data = self.index[key]["pruned_schema"]
            return data["schema"], data["reasoning"]
        return None

    def get_plan(self, question: str, db_name: str, schema_str: str) -> Optional[Dict[str, Any]]:
        key = self._get_key(question, db_name, schema_str)
        if key in self.index and "plan" in self.index[key]:
            logger.info(f"[CACHE HIT] Loading validated plan for: {question[:50]}...")
            return self.index[key]["plan"]
        return None

    def get_sql(self, question: str, db_name: str, schema_str: str) -> Optional[str]:
        key = self._get_key(question, db_name, schema_str)
        if key in self.index and "sql" in self.index[key]:
            logger.info(f"[CACHE HIT] Loading validated SQL for: {question[:50]}...")
            return self.index[key]["sql"]
        return None

    def save(self, question: str, db_name: str, schema_str: str, plan: Dict[str, Any] = None, sql: str = None, pruned_schema: tuple = None):
        key = self._get_key(question, db_name, schema_str)
        if key not in self.index:
            self.index[key] = {"question": question, "db": db_name}
        
        if plan:
            self.index[key]["plan"] = plan
        if sql:
            self.index[key]["sql"] = sql
        if pruned_schema:
            self.index[key]["pruned_schema"] = {
                "schema": pruned_schema[0],
                "reasoning": pruned_schema[1]
            }
            
        self._save_index()
        logger.info(f"[CACHE] Result persisted for: {question[:50]}...")
