from typing import List, Dict, Optional, Any
import os
import json
import boto3
import inspect
import re
from app.schemas.agent_state import AgentState
from app.core.logger import Logger
from app.core.settings import settings

try:
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

class LLMService:
    """
    Service to handle interactions strictly with Amazon Bedrock using ChatBedrockConverse.
    """
    # Class-level cache for LLM clients
    _CLIENT_CACHE = {} # (model_id) -> client instance

    def __init__(self, model: str = None, config_override: Optional[Dict[str, Any]] = None, **kwargs):
        # Load configs from override or global settings
        self.config = config_override or {}
        
        # Default to settings if not provided
        self.model = model or self.config.get("llm_model") or settings.LLM_MODEL or "anthropic.claude-3-sonnet-20240229-v1:0"
        
        # Strip 'bedrock/' prefix if present for internal model_id
        self.model_id = self.model.split("/", 1)[1] if "/" in str(self.model) else self.model
        
        self.client = None
        self.bedrock_agent_runtime = None
        
        # Cache key based on model and credentials
        cache_key = (self.model_id, json.dumps(self.config, sort_keys=True) if self.config else "global")
        
        if cache_key in LLMService._CLIENT_CACHE:
            self.client = LLMService._CLIENT_CACHE[cache_key]
        else:
            self._init_bedrock_client()
            if self.client:
                LLMService._CLIENT_CACHE[cache_key] = self.client

    def _init_bedrock_client(self):
        if not LANGCHAIN_AVAILABLE:
            Logger.log("ERROR: langchain-aws or langchain-core not installed.", level="ERROR")
            return

        try:
            # Get credentials from override or settings
            region = self.config.get("bedrock_region") or settings.BEDROCK_REGION or "us-east-1"
            secret_key = self.config.get("bedrock_secret_key") or settings.BEDROCK_SECRET_ACCESS_KEY
            access_key = self.config.get("bedrock_access_key") or settings.BEDROCK_ACCESS_KEY_ID

            # Initialize ChatBedrockConverse
            self.client = ChatBedrockConverse(
                model_id=self.model_id,
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                max_tokens=4000,
                temperature=0.0,
            )
            Logger.log(f"Initialized Bedrock client: {self.model_id} ({region})", level="INFO")
        except Exception as e:
            Logger.log(f"Failed to initialize Bedrock client: {e}", level="ERROR")
            self.client = None

    def _init_bedrock_agent_runtime(self):
        try:
            self.bedrock_agent_runtime = boto3.client(
                service_name='bedrock-agent-runtime',
                region_name=self.config.get("bedrock_region") or settings.BEDROCK_REGION or "us-east-1",
                aws_access_key_id=self.config.get("bedrock_access_key") or settings.BEDROCK_ACCESS_KEY_ID,
                aws_secret_access_key=self.config.get("bedrock_secret_key") or settings.BEDROCK_SECRET_ACCESS_KEY
            )
        except Exception as e:
            Logger.log(f"Failed to initialize Bedrock Agent Runtime: {e}", level="ERROR")
            self.bedrock_agent_runtime = None

    def retrieve_from_kb(self, kb_id: str, query: str, max_results: int = 5) -> List[str]:
        """Retrieve context from Bedrock Knowledge Base."""
        if not self.bedrock_agent_runtime:
            self._init_bedrock_agent_runtime()
            
        if not self.bedrock_agent_runtime:
             return []
             
        try:
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': max_results}}
            )
            results = [r.get('content', {}).get('text', '') for r in response.get('retrievalResults', [])]
            return [r for r in results if r]
        except Exception as e:
            Logger.log(f"KB Retrieval Failed: {e}", level="ERROR")
            return []

    def get_completion(self, 
                       messages: List[Dict[str, str]], 
                       temperature: float = 0.0, 
                       max_tokens: int = 8000,
                       state: Optional[AgentState] = None,
                       agent_name: str = None) -> str:
        if not self.client:
            return "ERROR: Bedrock client not initialized. Check credentials."

        # Log prompt
        try:
            caller = agent_name or "Agent"
            log_msg = f"\n--- {caller.upper()} PROMPT ---\n"
            for m in messages:
                log_msg += f"**[{m.get('role', 'user').upper()}]**:\n{m.get('content', '')}\n\n"
            Logger.log(log_msg, level="DEBUG")
        except: pass

        try:
            # Map messages for LangChain
            lc_messages = []
            system_msg = ""
            for m in messages:
                role, content = m.get("role"), m.get("content")
                if role == "system": system_msg = content
                elif role == "assistant": lc_messages.append(AIMessage(content=content))
                else: lc_messages.append(HumanMessage(content=content))

            if system_msg:
                # ChatBedrockConverse handles system messages if prepended or passed correctly
                lc_messages.insert(0, SystemMessage(content=system_msg))

            response = self.client.invoke(lc_messages, temperature=temperature, max_tokens=max_tokens)
            
            # Track Usage
            try:
                usage = getattr(response, "response_metadata", {}).get("usage", {})
                self._track_usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0), state)
            except: pass

            return str(response.content).strip()
        except Exception as e:
            msg = str(e)
            Logger.log(f"Bedrock Error: {msg}", level="ERROR")
            return f"ERROR: {msg}"

    def get_completion_stream(self, messages: List[Dict[str, str]], **kwargs):
        """Streams tokens from Bedrock."""
        if not self.client:
            yield "ERROR: Client not initialized."
            return

        lc_messages = []
        for m in messages:
            role, content = m.get("role"), m.get("content")
            if role == "system": lc_messages.append(SystemMessage(content=content))
            elif role == "assistant": lc_messages.append(AIMessage(content=content))
            else: lc_messages.append(HumanMessage(content=content))

        try:
            for chunk in self.client.stream(lc_messages):
                yield chunk.content if hasattr(chunk, "content") else str(chunk)
        except Exception as e:
            Logger.log(f"Stream Failed: {e}", level="ERROR")
            yield ""

    def _track_usage(self, input_tokens: int, output_tokens: int, state: Optional[AgentState] = None):
        if state and hasattr(state, 'token_usage'):
            state.token_usage['input'] += input_tokens
            state.token_usage['output'] += output_tokens

    def get_json_completion(self, messages: List[Dict[str, str]], state: Optional[AgentState] = None, **kwargs) -> Any:
        content = self.get_completion(messages, state=state, **kwargs)
        if state: state.last_raw_response = content
        if content.startswith("ERROR:"): return None
        return self._parse_json_response(content)
    
    def _parse_json_response(self, content: str) -> Any:
        raw = content.strip()
        # SQL block extraction
        sql_match = re.search(r'```sql\s*([\s\S]*?)```', raw, re.IGNORECASE)
        if sql_match:
            sql = sql_match.group(1).strip()
            return {"sql": sql, "approach": "recovered_raw_sql"}

        # JSON block extraction
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        
        try:
            return json.loads(content)
        except:
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                try: return json.loads(json_match.group())
                except: pass
        
        Logger.log(f"JSON Parse Failure: {content[:50]}...", level="ERROR")
        return None

    def cleanup(self):
        self.client = None
