import json
import os
from typing import List, Dict, Any
from src.core.models import ColumnMapping, ExecutionResult
from src.utils.logger import logger

class Memory:
    def __init__(self, path: str = "memory.json"):
        self.path = path
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"success_mappings": {}, "successful_queries": []}

    def update(self, query: str, mappings: List[ColumnMapping]):
        self.data["successful_queries"].append({
            "query": query,
            "mappings": [m.model_dump() for m in mappings]
        })
        
        # Boost individual mappings
        for m in mappings:
            fqn = m.column.fqn
            self.data["success_mappings"][fqn] = self.data["success_mappings"].get(fqn, 0) + 1
            
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)
        logger.info("Memory updated.")
