import os
import json
import re
import traceback
from typing import Type, TypeVar, List, Dict, Any, Optional
from pydantic import BaseModel
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.utils.logger import logger
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

T = TypeVar('T', bound=BaseModel)

class LLMClient:
    """
    Refactored LLM Client to use ChatBedrockConverse with credentials from .env.
    Supports proxy-aware Bearer token authentication.
    """
    def __init__(self, model: str = None, temperature: float = 0.0):
        # Use LLM_MODEL from .env if not provided
        self.full_model_name = model or os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b")
        
        # Split prefix if present (e.g., 'bedrock/...')
        if "/" in self.full_model_name:
            self.model_id = self.full_model_name.split("/", 1)[1]
        else:
            self.model_id = self.full_model_name

        self.region = os.getenv("BEDROCK_REGION", "us-east-1")
        
        # Using the secret key as the Bearer token as per src_backup1 implementation
        api_key = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            logger.info(f"Initializing ChatBedrockConverse | Model: {self.model_id} | Region: {self.region}")
            self.llm = ChatBedrockConverse(
                model_id=self.model_id,
                region_name=self.region,
                default_headers=headers,
                max_tokens=8000,
                temperature=temperature,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatBedrockConverse: {str(e)}")
            raise

    def generate_structured(self, system_prompt: str, user_prompt: str, response_model: Type[T]) -> T:
        """
        Sends a prompt and forces the output to match the provided Pydantic schema.
        Uses manual JSON extraction followed by Pydantic validation.
        """
        data = self.generate_json(system_prompt, user_prompt)
        if not data:
            raise ValueError(f"Failed to generate valid JSON for {response_model.__name__}")
        
        try:
            return response_model.model_validate(data)
        except Exception as e:
            logger.error(f"Pydantic Validation Failed for {response_model.__name__}: {str(e)}")
            logger.error(f"Data: {json.dumps(data, indent=2)}")
            raise
    def generate_json(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Sends a prompt and extracts JSON from the response.
        """
        content = self.generate(system_prompt, user_prompt)
        if not content:
            return None
            
        # 1. Try to extract from ```json block (if properly closed)
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if json_match:
            try:
                clean = re.sub(r',\s*([\]\}])', r'\1', json_match.group(1).strip())
                return json.loads(clean)
            except:
                pass

        # 2. Brace counting algorithm to find the largest valid JSON object
        best_json = None
        max_len = -1
        
        for i in range(len(content)):
            if content[i] == '{':
                brace_count = 0
                for j in range(i, len(content)):
                    if content[j] == '{':
                        brace_count += 1
                    elif content[j] == '}':
                        brace_count -= 1
                        
                    if brace_count == 0:
                        candidate = content[i:j+1]
                        if len(candidate) > max_len:
                            try:
                                clean = re.sub(r',\s*([\]\}])', r'\1', candidate.strip())
                                parsed = json.loads(clean)
                                best_json = parsed
                                max_len = len(candidate)
                            except:
                                pass
                        break # Found the matching closing brace for this opening brace
                        
        if best_json is not None:
            return best_json
            
        logger.error(f"JSON Parsing Failed. Raw content:\n{content}")
        return None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Simple text completion."""
        logger.debug(f"LLM Prompt lengths | System: {len(system_prompt)} | User: {len(user_prompt)}")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        try:
            response = self.llm.invoke(messages)
            content = response.content
            if isinstance(content, list):
                # Join all blocks (text or reasoning) to ensure we capture the output
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        # Try to find 'text' or 'reasoning_content'
                        if "text" in block:
                            parts.append(block["text"])
                        elif "reasoning_content" in block:
                            # If it's a dict with 'text', get it
                            rc = block["reasoning_content"]
                            if isinstance(rc, dict) and "text" in rc:
                                parts.append(rc["text"])
                            else:
                                parts.append(str(rc))
                    else:
                        parts.append(str(block))
                return "".join(parts).strip()
            return str(content).strip()
        except Exception as e:
            logger.error(f"LLM Generation Failed: {str(e)}")
            raise
