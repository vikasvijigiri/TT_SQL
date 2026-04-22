import os
import re
import json
import logging
from typing import List, Dict, Optional, Any
from tt_sql.core.logger import Logger
from tt_sql.core.config import get_settings

class LLMService:
    """
    Unified interface for calling LLMs (Bedrock).
    Provides consistent methods for text and JSON generation.
    """
    _CACHE = {}

    @classmethod
    def clear_cache(cls):
        cls._CACHE = {}

    def __init__(self, model: Optional[str] = None):
        settings = get_settings()
        self.model_name = model or settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        
        # Bedrock configuration
        self.aws_access_key = settings.BEDROCK_ACCESS_KEY
        self.aws_secret_key = settings.BEDROCK_SECRET_ACCESS_KEY
        self.aws_region = settings.BEDROCK_REGION
        
        self.enabled = bool(self.aws_access_key and self.aws_secret_key)
        if not self.enabled:
            Logger.log("Bedrock credentials missing. LLM service will be simulated.", level="WARN")

    def get_completion(self, 
                       messages: List[Dict[str, str]], 
                       max_tokens: int = 2000, 
                       state: Optional[Any] = None,
                       agent_name: str = "UNKNOWN") -> str:
        """Calls Bedrock with standardized message format."""
        if not self.enabled:
            return "SIMULATED_RESPONSE: LLM not configured."

        try:
            from langchain_aws import ChatBedrockConverse
            model_id = self.model_name
            
            # Logger context
            formatted_agent = f"LLM REQUEST: {agent_name.upper()}"
            Logger.log_stage_header(formatted_agent)

            llm = ChatBedrockConverse(
                model_id=model_id,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region,
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                base_url=get_settings().LLM_API_BASE
            )
            
            response = llm.invoke(messages)
            content = response.content
            
            # Simple caching for exact same prompt
            if state:
                state.token_usage["input"] += len(str(messages)) // 4
                state.token_usage["output"] += len(content) // 4
                
            return content

        except Exception as e:
            Logger.log(f"Error calling Bedrock: {e}", level="ERROR")
            return f"ERROR: {e}"

    def get_json_completion(self, 
                            messages: List[Dict[str, str]], 
                            state: Optional[Any] = None,
                            agent_name: str = "UNKNOWN") -> Any:
        """Helper to get and parse JSON response."""
        content = self.get_completion(messages, state=state, agent_name=agent_name)
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Any:
        """Parses JSON from LLM response with fallback for noise."""
        if not content or content.startswith("ERROR:"):
            return None
            
        try:
            # 1. Standard approach: Clean markdown code blocks
            clean = re.sub(r"```json\s*|```\s*", "", content).strip()
            return json.loads(clean)
        except Exception:
            # 2. Resilient approach: Extract first valid JSON object
            match = re.search(r"(\{.*\})", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception as e:
                    Logger.log(f"JSON extraction failed: {e}. Snippet: {content[:100]}", level="DEBUG")
            
            return None
