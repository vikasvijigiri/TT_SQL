import json
import re
from typing import Any

from botocore.config import Config

from core.config import get_settings
from core.logger import Logger


class LLMService:
    """
    Unified interface for calling LLMs (Bedrock).
    Provides consistent methods for text and JSON generation.
    """

    _CACHE = {}

    @classmethod
    def clear_cache(cls):
        cls._CACHE = {}

    def __init__(self, model: str | None = None):
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
            Logger.log(
                "Bedrock credentials missing. LLM service will be simulated.",
                level="WARN",
            )

    def get_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        state: Any | None = None,
        agent_name: str = "UNKNOWN",
    ) -> str:
        """Calls Bedrock with standardized message format."""
        if not self.enabled:
            return "SIMULATED_RESPONSE: LLM not configured."

        try:
            from langchain_aws import ChatBedrockConverse

            # Strip provider prefix if present (e.g. 'bedrock/model-id' -> 'model-id')
            model_id = (
                self.model_name.split("/")[-1]
                if "/" in self.model_name
                else self.model_name
            )

            # Logger context
            formatted_agent = f"LLM REQUEST: {agent_name.upper()}"
            Logger.log_stage_header(formatted_agent)

            # Configure timeout via botocore
            # settings.TIMEOUT_SECONDS defaults to 90, we can use a higher one for Bedrock
            # User proxy might be slow, so we'll ensure we use at least 180s
            effective_timeout = max(get_settings().TIMEOUT_SECONDS, 180)

            # Finalized Bedrock initialization with Bearer token
            llm = ChatBedrockConverse(
                model_id=model_id,
                region_name=self.aws_region or "us-east-1",
                default_headers={"Authorization": f"Bearer {self.aws_secret_key}"},
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                config=Config(
                    connect_timeout=effective_timeout, read_timeout=effective_timeout
                ),
            )

            # Log the prompt for auditability
            Logger.log("--- LLM PROMPT START ---")
            for msg in messages:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                Logger.log(f"**[{role}]**:\n{content}\n")
            Logger.log("--- LLM PROMPT END ---")

            response = llm.invoke(messages)
            content = response.content
            
            # Log Response Metadata for auditability (including content-length, tokens, etc.)
            if hasattr(response, "response_metadata"):
                Logger.log(f"ResponseMetadata: {json.dumps(response.response_metadata)}")

            # Simple handle for multi-part content
            if isinstance(content, list):
                text_parts = []
                for b in content:
                    if isinstance(b, str):
                        text_parts.append(b)
                    elif isinstance(b, dict):
                        if "text" in b:
                            text_parts.append(str(b["text"]))
                        elif "reasoning_content" in b and isinstance(
                            b["reasoning_content"], dict
                        ):
                            text_parts.append(
                                str(b["reasoning_content"].get("text", ""))
                            )
                        elif "content" in b:
                            text_parts.append(str(b["content"]))
                        else:
                            # Fallback: if it's a dict but we don't know the key, just stringify it
                            text_parts.append(str(b))
                content = "".join(text_parts)

            # Refresh state with latest response for traceability
            if state:
                state.last_raw_response = content
                state.token_usage["input"] += len(str(messages)) // 4
                state.token_usage["output"] += len(content) // 4

            return content

        except Exception as e:
            Logger.log(f"Error calling Bedrock: {e}", level="ERROR")
            return f"ERROR: {e}"

    def get_json_completion(
        self,
        messages: list[dict[str, str]],
        state: Any | None = None,
        agent_name: str = "UNKNOWN",
    ) -> Any:
        """Helper to get and parse JSON response."""
        content = self.get_completion(messages, state=state, agent_name=agent_name)
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Any:
        """Parses JSON from LLM response with robust multi-stage recovery.
        Handles markdown blocks, conversational noise, and trailing commas.
        """
        if not content or content.startswith("ERROR:"):
            return None

        # 1. Direct Load Attempt
        content_clean = content.strip()
        try:
            return json.loads(content_clean)
        except Exception:
            pass

        # 2. Markdown Block Extraction
        # Look for ```json ... ``` or ``` ... ```
        json_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content_clean)
        for block in reversed(json_blocks):
            repaired = self._repair_json_string(block)
            try:
                return json.loads(repaired)
            except Exception:
                continue

        # 3. Brute Force Brace Extraction
        # Find the first '{' or '[' and the last '}' or ']'
        try:
            # Check for Objects first
            obj_start = content_clean.find("{")
            obj_end = content_clean.rfind("}")
            if obj_start != -1 and obj_end != -1:
                candidate = content_clean[obj_start : obj_end + 1]
                repaired = self._repair_json_string(candidate)
                try:
                    return json.loads(repaired)
                except Exception:
                    pass

            # Check for Arrays second
            arr_start = content_clean.find("[")
            arr_end = content_clean.rfind("]")
            if arr_start != -1 and arr_end != -1:
                candidate = content_clean[arr_start : arr_end + 1]
                repaired = self._repair_json_string(candidate)
                try:
                    return json.loads(repaired)
                except Exception:
                    pass
        except Exception:
            pass

        return None

    def _repair_json_string(self, raw_str: str) -> str:
        """Applies common fixes to malformed JSON strings from LLMs."""
        # 1. Remove trailing commas before closing braces/brackets
        # This matches a comma followed by whitespace and then a closing brace/bracket
        repaired = re.sub(r",\s*([\]}])", r"\1", raw_str)
        
        # 2. Fix many-to-one escaped quotes if present (less common but happens)
        # repaired = repaired.replace('\\"', '"') 
        
        return repaired.strip()
