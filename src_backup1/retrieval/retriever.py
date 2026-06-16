import re
from typing import List, Dict, Any, Optional, Tuple
from src.core.models import Intent, CandidateColumn, Filter
from src.indexing.schema_indexer import SchemaIndexer
from src.utils.logger import logger

class Retriever:
    def __init__(self, indexer: SchemaIndexer, top_k: int = 150):
        self.indexer = indexer
        self.top_k = top_k
        self.memory_boosts: Dict[str, float] = {} # fqn -> boost

    def retrieve(self, intent: Intent) -> List[CandidateColumn]:
        # The new Indexer has a powerful search method that handles tokens, phrases, and values
        # We can run search for the raw query and individual components
        
        candidates: Dict[str, CandidateColumn] = {}
        
        # 1. Global Query Search
        global_results = self.indexer.search(intent.query, top_k=self.top_k)
        for col, score in global_results:
            self._add_or_update_candidate(candidates, col, score, "Global search")
            
        # 2. Component-specific Search (Boost)
        for filt in intent.flatten_filters():
            term = filt.field or str(filt.value)
            comp_results = self.indexer.search(term, top_k=20)
            for col, score in comp_results:
                self._add_or_update_candidate(candidates, col, score * 1.5, f"Filter search: {term}")
                
        for entity in intent.entities:
            ent_results = self.indexer.search(entity, top_k=20)
            for col, score in ent_results:
                self._add_or_update_candidate(candidates, col, score * 1.2, f"Entity search: {entity}")

        # 3. Apply memory boosts
        for fqn, boost in self.memory_boosts.items():
            if fqn in candidates:
                candidates[fqn].score += boost

        # Sort and return
        results = sorted(candidates.values(), key=lambda x: x.score, reverse=True)
        logger.info(f"Retrieved {len(results)} candidate columns.")
        return results[:self.top_k]

    def _add_or_update_candidate(self, candidates: Dict[str, CandidateColumn], col: CandidateColumn, weight: float, evidence: str):
        if col.fqn not in candidates:
            # We must be careful because col might be a Pydantic model now
            # but Indexer might have created it as a dict if unpickled? 
            # No, Indexer unpickles the objects.
            candidates[col.fqn] = col
            candidates[col.fqn].score = weight
            candidates[col.fqn].evidence = [evidence]
        else:
            candidates[col.fqn].score += weight
            if evidence not in candidates[col.fqn].evidence:
                candidates[col.fqn].evidence.append(evidence)

    def update_memory(self, fqns: List[str]):
        for fqn in fqns:
            self.memory_boosts[fqn] = self.memory_boosts.get(fqn, 0.0) + 1.0
