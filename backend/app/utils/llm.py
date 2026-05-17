import os
import json
import re
import traceback
import yaml
from typing import Type, TypeVar, List, Dict, Any, Optional
from pydantic import BaseModel
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

from backend.app.utils.logger import logger
from backend.app.core.config import CONFIG_DIR

# Load environment variables from .env
load_dotenv()

T = TypeVar('T', bound=BaseModel)

class LLMClient:
    """
    Refactored LLM Client to use ChatBedrockConverse with credentials from .env.
    Supports proxy-aware Bearer token authentication.
    """
    def __init__(self, model: str = None, temperature: float = None):
        try:
            with open(CONFIG_DIR / "system_params.yaml", "r", encoding="utf-8") as f:
                params = yaml.safe_load(f)
                sys_temp = float(params.get("llm", {}).get("temperature", 0.0))
                sys_model = params.get("llm", {}).get("model", "bedrock/openai.gpt-oss-safeguard-120b")
        except:
            sys_temp = 0.0
            sys_model = "bedrock/openai.gpt-oss-safeguard-120b"
            
        temp = temperature if temperature is not None else sys_temp
        self.full_model_name = model or os.getenv("LLM_MODEL", sys_model)
        
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
                temperature=temp,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatBedrockConverse: {str(e)}")
            raise

    def _extract_json_from_text(self, content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None
            
        def try_parse(s: str) -> Optional[Dict[str, Any]]:
            try:
                s = re.sub(r',\s*([\]\}])', r'\1', s.strip())
                return json.loads(s, strict=False)
            except:
                return None

        # Strip <think>...</think> blocks if present
        content_clean = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)

        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content_clean, re.DOTALL | re.IGNORECASE)
        if json_match:
            p = try_parse(json_match.group(1))
            if p is not None:
                return p

        # Scan ALL opening braces in content_clean
        idx = 0
        while idx < len(content_clean):
            start_idx = content_clean.find('{', idx)
            if start_idx == -1:
                break
                
            brace_count = 0
            for j in range(start_idx, len(content_clean)):
                if content_clean[j] == '{': brace_count += 1
                elif content_clean[j] == '}': brace_count -= 1
                if brace_count == 0:
                    cand = content_clean[start_idx:j+1]
                    p = try_parse(cand)
                    if p is not None:
                        return p
                    break
            idx = start_idx + 1

        # If cut off mid-string or mid-object at token limits
        start_idx = content_clean.find('{')
        if start_idx != -1:
            cut_off = content_clean[start_idx:].strip()
            for suffix in ('}', '"}', '""}', ']\n}', '"]\n}', '"""]\n}'):
                p = try_parse(cut_off + suffix)
                if p is not None:
                    return p
                    
        return None

    def generate_json(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Sends a prompt and extracts JSON from the response.
        """
        json_enforcer = "\n\nCRITICAL MANDATORY INSTRUCTION: You MUST format your entire response as pure valid JSON inside ```json ... ```. You MUST start your response directly with ```json\n{\n... without any introductory text, conversational preamble, or thinking process outside the JSON block."
        sys_enforced = system_prompt + json_enforcer if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt else system_prompt
        
        content = self.generate(sys_enforced, user_prompt)
        res = self._extract_json_from_text(content)
        if res is not None:
            return res
            
        logger.error(f"JSON Parsing Failed. Raw content:\n{content}")
        return None

    def generate_structured(self, system_prompt: str, user_prompt: str, response_model: Type[T]) -> T:
        """
        Sends a prompt and forces the output to match the provided Pydantic schema.
        Includes an automated self-repair retry if JSON parsing or Pydantic validation fails.
        """
        json_enforcer = "\n\nCRITICAL MANDATORY INSTRUCTION: You MUST format your entire output EXACTLY as pure valid JSON enclosed in ```json ... ``` matching the expected schema. You MUST start your response directly with ```json\n{\n... without any introductory text, conversational preamble, thinking out loud, or concluding remarks outside the JSON block. All step-by-step reasoning MUST be placed strictly inside the JSON string fields."
        sys_enforced = system_prompt + json_enforcer if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt else system_prompt
        
        raw_content = self.generate(sys_enforced, user_prompt)
        data = self._extract_json_from_text(raw_content)
        
        if not data:
            logger.warning(f"Initial JSON generation failed for {response_model.__name__}. Executing self-repair retry...")
            repair_prompt = user_prompt + f"\n\n[SYSTEM REPAIR NOTICE]: Your previous response failed to parse as valid JSON because you output conversational text or markdown before the JSON object. You MUST return ONLY pristine JSON matching the schema requirements starting directly with ```json\n{{\n... without any commentary outside the JSON block."
            raw_content2 = self.generate(sys_enforced, repair_prompt)
            data = self._extract_json_from_text(raw_content2)
            if not data:
                logger.error(f"JSON Parsing Failed after self-repair retry. Raw content:\n{raw_content2}")
                raise ValueError(f"Failed to generate valid JSON for {response_model.__name__} after self-repair retry.")
                
        try:
            return response_model.model_validate(data)
        except Exception as e:
            logger.warning(f"Pydantic Validation Failed for {response_model.__name__}: {str(e)}. Attempting self-repair retry...")
            repair_prompt = user_prompt + f"\n\n[SYSTEM REPAIR NOTICE]: Your previous JSON failed schema validation with error: {str(e)}.\nData parsed was:\n{json.dumps(data, indent=2)}\n\nYou MUST correct this and return ONLY valid JSON matching the exact schema."
            raw_content2 = self.generate(sys_enforced, repair_prompt)
            data2 = self._extract_json_from_text(raw_content2)
            if not data2:
                raise e
            try:
                return response_model.model_validate(data2)
            except Exception as e2:
                logger.error(f"Pydantic Validation Failed on retry for {response_model.__name__}: {str(e2)}")
                raise e2

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
                        if "text" in block:
                            parts.append(block["text"])
                        elif "reasoning_content" in block:
                            rc = block["reasoning_content"]
                            rc_text = rc["text"] if isinstance(rc, dict) and "text" in rc else str(rc)
                            parts.append(f"<think>\n{rc_text}\n</think>\n")
                    else:
                        parts.append(str(block))
                final_str = "\n".join(parts).strip()
            else:
                final_str = str(content).strip()
            
            # Log the complete prompt and response for auditing
            full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
            agent_name = getattr(logger.logger, 'name', 'AGENT')
            logger.log_agent_call(agent_name, full_prompt, final_str)
            
            return final_str
        except Exception as e:
            logger.error(f"LLM Generation Failed: {str(e)}")
            raise
