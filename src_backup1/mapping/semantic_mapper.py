import re
from typing import List, Optional, Any
from sentence_transformers import SentenceTransformer, util
from src.core.models import Intent, CandidateColumn, ColumnMapping, Filter
from src.utils.logger import logger
from src.utils.llm import LLMService

class SemanticMapper:
    """Tier 1: Fast Path Mapper. Uses SentenceTransformers for semantic similarity."""
    _model = None

    def __init__(self, threshold: float = 0.35):
        self.threshold = threshold
        self.llm = LLMService()
        if SemanticMapper._model is None:
            logger.info("Loading SentenceTransformer (all-MiniLM-L6-v2)...")
            SemanticMapper._model = SentenceTransformer('all-MiniLM-L6-v2')

    def map(self, intent: Intent, candidates: List[CandidateColumn], state: Any = None, external_knowledge: str = "") -> List[ColumnMapping]:
        if not candidates:
            return []
            
        mappings = []
        
        # 1. Map Filters
        for filt in intent.flatten_filters():
            mapping = self._map_source(filt.field or str(filt.value), "filter", filt, candidates, state, external_knowledge)
            if mapping:
                mappings.append(mapping)
                
        # 2. Map Entities
        for entity in intent.entities:
            mapping = self._map_source(entity, "entity", None, candidates, state, external_knowledge)
            if mapping:
                mappings.append(mapping)
                
        logger.info(f"Tier 1 Semantic Mapping: Produced {len(mappings)} mappings.")
        return mappings

    def _map_source(self, text: str, source_type: str, source_obj: Optional[Filter], candidates: List[CandidateColumn], state: Any, external_knowledge: str) -> Optional[ColumnMapping]:
        # Pre-compute identity strings for candidates
        col_texts = [f"{c.table} {c.column} {c.description} {' '.join(c.sample_values)}" for c in candidates]
        col_embeddings = SemanticMapper._model.encode(col_texts, convert_to_tensor=True)
        
        # Expand term
        expanded_terms = [text]
        if self.llm.enabled:
            expansion_prompt = f"List 5-8 technical column names or medical synonyms for '{text}' in a Snowflake DICOM/TCGA database. Return only a comma-separated list."
            res = self.llm.get_completion([{"role": "user", "content": expansion_prompt}], agent_name="Expansion").strip()
            if res and "ERROR" not in res:
                expanded_terms.extend([t.strip().strip('"') for t in res.split(',')])
        
        term_embeddings = SemanticMapper._model.encode(expanded_terms, convert_to_tensor=True)
        source_embedding = term_embeddings.mean(dim=0)
        
        # Compute cosine similarities
        cos_scores = util.cos_sim(source_embedding, col_embeddings)[0]
        
        best_col = None
        max_final_score = -1.0
        
        for i, col in enumerate(candidates):
            semantic_score = float(cos_scores[i])
            keyword_score = 0.0
            if text.lower() in col.column.lower(): keyword_score += 0.3
            
            final_score = semantic_score + keyword_score
            if final_score > max_final_score:
                max_final_score = final_score
                best_col = col

        # LLM Re-ranking if ambiguous
        if self.llm.enabled and max_final_score < 0.7:
            llm_col = self._rerank_with_llm(text, source_type, source_obj, candidates[:30], state, external_knowledge)
            if llm_col:
                best_col = llm_col
                max_final_score = 0.9

        if best_col and max_final_score >= self.threshold:
            return ColumnMapping(
                source_type=source_type,
                source_name=text,
                column=best_col,
                confidence=min(max_final_score, 1.0)
            )
        return None

    def _rerank_with_llm(self, text: str, source_type: str, source_obj: Optional[Filter], candidates: List[CandidateColumn], state: Any, external_knowledge: str) -> Optional[CandidateColumn]:
        candidate_info = "\n".join([f"- {c.fqn} (type: {c.dtype}, samples: {c.sample_values})" for c in candidates])
        prompt = f"""
        Map the medical concept '{text}' ({source_type}) to the most relevant database column.
        
        CANDIDATE COLUMNS:
        {candidate_info}
        
        Return ONLY the FQN (Table.Column) of the best match or "NONE".
        """
        res = self.llm.get_completion([{"role": "user", "content": prompt}], state=state, agent_name="SemanticMapper").strip()
        for c in candidates:
            if c.fqn.lower() in res.lower():
                return c
        return None
