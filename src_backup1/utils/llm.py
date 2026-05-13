import json
import re
import os
import boto3
import inspect
from typing import List, Dict, Optional, Any
from botocore.config import Config
from dotenv import load_dotenv

# Import state and logger from src namespace
from src.core.models import ExecutionResult as AgentState
from src.utils.logger import logger as Logger

load_dotenv()

try:
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
    # Using the secret key as the Bearer token as per user implementation
    API_KEY = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
except ImportError:
    LANGCHAIN_AVAILABLE = False

class LLMService:
    """
    Unified LLM Service aligned with the user-provided proxy-aware implementation.
    Supports Bearer token authentication for Bedrock proxies.
    """
    _CLIENT_CACHE = {}

    def __init__(self, provider: str = None, model: str = None):
        self.model = model or os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b")
        self.is_bedrock = self.model.lower().startswith("bedrock/")
        self.client = None
        
        cache_key = ("bedrock" if self.is_bedrock else "openai", self.model)
        if cache_key in LLMService._CLIENT_CACHE:
             self.client = LLMService._CLIENT_CACHE[cache_key]
             if self.is_bedrock:
                 self.model_id = self.model.split("/", 1)[1] if "/" in self.model else self.model
             return

        if self.is_bedrock:
            self._init_bedrock_client()
        else:
            self._init_openai_client()
        
        if self.client:
             LLMService._CLIENT_CACHE[cache_key] = self.client

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _init_bedrock_client(self):
        if not LANGCHAIN_AVAILABLE:
            Logger.log("ERROR: langchain-aws or langchain-core not installed.", level="ERROR")
            self.client = None
            return

        try:
            self.model_id = self.model.split("/", 1)[1] if "/" in self.model else self.model
            
            # Explicitly load credentials to avoid fallback to standard AWS auth
            region = os.getenv("BEDROCK_REGION") or "us-east-1"
            
            # OSS Safeguard / Proxy auth pattern: Use Bearer token in headers
            headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            
            # Check for proxy endpoint (port 4000)
            base_url = os.getenv("LLM_API_BASE")
            
            self.client = ChatBedrockConverse(
                model_id=self.model_id,
                region_name=region,
                default_headers=headers,
                max_tokens=8000,
                temperature=0.0,
                # If proxy base URL is provided, we'd need a custom botocore endpoint 
                # but ChatBedrockConverse uses standard region-based discovery unless told otherwise.
            )
            Logger.log(f"Initialized ChatBedrockConverse for: {self.model_id}", level="INFO")
        except Exception as e:
            Logger.log(f"Failed to initialize ChatBedrockConverse client: {e}", level="ERROR")
            self.client = None

    def _init_openai_client(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            Logger.log(f"Initialized OpenAI SDK for: {self.model}", level="INFO")
        except Exception as e:
            Logger.log(f"Failed to initialize OpenAI client: {e}", level="ERROR")
            self.client = None

    def get_completion(self, 
                       messages: List[Dict[str, str]], 
                       temperature: float = 0.0, 
                       max_tokens: int = 8000,
                       state: Optional[AgentState] = None,
                       agent_name: str = "UNKNOWN") -> str:
        if not self.client:
            return "ERROR: LLM Client not initialized. Please check your credentials in .env"

        # Prepare prompt for logging
        prompt_log = ""
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            prompt_log += f"**[{role}]**:\n{content}\n\n"

        try:
            if self.is_bedrock:
                result = self._get_bedrock_completion(messages, temperature, max_tokens, state)
            else:
                result = self._get_openai_completion(messages, temperature, max_tokens, state)
            
            # Log with metrics if available in state
            metrics = None
            if state and hasattr(state, 'token_usage') and state.token_usage:
                # We want the tokens for THIS call, but state stores aggregate.
                # Since we don't have per-call tokens easily here without modifying _get_bedrock_completion,
                # let's just log the response.
                pass
            
            Logger.log_agent_block(agent_name, prompt_log, result)
            return result
        except Exception as e:
            error_msg = str(e)
            if "UnrecognizedClientException" in error_msg:
                 error_msg = "Bedrock Authentication Failed. Proxy keys rejected. Ensure BEDROCK_SECRET_ACCESS_KEY is set correctly."
            Logger.log(f"LLM Error: {error_msg}", level="ERROR")
            return f"ERROR: {error_msg}"

    def _get_bedrock_completion(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, state: Optional[AgentState] = None) -> str:
        system_content = []
        lc_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system_content.append(content)
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        if system_content and not lc_messages:
            lc_messages.append(HumanMessage(content="\n\n".join(system_content)))
        elif system_content and lc_messages:
            first_msg_content = lc_messages[0].content
            combined_content = "\n\n".join(system_content) + "\n\n" + first_msg_content
            lc_messages[0] = HumanMessage(content=combined_content)

        response = self.client.invoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Track usage
        try:
            meta = getattr(response, 'response_metadata', {})
            usage = meta.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            
            if input_tokens > 0 and state:
                if not hasattr(state, 'token_usage') or state.token_usage is None:
                    state.token_usage = {'input': 0, 'output': 0}
                state.token_usage['input'] += input_tokens
                state.token_usage['output'] += output_tokens
                if hasattr(state, 'llm_call_count'):
                    state.llm_call_count += 1
        except Exception:
            pass
        
        content = response.content
        if isinstance(content, list):
             content = "".join([b.get('text', '') if isinstance(b, dict) else str(b) for b in content])
             
        return str(content).strip()

    def _get_openai_completion(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, state: Optional[AgentState] = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        content = response.choices[0].message.content.strip()
        return content

    def _repair_json(self, json_str: str) -> str:
        """Fixes common LLM JSON errors like trailing commas."""
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
        # Fix missing quotes on keys (only if at start of line or after { to avoid matching inside strings)
        json_str = re.sub(r'([{\n]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
        return json_str

    def get_json_completion(self, 
                            messages: List[Dict[str, str]], 
                            state: Optional[AgentState] = None,
                            agent_name: str = "UNKNOWN") -> Any:
        # Pass state to get_completion for tracking
        content = self.get_completion(messages, state=state, agent_name=agent_name)
        if not content or content.startswith("ERROR:"):
            return None
        
        # Extract JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        clean_content = json_match.group(1).strip() if json_match else content.strip()
        
        try:
            return json.loads(self._repair_json(clean_content))
        except Exception:
            # Fallback re-search for brace
            try:
                start = clean_content.find('{')
                end = clean_content.rfind('}')
                if start != -1 and end != -1:
                    json_str = clean_content[start:end+1]
                    # Strip comments safely (look for // preceded by whitespace, avoid URLs)
                    json_str = re.sub(r'\s+//.*', '', json_str)
                    return json.loads(self._repair_json(json_str))
            except:
                pass
            Logger.log(f"JSON Parsing Failed for {agent_name}. Content: {content[:500]}...", level="ERROR")
            return None
