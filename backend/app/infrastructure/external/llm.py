import json
import re
from typing import List, Dict, Optional, Any
from app.core.config.settings import settings
from app.core.logging.logger import Logger

try:
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

class LLMService:
    """
    Infrastructure layer service for interacting with Amazon Bedrock.
    Utilizes LangChain's ChatBedrockConverse for unified AWS integration.
    """
    _CLIENT_CACHE = {}

    def __init__(self, model: str = None, config_override: Optional[Dict[str, Any]] = None):
        self.config = config_override or {}
        self.model_name = model or self.config.get("llm_model") or settings.LLM_MODEL
        self.model_id = self.model_name.split("/", 1)[1] if "/" in str(self.model_name) else self.model_name
        
        cache_key = (self.model_id, json.dumps(self.config, sort_keys=True) if self.config else "global")
        self.client = self._CLIENT_CACHE.get(cache_key) or self._init_client(cache_key)

    def _init_client(self, cache_key: tuple):
        if not LANGCHAIN_AVAILABLE:
            Logger.log("Critical: LangChain dependencies missing.", level="ERROR")
            return None
            
        try:
            region = self.config.get("bedrock_region") or settings.BEDROCK_REGION or "us-east-1"
            client = ChatBedrockConverse(
                model_id=self.model_id,
                region_name=region,
                aws_access_key_id=self.config.get("bedrock_access_key") or settings.BEDROCK_ACCESS_KEY_ID,
                aws_secret_access_key=self.config.get("bedrock_secret_key") or settings.BEDROCK_SECRET_ACCESS_KEY,
                max_tokens=4000,
                temperature=0.0,
            )
            self._CLIENT_CACHE[cache_key] = client
            return client
        except Exception as e:
            Logger.log(f"Bedrock Init Failed: {e}", level="ERROR")
            return None

    def get_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.client: return "ERROR: Client not initialized."
        
        try:
            lc_msgs = []
            for m in messages:
                role, content = m["role"], m["content"]
                if role == "system": lc_msgs.insert(0, SystemMessage(content=content))
                elif role == "assistant": lc_msgs.append(AIMessage(content=content))
                else: lc_msgs.append(HumanMessage(content=content))

            response = self.client.invoke(lc_msgs, **kwargs)
            return str(response.content).strip()
        except Exception as e:
            Logger.log(f"LLM Invocation Error: {e}", level="ERROR")
            return f"ERROR: {e}"

    def get_json_completion(self, messages: List[Dict[str, str]], **kwargs) -> Optional[Dict[str, Any]]:
        content = self.get_completion(messages, **kwargs)
        if content.startswith("ERROR:"): return None
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            # Match JSON block or try raw parse
            match = re.search(r'```json\s*([\s\S]*?)```', content)
            raw = match.group(1) if match else content
            return json.loads(raw)
        except:
            # Fallback to regex for inner braces
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try: return json.loads(match.group())
                except: pass
        return None
