from typing import List, Dict
from src.utils.logger import logger

class JoinRanker:
    def __init__(self):
        self.memory_boosts: Dict[str, float] = {} # table_pair -> boost

    def rank(self, paths: List[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        if not paths:
            return []
            
        # For now, just return the shortest path
        # In a real system, we'd score based on:
        # 1. Path length (shorter is better)
        # 2. Memory boost (historical success)
        # 3. Table uniqueness
        
        sorted_paths = sorted(paths, key=len)
        return sorted_paths[0] if sorted_paths else []

    def update_memory(self, table_pair: str):
        self.memory_boosts[table_pair] = self.memory_boosts.get(table_pair, 0.0) + 1.0
