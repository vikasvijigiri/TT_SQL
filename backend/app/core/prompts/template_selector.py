from typing import List, Dict, Any, Optional
from backend.app.core.retrieval.hierarchical_retriever import QueryIntentAnalysis
from backend.app.utils.logger import logger

class TemplateSelector:
    """
    Enterprise Query-Aware Template Selector.
    Analyzes query intent (window functions, lateral flatten, geospatial, aggregations)
    and retrieves only the required SQL syntax templates, preventing prompt bloat from irrelevant examples.
    """
    
    @classmethod
    def select_templates(cls, raw_templates: List[Dict[str, str]], intent: QueryIntentAnalysis, max_templates: int = 2) -> List[Dict[str, str]]:
        """
        Filters raw SQL templates based on query intent matching.
        """
        if not raw_templates:
            return []

        selected = []
        
        for tmpl in raw_templates:
            name = tmpl.get("name", "").lower()
            sql = tmpl.get("sql", "").lower()
            
            # Check if template is specific to a domain
            is_var = "flatten" in name or "variant" in name or "lateral flatten" in sql or "parse_json" in sql
            is_win = "window" in name or "deduplication" in name or "row_number()" in sql or "over(" in sql
            is_geo = "geo" in name or "spatial" in name or "st_" in sql
            
            # Match against query intent
            if is_var and not intent.requires_variant_expansion:
                continue
            if is_win and not (intent.target_metrics and any(kw in str(intent.target_metrics).lower() for kw in ("rank", "row_number", "over", "lead", "lag"))):
                continue
            if is_geo and not intent.requires_geospatial:
                continue
                
            selected.append(tmpl)
            if len(selected) >= max_templates:
                break
                
        # If no specific templates matched but we have general analytical templates, include at most 1 baseline template
        if not selected and raw_templates:
            for tmpl in raw_templates:
                name = tmpl.get("name", "").lower()
                if "standard analytical" in name or "cte" in name:
                    selected.append(tmpl)
                    break
            if not selected:
                selected.append(raw_templates[0])

        logger.debug(f"[TemplateSelector] Selected {len(selected)} query-aware templates out of {len(raw_templates)} candidate templates.")
        return selected

    @classmethod
    def format_templates(cls, templates: List[Dict[str, str]]) -> str:
        """Formats selected templates as markdown."""
        if not templates:
            return ""
        out = "=== RELEVANT SQL SYNTAX TEMPLATES ===\n"
        for t in templates:
            name = t.get("name", "Template")
            sql = t.get("sql", "").strip()
            out += f"\n--- [Template] {name} ---\n```sql\n{sql}\n```\n"
        return out
