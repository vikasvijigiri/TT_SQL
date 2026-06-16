import os
import re
import json
from typing import List, Optional, Any, Dict
from src.core.models import Intent, Condition, ConditionGroup, MappingCandidate, Source, Select, Aggregation
from src.utils.llm import LLMService
from src.utils.logger import logger
from src.utils.prompt_loader import PromptLoader
from src.intent.postprocess import validate_and_fix_intent

class IntentAnalyzer:
    """
    Advanced Intent Analyzer:
    - Uses a comprehensive schema for deep Text2SQL intent extraction.
    - LLM-driven with prompts loaded from YAML.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService()
        self.prompt_path = os.path.join(os.path.dirname(__file__), "intent_analyzer.yaml")

    def analyze(self, query: str, external_knowledge: str = "") -> Intent:
        query_clean = self._clean(query)
        logger.info(f"Analyzing intent for: {query_clean}")
        
        intent_dict = self._llm_analyze(query_clean, external_knowledge=external_knowledge)
        
        if not intent_dict:
            logger.warning("LLM intent analysis failed. Using minimal fallback.")
            return Intent(
                query=query_clean,
                intent_type="unknown",
                complexity="low",
                confidence=0.1
            )

        # Post-process for strict fidelity
        intent_dict = validate_and_fix_intent(intent_dict, query_clean)
        logger.debug(f"Pre-validation Intent Dict: {json.dumps(intent_dict, indent=2)}")

        # Map the dictionary to our Pydantic model
        try:
            intent_dict["query"] = query_clean
            intent = Intent.model_validate(intent_dict)
            return intent
        except Exception as e:
            logger.error(f"Failed to validate Intent model: {e}")
            return Intent(
                query=query_clean,
                intent_type="unknown",
                complexity="low",
                confidence=0.1
            )

    def _clean(self, query: str) -> str:
        query = query.strip()
        query = query.replace("“", '"').replace("”", '"')
        query = query.replace("‘", "'").replace("’", "'")
        query = re.sub(r"\s+", " ", query)
        return query

    def _llm_analyze(self, query: str, external_knowledge: str = "") -> Optional[Dict]:
        try:
            # We don't have SCHEMA here yet, so we pass empty or partial
            messages = PromptLoader.load(self.prompt_path, variables={
                "USER_QUERY": query,
                "SCHEMA": "Not provided at this stage",
                "EXTERNAL_KNOWLEDGE": external_knowledge
            })
            
            res = self.llm.get_completion(messages, agent_name="IntentAnalyzer")
            match = re.search(r"\{.*\}", res, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.error(f"LLM Intent Analysis failed: {e}")
        return None