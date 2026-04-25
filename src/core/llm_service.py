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

            # --- [SHOWING ONLY IMPORTANT THINGS - PRECISE PARSING] ---
            if final_reasoning:
                display_reasoning = final_reasoning if len(final_reasoning) < 1200 else final_reasoning[:1200] + "..."
                Logger.log(f"#### 💡 THOUGHT PROCESS\n{display_reasoning}\n")
            
            parsed_json = None
            if "{" in final_content:
                try:
                    # Look for JSON within the text if wrapped in markdown
                    json_str = final_content.strip()
                    if json_str.startswith("```json"): json_str = json_str.split("```json")[1].split("```")[0]
                    elif json_str.startswith("```"): json_str = json_str.split("```")[1].split("```")[0]
                    parsed_json = json.loads(json_str)
                except: pass

            if parsed_json:
                # Handle specific project keys to make it non-messy
                if "candidates" in parsed_json:
                    for i, c in enumerate(parsed_json["candidates"]):
                        Logger.log(f"#### ✨ SQL CANDIDATE {i+1}")
                        if "reasoning" in c: Logger.log(f"> {c['reasoning']}")
                        Logger.log_code(c["sql"], language="sql")
                elif "winning_id" in parsed_json:
                    Logger.log(f"#### 🎯 SELECTION RESULT")
                    Logger.log(f"**Winner**: Candidate {parsed_json.get('winning_id')}")
                    Logger.log(f"**Feedback**: {parsed_json.get('feedback')}")
                elif "is_valid" in parsed_json:
                    Logger.log(f"#### 🔍 AUDIT FEEDBACK")
                    Logger.log(f"**Valid**: {parsed_json.get('is_valid')}")
                    Logger.log(f"**Observation**: {parsed_json.get('feedback')}")
                else:
                    # Fallback for other JSON types (Planning/Discovery)
                    Logger.log("#### 📦 GENERATED DATA")
                    Logger.log_code(json.dumps(parsed_json, indent=2), language="json")
            elif final_content:
                Logger.log(f"#### 📝 RESPONSE\n{final_content}\n")
            
            content = final_content # Carry forward cleaned string
            
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
        max_tokens: int = 4096,
    ) -> Any:
        """Helper to get and parse JSON response."""
        content = self.get_completion(messages, state=state, agent_name=agent_name, max_tokens=max_tokens)
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
