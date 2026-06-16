import os
import json
import re
from typing import List, Dict, Any, Optional
from src.core.models import Intent, CandidateColumn, ColumnMapping, Filter
from src.utils.llm import LLMService
from src.utils.logger import logger
from src.utils.prompt_loader import PromptLoader

class SchemaLinker:
    """Tier 3: Expert Mapper. Performs joint mapping of all intent components to schema."""
    def __init__(self):
        self.llm = LLMService()
        self.prompt_path = os.path.join(os.path.dirname(__file__), "schema_linker.yaml")

    def map(self, intent: Intent, candidates: List[CandidateColumn], external_knowledge: str = "", state: Any = None) -> List[ColumnMapping]:
        if not self.llm.enabled or not (intent.filters or intent.entities) or not candidates:
            return []

        logger.info(f"SchemaLinker: Jointly mapping intent against {len(candidates)} candidates.")
        
        # Deduplicate candidates
        unique_candidates = {c.fqn: c for c in candidates}
        candidate_list = list(unique_candidates.values())
        candidate_list.sort(key=lambda x: x.score, reverse=True)
        candidate_info = "\n".join([f"- {c.fqn} (type: {c.dtype}, samples: {c.sample_values})" for c in candidate_list[:150]])
        
        filter_info = "\n".join([f"- Filter: {f.field or 'unnamed'} {f.operator} {f.value}" for f in intent.flatten_filters()])
        entity_info = "\n".join([f"- Entity: {e}" for e in intent.entities])
        
        knowledge_str = f"EXTERNAL KNOWLEDGE:\n{external_knowledge}\n" if external_knowledge else ""

        try:
            messages = PromptLoader.load(self.prompt_path, variables={
                "query": intent.query,
                "knowledge": knowledge_str,
                "filters": filter_info,
                "entities": entity_info,
                "candidates": candidate_info
            })
            
            res = self.llm.get_completion(messages, state=state, agent_name="SchemaLinker")
            match = re.search(r"\{.*\}", res, re.DOTALL)
            if not match: return []
            
            data = json.loads(match.group(0))
            mappings = []
            for m_data in data.get("mappings", []):
                fqn = m_data.get("column")
                if fqn and fqn in unique_candidates:
                    mappings.append(ColumnMapping(
                        source_type=m_data.get("source_type"),
                        source_name=m_data.get("source_name"),
                        column=unique_candidates[fqn],
                        confidence=0.9
                    ))
            return mappings
        except Exception as e:
            logger.error(f"SchemaLinker failed: {e}")
            return []
