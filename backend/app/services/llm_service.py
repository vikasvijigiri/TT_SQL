from typing import List, Dict, Optional, Any
import os
import json
from openai import OpenAI
import re
from app.models.agent_state import AgentState
from app.services.logger import Logger
from dotenv import load_dotenv

from app.models.config import settings

# LangChain removed to fix Pydantic v1 conflicts

class LLMService:
    """
    Service to handle interactions with Large Language Models using official SDKs.
    Supports Amazon Bedrock (Direct via Boto3) and OpenAI.
    """
    # Class-level cache for LLM clients
    _CLIENT_CACHE = {} # (provider, model_id) -> client instance

    def __init__(self, provider: str = None, model: str = None):
        # Load configs from settings
        self.model = model or settings.LLM_MODEL or "gpt-3.5-turbo"
        
        # Determine if we are using Bedrock
        self.is_bedrock = str(self.model).lower().startswith("bedrock/")
        
        self.client = None
        
        # Check cache
        cache_key = ("bedrock" if self.is_bedrock else "openai", self.model)
        if cache_key in LLMService._CLIENT_CACHE:
             self.client = LLMService._CLIENT_CACHE[cache_key]
             if self.is_bedrock:
                 self.model_id = self.model.split("/", 1)[1] if "/" in self.model else self.model
             return

        # Initialize and Cache
        if self.is_bedrock:
            self._init_bedrock_client()
        else:
            self._init_openai_client()
        
        if self.client:
             LLMService._CLIENT_CACHE[cache_key] = self.client

    def _init_bedrock_client(self):
        try:
            from langchain_aws import ChatBedrockConverse
            
            # Strip prefix (e.g. 'bedrock/anthropic...' -> 'anthropic...')
            self.model_id = self.model.split("/", 1)[1] if "/" in self.model else self.model

            endpoint_url = settings.LLM_API_BASE
            api_key = settings.BEDROCK_SECRET_ACCESS_KEY or settings.BEDROCK_ACCESS_KEY_ID
            region = settings.BEDROCK_REGION
            
            kwargs = {
                "model_id": self.model_id,
                "region_name": region,
            }
            if endpoint_url:
                kwargs["endpoint_url"] = endpoint_url
                Logger.log(f"Using custom Bedrock endpoint: {endpoint_url}", level="INFO")
            if api_key:
                kwargs["default_headers"] = {"Authorization": f"Bearer {api_key}"}
                
            self.client = ChatBedrockConverse(**kwargs)
            Logger.log(f"Initialized ChatBedrockConverse Client for: {self.model_id}", level="INFO")
        except Exception as e:
            Logger.log(f"Failed to initialize ChatBedrockConverse client: {type(e).__name__}: {e}", level="ERROR")
            self.client = None

    def _init_openai_client(self):
        try:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            Logger.log(f"Initialized OpenAI SDK for: {self.model}", level="INFO")
        except Exception as e:
            Logger.log(f"Failed to initialize OpenAI client: {type(e).__name__}: {e}", level="ERROR")
            self.client = None


    def get_completion(self, 
                       messages: List[Dict[str, str]], 
                       temperature: float = 0.0, 
                       max_tokens: int = 3000,  # B3: was 8000 — reduced to lower API wait time
                       state: Optional[AgentState] = None,
                       agent_name: str = None) -> str:  # B1: accept name directly, no inspect.stack()
        if not self.client:
            return "ERROR: LLM Client not initialized. Please check your credentials in .env"

        # B1: Log prompt with provided agent_name — no more call stack walk
        if agent_name:
            try:
                log_content = f"\n--- {agent_name.upper()} PROMPT ---\n"
                for msg in messages:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    log_content += f"**[{role}]**:\n{content}\n\n"
                log_content += "----------------\n"
                Logger.log(log_content, level="DEBUG")
            except Exception:
                pass

        try:
            if self.is_bedrock:
                return self._get_bedrock_completion(messages, temperature, max_tokens, state)
            else:
                return self._get_openai_completion(messages, temperature, max_tokens, state)
        except Exception as e:
            error_msg = str(e)
            if "UnrecognizedClientException" in error_msg:
                 return f"ERROR: Bedrock Authentication Failed. If you are using a proxy (like on port 4000), please ensure LLM_API_BASE is set in .env to the correct endpoint URL."
            Logger.log(f"LLM Error: {error_msg}", level="ERROR")
            return f"ERROR: {error_msg}"

    def _track_usage(self, input_tokens: int, output_tokens: int, state: Optional[AgentState] = None):
        """Helper to update state with token usage."""
        if state and hasattr(state, 'token_usage'):
            state.token_usage['input'] += input_tokens
            state.token_usage['output'] += output_tokens

    def _get_bedrock_completion(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, state: Optional[AgentState] = None) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        
        lc_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        response = self.client.invoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract token usage
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            
            Logger.log(f"📊 Token Usage - Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens}", level="INFO")
            self._track_usage(input_tokens, output_tokens, state)

        content = response.content
        if isinstance(content, list):
            text_blocks = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
            if not text_blocks:
                content_str = str(content)
            else:
                content_str = "".join(text_blocks)
        else:
            content_str = str(content)
            
        return content_str.strip()

    def get_completion_stream(self, 
                              messages: List[Dict[str, str]], 
                              temperature: float = 0.0, 
                              max_tokens: int = 3000,
                              agent_name: str = None):  # B1: accept name
        """Yields completion tokens."""
        if not self.client:
            yield "ERROR: LLM Client not initialized."
            return

        # B1: Log prompt with provided agent_name
        if agent_name:
            try:
                log_content = f"\n--- {agent_name.upper()} PROMPT (STREAM) ---\n"
                for msg in messages:
                    role = msg.get("role", "unknown").upper()
                    content = msg.get("content", "")
                    log_content += f"**[{role}]**:\n{content}\n\n"
                log_content += "----------------\n"
                Logger.log(log_content, level="DEBUG")
            except Exception:
                pass

        try:
            if self.is_bedrock:
                from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
                lc_messages = []
                for msg in messages:
                    role = msg.get("role")
                    content = msg.get("content")
                    if role == "system":
                        lc_messages.append(SystemMessage(content=content))
                    elif role == "user":
                        lc_messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        lc_messages.append(AIMessage(content=content))

                # Use langchain_aws ChatBedrockConverse stream
                for chunk in self.client.stream(lc_messages, temperature=temperature, max_tokens=max_tokens):
                    if hasattr(chunk, 'content'):
                        if isinstance(chunk.content, list):
                            for item in chunk.content:
                                if isinstance(item, dict) and "text" in item:
                                    yield item["text"]
                                elif hasattr(item, 'text'):
                                    yield item.text
                                elif isinstance(item, str):
                                    yield item
                        elif isinstance(chunk.content, str):
                            yield chunk.content
            else:
                yield from self._get_openai_stream(messages, temperature, max_tokens)
        except Exception as e:
            error_msg = str(e)
            Logger.log(f"LLM Stream Error: {error_msg}", level="ERROR")
            yield f"ERROR: {error_msg}"

    def _get_openai_stream(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    def _get_openai_completion(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, state: Optional[AgentState] = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract and log token usage
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            Logger.log(
                f"📊 Token Usage - Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens} | Max: {max_tokens}",
                level="INFO"
            )
            self._track_usage(input_tokens, output_tokens, state)
        
        return response.choices[0].message.content.strip()

    def cleanup(self):
        self.client = None

    def get_json_completion(self, 
                            messages: List[Dict[str, str]], 
                            state: Optional[AgentState] = None,
                            agent_name: str = None) -> Any:
        # Pass name to get_completion for tracking
        content = self.get_completion(messages, state=state, agent_name=agent_name)
        if state:
            state.last_raw_response = content
        
        if content.startswith("ERROR:"):
            return None
        
        return self._parse_json_response(content)
    
    def _parse_json_response(self, content: str) -> Any:
        raw_content = content.strip()
        
        # Simple JSON extraction logic for SQL agents
        # Use re.search instead of re.match to find the block anywhere in the text
        sql_match = re.search(r'```sql\s*([\s\S]*?)```', raw_content, re.IGNORECASE)
        if not sql_match:
             sql_match = re.search(r'```sql\s*([\s\S]*?)$', raw_content, re.IGNORECASE)
             
        if sql_match:
            sql = sql_match.group(1).strip()
            return {
                "corrections": ["Recovered from raw SQL block"],
                "sql": sql,
                "sql_lines": sql.split('\n'),
                "approach": "recovered_raw_sql",
                "explanation": "Extracted from markdown block"
            }

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        
        content = content.strip()
        
        try:
            if content.startswith('{') or content.startswith('['):
                return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_content)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
            
        Logger.log(f"FAILED to parse JSON. Raw response: {content[:100]}...", level="ERROR")
        return None
