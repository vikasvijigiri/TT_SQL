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

            # Strip provider prefix if present (e.g. 'bedrock/openai...' -> 'openai...')
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

            response = llm.invoke(messages)
            content = response.content

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
        """Parses JSON from LLM response with fallback for noise."""
        if not content or content.startswith("ERROR:"):
            return None

        content_clean = content.strip()

        try:
            # 1. Try extracting content inside markdown code blocks first
            json_matches = re.findall(
                r"```(?:json)?\s*(\{.*?\})\s*```", content_clean, re.DOTALL
            )
            if json_matches:
                # Try from last to first (usually the answer is at the end)
                for candidate in reversed(json_matches):
                    try:
                        return json.loads(candidate.strip())
                    except Exception:
                        continue

            # 2. Fallback: Extract ANY valid-looking JSON block { ... }
            # We use a balanced-extraction-like approach or just try all candidates
            # Regex for finding candidates between balanced braces is hard,
            # so we'll find all indices of '{' and try everything from there.
            all_starts = [m.start() for m in re.finditer(r"\{", content_clean)]
            for start in reversed(all_starts):
                # Look for the matching last '}'
                end = content_clean.rfind("}", start)
                if end != -1:
                    candidate = content_clean[start : end + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        continue

        except Exception:
            pass

        return None
