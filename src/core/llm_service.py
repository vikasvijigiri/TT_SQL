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
            agent_display = agent_name or "Agent"

            # Configure timeout via botocore
            # settings.TIMEOUT_SECONDS defaults to 90, we can use a higher one for Bedrock
            # User proxy might be slow, so we'll ensure we use at least 180s
            effective_timeout = max(get_settings().TIMEOUT_SECONDS, 180)

            # Finalized Bedrock initialization (Serverless mode)
            llm = ChatBedrockConverse(
                model_id=model_id,
                region_name=self.aws_region or "us-east-1",
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                config=Config(
                    connect_timeout=effective_timeout, read_timeout=effective_timeout
                ),
            )

            response = llm.invoke(messages)
            content = response.content
            
            # --- [PARSING USEFUL CONTENT] ---
            text_parts = []
            reasoning_parts = []
            
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, str): text_parts.append(b)
                    elif isinstance(b, dict):
                        if b.get("type") == "text": text_parts.append(str(b.get("text", "")))
                        elif b.get("type") == "reasoning_content":
                            r_val = b.get("reasoning_content", {})
                            if isinstance(r_val, dict): reasoning_parts.append(str(r_val.get("text", "")))
                        elif "text" in b: text_parts.append(str(b["text"]))
                
                final_content = "".join(text_parts)
                final_reasoning = "".join(reasoning_parts)
            else:
                final_content = str(content)
                final_reasoning = ""

            # --- [USAGE METRICS] ---
            usage = getattr(response, "response_metadata", {}).get("usage", {})
            if not usage:
                usage = getattr(response, "usage_metadata", {})
                
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or (len(str(messages)) // 4)
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or (len(final_content) // 4)
            stop_reason = getattr(response, "response_metadata", {}).get("stop_reason") or "end_turn"

            if state:
                state.last_raw_response = final_content
                state.token_usage["input"] += input_tokens
                state.token_usage["output"] += output_tokens
                state.last_call_metrics = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "max": max_tokens or self.max_tokens,
                    "stop": stop_reason.lower()
                }
                state.llm_call_count += 1
                
                # Per-agent breakdown tracking
                if not hasattr(state, "agent_metrics") or state.agent_metrics is None:
                    state.agent_metrics = {}
                
                a_name = agent_name or "Agent"
                if a_name not in state.agent_metrics:
                    state.agent_metrics[a_name] = {"calls": 0, "tokens": []}
                
                state.agent_metrics[a_name]["calls"] += 1
                state.agent_metrics[a_name]["tokens"].append(input_tokens + output_tokens)
                
            return final_content

        except Exception as e:
            Logger.log(f"Error calling Bedrock: {e}", level="ERROR")
            return f"ERROR: {e}"

    def get_json_completion(
        self,
        messages: list[dict[str, str]],
        state: Any | None = None,
        agent_name: str = "UNKNOWN",
        max_tokens: int = 4096,
    ) -> Any:
        """Helper to get and parse JSON response."""
        content = self.get_completion(messages, state=state, agent_name=agent_name, max_tokens=max_tokens)
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Any:
        """Strict JSON parsing (Task 2). No repair. No markdown extraction."""
        if not content or content.startswith("ERROR:"):
            return None

        try:
            return json.loads(content.strip())
        except Exception:
            return None
