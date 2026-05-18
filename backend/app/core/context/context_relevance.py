import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from backend.app.utils.logger import logger

class ComponentScore(BaseModel):
    component_name: str
    query_overlap: float = 0.0
    keyword_relevance: float = 0.0
    structural_necessity: float = 0.0
    composite_score: float = 0.0
    is_retained: bool = True
    rejection_reason: str = ""

class ContextRelevanceScorer:
    """
    Enterprise Context Relevance Auditing Engine.
    Evaluates individual prompt components (schema tables, rule blocks, example snippets)
    across query overlap, domain keywords, and structural necessity before prompt assembly.
    Blocks below the configured minimum threshold are marked for exclusion.
    """
    
    DOMAIN_KEYWORDS = {
        "geospatial": ["area", "distance", "boundary", "region", "polygon", "st_", "geo", "latitude", "longitude"],
        "variant": ["genotype", "variant", "allele", "vcf", "json", "nested", "call", "path", "flatten", "lateral"],
        "temporal": ["date", "time", "year", "month", "day", "epoch", "interval", "between", "timestamp"],
        "aggregation": ["sum", "avg", "count", "max", "min", "average", "total", "percentage", "ratio"]
    }

    def __init__(self, min_threshold: float = 0.20):
        self.min_threshold = min_threshold

    def _compute_query_overlap(self, query: str, content: str) -> float:
        q_tokens = set(re.findall(r'\w+', query.lower()))
        if not q_tokens or not content:
            return 0.0
        c_tokens = set(re.findall(r'\w+', content.lower()))
        if not c_tokens:
            return 0.0
        overlap = len(q_tokens.intersection(c_tokens))
        return min(1.0, overlap / max(1, len(q_tokens)))

    def _compute_keyword_relevance(self, query: str, content: str) -> float:
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Determine active domains in query
        active_domains = [domain for domain, kws in self.DOMAIN_KEYWORDS.items() if any(kw in query_lower for kw in kws)]
        if not active_domains:
            return 0.5 # Neutral baseline if no specific domain triggers
            
        score = 0.0
        for domain in active_domains:
            kws = self.DOMAIN_KEYWORDS[domain]
            if any(kw in content_lower for kw in kws):
                score += 1.0
                
        return min(1.0, score / len(active_domains))

    def score_component(self, name: str, content: str, user_query: str, is_mandatory: bool = False, baseline_necessity: float = 0.5) -> ComponentScore:
        """Scores a single prompt component across multiple relevance dimensions."""
        if is_mandatory:
            return ComponentScore(
                component_name=name,
                query_overlap=1.0,
                keyword_relevance=1.0,
                structural_necessity=1.0,
                composite_score=1.0,
                is_retained=True,
                rejection_reason="Mandatory component"
            )

        q_overlap = self._compute_query_overlap(user_query, content)
        kw_rel = self._compute_keyword_relevance(user_query, content)
        struct = baseline_necessity

        # Composite formula weighting query overlap heavily, supported by domain keywords
        comp = (q_overlap * 0.5) + (kw_rel * 0.3) + (struct * 0.2)
        comp = round(min(1.0, max(0.0, comp)), 3)

        retained = comp >= self.min_threshold
        reason = f"Composite score {comp} below minimum threshold {self.min_threshold}." if not retained else ""

        if not retained:
            logger.debug(f"[ContextRelevanceScorer] Component '{name}' flagged for exclusion (Score: {comp}).")

        return ComponentScore(
            component_name=name,
            query_overlap=round(q_overlap, 3),
            keyword_relevance=round(kw_rel, 3),
            structural_necessity=round(struct, 3),
            composite_score=comp,
            is_retained=retained,
            rejection_reason=reason
        )

    def filter_components(self, components: Dict[str, str], user_query: str, mandatory_names: List[str] = None) -> Dict[str, str]:
        """
        Takes a map of component name -> content and returns only those that pass relevance scoring.
        """
        mandatory_names = mandatory_names or []
        retained = {}
        
        for name, content in components.items():
            is_man = name in mandatory_names
            score = self.score_component(name, content, user_query, is_mandatory=is_man)
            if score.is_retained:
                retained[name] = content
                
        return retained
