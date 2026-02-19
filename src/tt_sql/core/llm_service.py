from typing import List, Dict, Optional, Any
import os
import json
import boto3
from openai import OpenAI
import re
from .state import AgentState
from .logger import Logger
from dotenv import load_dotenv

load_dotenv()

try:
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
    API_KEY = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
    
except ImportError:
    LANGCHAIN_AVAILABLE = False

class LLMService:
    """
    Service to handle interactions with Large Language Models using official SDKs.
    Supports Amazon Bedrock (Direct via Boto3) and OpenAI.
    """
    
    def __init__(self, provider: str = None, model: str = None):
        # Load configs from ENV or defaults
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        
        # Determine if we are using Bedrock
        self.is_bedrock = self.model.lower().startswith("bedrock/")
        
        if self.is_bedrock:
            self._init_bedrock_client()
        else:
            self._init_openai_client()

    def _init_bedrock_client(self):
        if not LANGCHAIN_AVAILABLE:
            print("ERROR: langchain-aws or langchain-core not installed.")
            self.client = None
            return

        try:
            # Strip prefix (e.g. 'bedrock/anthropic...' -> 'anthropic...')
            self.model_id = self.model.split("/", 1)[1] if "/" in self.model else self.model

            # ChatBedrockConverse uses AWS credentials from environment or ~/.aws/credentials
            # No need to explicitly pass credentials if configured via 'aws configure'
            self.client = ChatBedrockConverse(
                model_id=self.model_id,
                region_name=os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "us-east-1",
                default_headers={"Authorization": f"Bearer {API_KEY}"},
                max_tokens=4000,
                temperature=0.0,
            )
            print(f"Initialized ChatBedrockConverse for: {self.model_id}")
        except Exception as e:
            print(f"Failed to initialize ChatBedrockConverse client: {e}")
            self.client = None

    def _init_openai_client(self):
        try:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            print(f"Initialized OpenAI SDK for: {self.model}")
        except Exception as e:
            print(f"Failed to initialize OpenAI client: {e}")
            self.client = None

    def _init_bedrock_agent_runtime(self):
        try:
            self.bedrock_agent_runtime = boto3.client(
                service_name='bedrock-agent-runtime',
                region_name=os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "us-east-1",
                aws_access_key_id=os.getenv("BEDROCK_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("BEDROCK_SECRET_ACCESS_KEY")
            )
        except Exception as e:
            print(f"Failed to initialize Bedrock Agent Runtime: {e}")
            self.bedrock_agent_runtime = None

    def retrieve_from_kb(self, kb_id: str, query: str, max_results: int = 5) -> List[str]:
        """
        Retrieve relevant context from Amazon Bedrock Knowledge Base.
        """
        if not hasattr(self, 'bedrock_agent_runtime') or not self.bedrock_agent_runtime:
            self._init_bedrock_agent_runtime()
            
        if not self.bedrock_agent_runtime:
             Logger.log("Bedrock Agent Runtime not available", level="WARNING")
             return []
             
        try:
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=kb_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results
                    }
                }
            )
            
            results = []
            if 'retrievalResults' in response:
                for result in response['retrievalResults']:
                    content = result.get('content', {}).get('text', '')
                    if content:
                        results.append(content)
                        
            Logger.log(f"Retrieved {len(results)} chunks from Knowledge Base", level="INFO")
            return results
        except Exception as e:
            Logger.log(f"Knowledge Base Retrieval Failed: {e}", level="ERROR")
            return []

    def get_completion(self, 
                       messages: List[Dict[str, str]], 
                       temperature: float = 0.0, 
                       max_tokens: int = 8000,
                       state: Optional[AgentState] = None) -> str:
        if not self.client:
            return "ERROR: LLM Client not initialized. Please check your credentials in .env"

        # --- LOG PROMPT WITH AGENT NAME ---
        try:
            import inspect
            caller_name = "UNKNOWN"
            for frame_info in inspect.stack():
                obj = frame_info.frame.f_locals.get("self")
                if obj and hasattr(obj, "name") and obj is not self:
                    caller_name = obj.name
                    break

            log_content = f"\n--- {caller_name.upper()} PROMPT ---\n"
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                log_content += f"**[{role}]**:\n{content}\n\n"
            log_content += "----------------\n"
            Logger.log(log_content, level="DEBUG") 
        except Exception:
            pass
        # ------------------

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
        # Extract system messages separately - Bedrock Converse doesn't support them in messages array
        system_content = []
        lc_messages = []
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                # Collect system messages separately
                system_content.append(content)
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                # Fallback for unknown roles
                lc_messages.append(HumanMessage(content=content))

        # If we have system messages but no user messages, prepend system as user message
        if system_content and not lc_messages:
            lc_messages.append(HumanMessage(content="\n\n".join(system_content)))
        elif system_content and lc_messages:
            # Prepend system content to first user message
            first_msg_content = lc_messages[0].content
            combined_content = "\n\n".join(system_content) + "\n\n" + first_msg_content
            lc_messages[0] = HumanMessage(content=combined_content)

        # Invoke via LangChain
        response = self.client.invoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract and log token usage - try multiple metadata structures
        try:
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            
            # Try different metadata structures
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                
                # Structure 1: usage dict
                if 'usage' in metadata:
                    usage = metadata['usage']
                    input_tokens = usage.get('input_tokens', usage.get('prompt_tokens', 0))
                    output_tokens = usage.get('output_tokens', usage.get('completion_tokens', 0))
                    total_tokens = usage.get('total_tokens', input_tokens + output_tokens)
                
                # Structure 2: Direct in metadata
                elif 'input_tokens' in metadata or 'prompt_tokens' in metadata:
                    input_tokens = metadata.get('input_tokens', metadata.get('prompt_tokens', 0))
                    output_tokens = metadata.get('output_tokens', metadata.get('completion_tokens', 0))
                    total_tokens = metadata.get('total_tokens', input_tokens + output_tokens)
            
            if input_tokens > 0 or output_tokens > 0:
                Logger.log(
                    f"📊 Token Usage - Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens} | Max: {max_tokens}",
                    level="INFO"
                )
                self._track_usage(input_tokens, output_tokens, state)
            else:
                # Debug: log the metadata structure to understand it
                Logger.log(f"Debug: Response metadata structure: {response.response_metadata if hasattr(response, 'response_metadata') else 'No metadata'}", level="DEBUG")
        except Exception as e:
            Logger.log(f"Failed to extract token usage: {e}", level="DEBUG")
        
        # Handle content being a list (Converse API structure)
        content = response.content
        if isinstance(content, list):
             # Join text blocks
             text_parts = []
             for block in content:
                 if isinstance(block, str):
                     text_parts.append(block)
                 elif isinstance(block, dict) and 'text' in block:
                     text_parts.append(block['text'])
             content = "".join(text_parts)
             
        return content.strip() if isinstance(content, str) else str(content)

    def get_completion_stream(self, 
                              messages: List[Dict[str, str]], 
                              temperature: float = 0.0, 
                              max_tokens: int = 8000):
        """Yields completion tokens."""
        if not self.client:
            yield "ERROR: LLM Client not initialized."
            return

        try:
            if self.is_bedrock:
                yield from self._get_bedrock_stream(messages, temperature, max_tokens)
            else:
                yield from self._get_openai_stream(messages, temperature, max_tokens)
        except Exception as e:
            error_msg = str(e)
            Logger.log(f"LLM Stream Error: {error_msg}", level="ERROR")
            yield f"ERROR: {error_msg}"

    def _get_bedrock_stream(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int):
        # Prepare messages (reuse logic from sync method)
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

        # Stream via LangChain
        try:
            for chunk in self.client.stream(lc_messages, temperature=temperature, max_tokens=max_tokens):
                if isinstance(chunk, str):
                    yield chunk
                elif hasattr(chunk, 'content'):
                    content = chunk.content
                    if isinstance(content, list):
                        # Handle list of blocks (e.g. [{'text': '...'}])
                        text_parts = []
                        for block in content:
                            if isinstance(block, str):
                                text_parts.append(block)
                            elif isinstance(block, dict) and 'text' in block:
                                text_parts.append(block['text'])
                        yield "".join(text_parts)
                    else:
                        yield str(content)
        except Exception as e:
            Logger.log(f"Bedrock stream failed: {e}", level="ERROR")
            yield ""

    def _get_openai_stream(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
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
                            state: Optional[AgentState] = None) -> Any:
        # Pass state to get_completion for tracking
        content = self.get_completion(messages, state=state)
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
