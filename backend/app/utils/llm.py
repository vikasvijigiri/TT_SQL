import asyncio
import os
import json
import re
import time
import yaml
from typing import Type, TypeVar, List, Dict, Any, Optional
from pydantic import BaseModel
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

from backend.app.utils.logger import logger
from backend.app.core.config import CONFIG_DIR
from backend.app.core.prompts.schema_compactor import SchemaCompactor

# Load environment variables from .env
load_dotenv()

import threading

# Bedrock transient errors that are safe to retry
_RETRYABLE_ERRORS = (
    "ThrottlingException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeoutException",
)

thread_local = threading.local()

def reset_token_counters():
    thread_local.input_tokens = 0
    thread_local.output_tokens = 0

def add_tokens(input_tokens: int, output_tokens: int):
    if not hasattr(thread_local, "input_tokens"):
        thread_local.input_tokens = 0
    if not hasattr(thread_local, "output_tokens"):
        thread_local.output_tokens = 0
    thread_local.input_tokens += input_tokens
    thread_local.output_tokens += output_tokens

def get_tokens() -> tuple:
    in_t = getattr(thread_local, "input_tokens", 0)
    out_t = getattr(thread_local, "output_tokens", 0)
    return in_t, out_t

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
                llm_cfg = params.get("llm", {})
                sys_temp = float(llm_cfg.get("temperature", 0.0))
                sys_model = llm_cfg.get("model", "bedrock/openai.gpt-oss-safeguard-120b")
                self._max_tokens = int(llm_cfg.get("max_tokens", 8000))
                self._max_retries = int(llm_cfg.get("max_retries", 3))
                self._retry_base_delay = float(llm_cfg.get("retry_base_delay_s", 1.0))
        except Exception:
            sys_temp = 0.0
            sys_model = "bedrock/openai.gpt-oss-safeguard-120b"
            self._max_tokens = 8000
            self._max_retries = 3
            self._retry_base_delay = 1.0

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
            logger.info(f"Initializing ChatBedrockConverse | Model: {self.model_id} | Region: {self.region} | max_tokens: {self._max_tokens}")
            self.llm = ChatBedrockConverse(
                model=self.model_id,
                region_name=self.region,
                default_headers=headers,
                max_tokens=self._max_tokens,
                temperature=temp,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatBedrockConverse: {str(e)}")
            raise

    def _extract_json_from_text(self, content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None
            
        # Strip <think>...</think> blocks if present
        content_clean = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # If <think> was unclosed due to truncation, strip from <think> to the first '{'
        if '<think>' in content_clean:
            first_brace = content_clean.find('{')
            if first_brace != -1 and first_brace > content_clean.find('<think>'):
                content_clean = content_clean[:content_clean.find('<think>')] + content_clean[first_brace:]
            else:
                content_clean = re.sub(r'<think>.*$', '', content_clean, flags=re.DOTALL | re.IGNORECASE)

        def try_parse(s: str) -> Optional[Dict[str, Any]]:
            try:
                # Remove JS/SQL style inline comments inside JSON
                s_clean = re.sub(r'^\s*//.*$', '', s, flags=re.MULTILINE)
                s_clean = re.sub(r'/\*.*?\*/', '', s_clean, flags=re.DOTALL)
                # Remove trailing commas
                s_clean = re.sub(r',\s*([\]\}])', r'\1', s_clean.strip())
                res = json.loads(s_clean, strict=False)
                if isinstance(res, dict):
                    return res
                return None
            except:
                return None

        # 1. Check markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content_clean, re.DOTALL | re.IGNORECASE)
        if json_match:
            p = try_parse(json_match.group(1))
            if p is not None:
                return p

        # 2. Industry standard: find outermost { and }
        start_idx = content_clean.find('{')
        end_idx = content_clean.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            outer_cand = content_clean[start_idx:end_idx+1]
            p = try_parse(outer_cand)
            if p is not None:
                return p

        # 3. Fallback scan ALL opening braces
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

        # 4. Truncation recovery at token limits
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
        try:
            schema_str = SchemaCompactor.compact_json_schema(response_model)
        except Exception:
            schema_str = "Required fields and types matching " + response_model.__name__

        json_enforcer = (
            f"\n\nCRITICAL MANDATORY INSTRUCTION: You MUST format your entire output EXACTLY as pure valid JSON enclosed in ```json ... ``` adhering to this minimal JSON skeleton structure:\n```json\n{schema_str}\n```\n\n"
            "You MUST start your JSON response directly with ```json\n{\n... without any introductory text outside the JSON block. "
            "IMPORTANT FOR REASONING MODELS: If you use a <think> scratchpad, you MUST keep your internal thinking concise and summarized under 500 tokens. "
            "Do NOT engage in repetitive item-by-item loops (such as repeating 'Potential issues: ... Good.' over and over). "
            "Exhaustive repetitive loops will cause token truncation before the JSON is generated, resulting in system failure."
        )

        sys_enforced = system_prompt + json_enforcer if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt else system_prompt
        
        raw_content = self.generate(sys_enforced, user_prompt)
        data = self._extract_json_from_text(raw_content)
        
        if not data:
            logger.warning(f"Initial JSON generation failed for {response_model.__name__}. Executing self-repair retry...")
            repair_prompt = user_prompt + (
                "\n\n[SYSTEM REPAIR NOTICE]: Your previous response failed to parse as valid JSON. "
                "This usually happens when your internal <think> scratchpad gets stuck in repetitive item-by-item verification loops, causing token truncation before the JSON object can be output. "
                "On this retry, you MUST keep your <think> reasoning extremely brief (under 300 tokens) and focus entirely on generating the complete valid JSON object inside ```json ... ``` before running out of tokens."
            )
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

    def _is_retryable(self, exc: Exception) -> bool:
        err_str = type(exc).__name__ + " " + str(exc)
        return any(tag in err_str for tag in _RETRYABLE_ERRORS)

    def _parse_response(self, response) -> tuple:
        """Return (final_str, in_t, out_t) from a Bedrock response."""
        content = response.content
        if isinstance(content, list):
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

        in_t, out_t = 0, 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            in_t = response.usage_metadata.get("input_tokens", 0)
            out_t = response.usage_metadata.get("output_tokens", 0)
        elif hasattr(response, "response_metadata") and "usage" in response.response_metadata:
            u = response.response_metadata["usage"]
            in_t = u.get("inputTokens", u.get("input_tokens", 0))
            out_t = u.get("outputTokens", u.get("output_tokens", 0))
        return final_str, in_t, out_t

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Simple text completion with exponential-backoff retry on transient Bedrock errors."""
        logger.debug(f"LLM Prompt lengths | System: {len(system_prompt)} | User: {len(user_prompt)}")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                final_str, in_t, out_t = self._parse_response(response)
                add_tokens(in_t, out_t)
                metrics = {"input_tokens": in_t, "output_tokens": out_t}
                full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
                agent_name = getattr(logger.logger, 'name', 'AGENT')
                logger.log_agent_call(agent_name, full_prompt, final_str, metrics)
                return final_str
            except Exception as e:
                last_exc = e
                if self._is_retryable(e) and attempt < self._max_retries:
                    delay = self._retry_base_delay * (2 ** attempt)
                    logger.warning(f"Transient Bedrock error (attempt {attempt + 1}/{self._max_retries}): {e}. Retrying in {delay:.1f}s…")
                    time.sleep(delay)
                else:
                    break

        logger.error(f"LLM Generation Failed after {self._max_retries + 1} attempts: {last_exc}")
        raise last_exc

    async def async_generate(self, system_prompt: str, user_prompt: str) -> str:
        """Non-blocking wrapper around generate() for use in async FastAPI handlers."""
        return await asyncio.to_thread(self.generate, system_prompt, user_prompt)

    async def async_generate_structured(self, system_prompt: str, user_prompt: str, response_model: Type[T]) -> T:
        """Non-blocking wrapper around generate_structured() for use in async FastAPI handlers."""
        return await asyncio.to_thread(self.generate_structured, system_prompt, user_prompt, response_model)
