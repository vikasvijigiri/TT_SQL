import os
import json
import re
import time
import yaml
from typing import Type, TypeVar, Dict, Any, Optional
from pydantic import BaseModel
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from dotenv import load_dotenv
from agent.app.core.observability.token_monitor import record_call as _record_token_call

# Force python to use the certifi CA bundle, preventing Windows-specific SSL cert lookup failures
import certifi
import urllib3
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Clean up invalid OpenSSL configuration on Windows if pointing to a non-existent file
if os.environ.get("OPENSSL_CONF") and not os.path.exists(os.environ["OPENSSL_CONF"]):
    os.environ.pop("OPENSSL_CONF", None)

# Load environment variables from .env
load_dotenv()

from agent.app.utils.logger import logger
from agent.app.core.config import CONFIG_DIR
from agent.app.core.prompts.schema_compactor import SchemaCompactor

# Load environment variables from .env
load_dotenv()

# Initialize global LLM cache if enabled
if os.getenv("USE_LLM_CACHE", "true").lower() == "true":
    set_llm_cache(SQLiteCache(database_path=str(CONFIG_DIR.parent / ".langchain_cache.db")))

import threading

# Bedrock transient errors that are safe to retry (and should count toward the CB)
_RETRYABLE_ERRORS = (
    "ThrottlingException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeoutException",
    "ReadTimeoutError",
    "TimeoutError",
    "ReadTimeout",
    "EndpointConnectionError",
    "ConnectionError",
    "ConnectTimeoutError",
    "NewConnectionError",
    "Connection was closed",
    "Connection reset",
    "RemoteDisconnected",
    "BrokenPipeError",
    "IncompleteRead",
    "ProtocolError",
)

thread_local = threading.local()

# ---------------------------------------------------------------------------
# Module-level circuit breaker for Bedrock / LLM backend
#
# Design goals:
#   • Open after CB_FAILURE_THRESHOLD consecutive non-retryable failures.
#   • When open, callers BLOCK (not raise) inside _cb_wait_until_clear()
#     so the pipeline thread stays alive and the log keeps accumulating.
#   • After CB_RESET_AFTER_S seconds exactly ONE thread is granted a probe;
#     all others keep blocking on _cb_probe_event to prevent thundering-herd
#     re-opens where 3 parallel workers all probe, all fail, reopen immediately.
#   • Total patience budget = CB_MAX_WAIT_S (10 min). Only after that does
#     the caller raise so the query is recorded as a genuine failure.
# ---------------------------------------------------------------------------
CB_FAILURE_THRESHOLD: int = 10     # raised for 8-10 parallel workers
CB_RESET_AFTER_S: float = 120.0    # lockout window per open event
CB_MAX_WAIT_S: float = 1800.0      # give up after 30 minutes of total waiting

_cb_lock = threading.Lock()
_cb_failures: int = 0
_cb_opened_at: float = 0.0
_cb_probing: bool = False
_cb_probe_event = threading.Event()
_cb_probe_event.set()   # SET = no active lockout; CLEAR = lockout active


def _cb_record_failure() -> None:
    global _cb_failures, _cb_opened_at, _cb_probing
    with _cb_lock:
        _cb_failures += 1
        if _cb_failures >= CB_FAILURE_THRESHOLD and _cb_opened_at == 0.0:
            _cb_opened_at = time.time()
            _cb_probe_event.clear()   # signal lockout — blocks waiting threads
        if _cb_probing:
            # Probe just failed: reset the lockout clock so the NEXT probe must
            # wait a full CB_RESET_AFTER_S window (prevents back-to-back probing
            # by all N waiting workers when Bedrock is down).
            _cb_probing = False
            _cb_opened_at = time.time()   # fresh 120s window before next probe
            # Keep event CLEAR — waiting threads stay blocked for the new window


def _cb_record_success() -> None:
    global _cb_failures, _cb_opened_at, _cb_probing
    with _cb_lock:
        _cb_failures = 0
        _cb_opened_at = 0.0
        _cb_probing = False
        _cb_probe_event.set()   # unblock all waiting threads


def _cb_is_open() -> bool:
    """Pure state check — does NOT block. Use _cb_wait_until_clear() to block.

    When the reset window elapses, exactly ONE thread is granted the probe slot
    (_cb_probing = True) and allowed through (returns False).  All other threads
    keep seeing True while _cb_probing is set, so they stay blocked in
    _cb_wait_until_clear().  This prevents the thundering-herd re-open where
    multiple workers probe simultaneously, all fail, and immediately re-open.

    Crucially, the probe does NOT reset _cb_failures here — only
    _cb_record_success() does that.  If we reset early, all threads calling
    _cb_is_open() would see failures=0 < threshold and rush through at once.
    """
    global _cb_probing
    with _cb_lock:
        if _cb_failures < CB_FAILURE_THRESHOLD:
            return False   # CB closed — allow through

        if _cb_probing:
            return True   # another thread already probing — keep this one blocked

        elapsed = time.time() - _cb_opened_at
        if elapsed >= CB_RESET_AFTER_S:
            # Reset window elapsed — grant this ONE thread the probe slot.
            # DO NOT touch _cb_failures / _cb_opened_at here; only success clears those.
            _cb_probing = True
            return False   # probe thread allowed through

        return True   # still within lockout window


def _cb_wait_until_clear(max_wait_s: float = CB_MAX_WAIT_S) -> None:
    """Block the calling thread until the circuit breaker clears or max_wait_s
    elapses.  Raises RuntimeError only after the patience budget is exhausted.

    Behaviour:
    - CB closed → returns immediately (no-op).
    - CB open, reset window not elapsed → waits on _cb_probe_event (efficient;
      wakes early when probe succeeds and sets the event).
    - CB open, reset window elapsed, no probe in-flight → this thread becomes
      the probe (returns immediately so it can make the real LLM call).
    - CB open, probe already in-flight → keeps waiting; probe result (success
      or new lockout) determines next action.
    """
    deadline = time.time() + max_wait_s
    while True:
        if not _cb_is_open():
            return   # clear — proceed with the LLM call

        remaining = deadline - time.time()
        if remaining <= 0:
            raise RuntimeError(
                f"LLM circuit breaker remained open for {max_wait_s:.0f}s "
                f"({CB_FAILURE_THRESHOLD} consecutive Bedrock failures). "
                "Giving up on this query."
            )

        # Block efficiently — wakes when probe_event is SET (probe succeeded)
        # or after min(CB_RESET_AFTER_S, remaining) seconds (next probe window)
        wait_s = min(CB_RESET_AFTER_S + 5, remaining)
        logger.warning(
            f"[CircuitBreaker] Bedrock endpoint unreachable — "
            f"blocking {wait_s:.0f}s (budget left: {remaining:.0f}s) ..."
        )
        _cb_probe_event.wait(timeout=wait_s)
        # After waking (event set OR timeout), loop and re-check _cb_is_open()


def reset_token_counters():
    thread_local.input_tokens = 0
    thread_local.output_tokens = 0


def add_tokens(input_tokens: int, output_tokens: int, component: Optional[str] = None):
    if not hasattr(thread_local, "input_tokens"):
        thread_local.input_tokens = 0
    if not hasattr(thread_local, "output_tokens"):
        thread_local.output_tokens = 0
    thread_local.input_tokens += input_tokens
    thread_local.output_tokens += output_tokens
    _record_token_call(input_tokens, output_tokens, component=component)  # aggregate to process-level monitor


def get_tokens() -> tuple:
    in_t = getattr(thread_local, "input_tokens", 0)
    out_t = getattr(thread_local, "output_tokens", 0)
    return in_t, out_t


T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Refactored LLM Client to use ChatBedrockConverse with credentials from .env.
    Supports proxy-aware Bearer token authentication.
    """

    def __init__(self, model: str | None = None, temperature: float | None = None):
        from agent.app.utils.cache import cache_service
        params = cache_service.get("system_params")
        if params is None:
            try:
                with open(CONFIG_DIR / "system_params.yaml", "r", encoding="utf-8") as f:
                    params = yaml.safe_load(f)
                    cache_service.set("system_params", params, ttl=3600)
            except Exception:
                params = {}

        try:
            llm_cfg = params.get("llm", {}) if params else {}
            sys_temp = float(llm_cfg.get("temperature", 0.0))
            sys_model = llm_cfg.get(
                "model", "bedrock/openai.gpt-oss-safeguard-120b"
            )
            self._max_tokens = int(llm_cfg.get("max_tokens", 8000))
            self._max_retries = int(llm_cfg.get("max_retries", 5))
            self._retry_base_delay = float(llm_cfg.get("retry_base_delay_s", 3.0))
            self._caching_models: tuple = tuple(
                llm_cfg.get("prompt_caching_models", ["claude-3-5", "claude-3-haiku", "claude-3-7", "claude-4", "nova"])
            )
        except Exception:
            sys_temp = 0.0
            sys_model = "bedrock/openai.gpt-oss-safeguard-120b"
            self._max_tokens = 8000
            self._max_retries = 5
            self._retry_base_delay = 3.0
            self._caching_models = ("claude-3-5", "claude-3-haiku", "claude-3-7", "claude-4", "nova")

        temp = temperature if temperature is not None else sys_temp
        self.full_model_name = model or os.getenv("LLM_MODEL", sys_model)

        # Split prefix if present (e.g., 'bedrock/...')
        if "/" in self.full_model_name:  # type: ignore
            self.model_id = self.full_model_name.split("/", 1)[1]  # type: ignore
        else:
            self.model_id = self.full_model_name

        self.region = os.getenv("BEDROCK_REGION", "us-east-1")

        # Pass the secret key as a Bearer token — this goes through the proxy gateway
        # which handles auth. Do NOT set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY here
        # as that would cause boto3 to do direct SigV4-signed requests to
        # bedrock-runtime.amazonaws.com instead of the intended Bearer-token proxy.
        api_key = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            logger.info(
                f"Initializing ChatBedrockConverse | Model: {self.model_id} | Region: {self.region} | max_tokens: {self._max_tokens} | temperature: {temp}"
            )
            self.llm = ChatBedrockConverse(
                model=self.model_id,
                region_name=self.region,
                default_headers=headers,
                max_tokens=self._max_tokens,
                temperature=temp,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatBedrockConverse: {e!s}")
            raise

    def _extract_json_from_text(self, content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None

        # Strip <think>...</think> blocks if present
        content_clean = re.sub(
            r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        # If <think> was unclosed due to truncation, strip from <think> to the first '{'
        if "<think>" in content_clean:
            first_brace = content_clean.find("{")
            if first_brace != -1 and first_brace > content_clean.find("<think>"):
                content_clean = (
                    content_clean[: content_clean.find("<think>")]
                    + content_clean[first_brace:]
                )
            else:
                content_clean = re.sub(
                    r"<think>.*$", "", content_clean, flags=re.DOTALL | re.IGNORECASE
                )

        def try_parse(s: str) -> Optional[Dict[str, Any]]:
            try:
                # Remove JS/SQL style inline comments inside JSON
                s_clean = re.sub(r"^\s*//.*$", "", s, flags=re.MULTILINE)
                s_clean = re.sub(r"/\*.*?\*/", "", s_clean, flags=re.DOTALL)
                # Remove trailing commas
                s_clean = re.sub(r",\s*([\]\}])", r"\1", s_clean.strip())
                res = json.loads(s_clean, strict=False)
                if isinstance(res, dict):
                    return res
                return None
            except Exception:
                return None

        # 1. Check markdown code blocks
        json_match = re.search(
            r"```(?:json)?\s*(.*?)\s*```", content_clean, re.DOTALL | re.IGNORECASE
        )
        if json_match:
            p = try_parse(json_match.group(1))
            if p is not None:
                return p

        # 2. Industry standard: find outermost { and }
        start_idx = content_clean.find("{")
        end_idx = content_clean.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            outer_cand = content_clean[start_idx : end_idx + 1]
            p = try_parse(outer_cand)
            if p is not None:
                return p

        # 3. Fallback scan ALL opening braces
        idx = 0
        while idx < len(content_clean):
            start_idx = content_clean.find("{", idx)
            if start_idx == -1:
                break

            brace_count = 0
            for j in range(start_idx, len(content_clean)):
                if content_clean[j] == "{":
                    brace_count += 1
                elif content_clean[j] == "}":
                    brace_count -= 1
                if brace_count == 0:
                    cand = content_clean[start_idx : j + 1]
                    p = try_parse(cand)
                    if p is not None:
                        return p
                    break
            idx = start_idx + 1

        # 4. Truncation recovery at token limits
        start_idx = content_clean.find("{")
        if start_idx != -1:
            cut_off = content_clean[start_idx:].strip()
            for suffix in ("}", '"}', '""}', "]\n}", '"]\n}', '"""]\n}'):
                p = try_parse(cut_off + suffix)
                if p is not None:
                    return p

        return None

    def generate_json(
        self, system_prompt: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        """
        Sends a prompt and extracts JSON from the response.
        """
        json_enforcer = "\n\nCRITICAL MANDATORY INSTRUCTION: You MUST format your entire response as pure valid JSON inside ```json ... ```. You MUST start your response directly with ```json\n{\n... without any introductory text, conversational preamble, or thinking process outside the JSON block."
        sys_enforced = (
            system_prompt + json_enforcer
            if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt
            else system_prompt
        )

        content = self.generate(sys_enforced, user_prompt)
        res = self._extract_json_from_text(content)
        if res is not None:
            return res

        logger.error(f"JSON Parsing Failed. Raw content:\n{content}")
        return None

    def generate_structured(
        self, system_prompt: str, user_prompt: str, response_model: Type[T]
    ) -> T:
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

        sys_enforced = (
            system_prompt + json_enforcer
            if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt
            else system_prompt
        )

        raw_content = self.generate(sys_enforced, user_prompt)
        data = self._extract_json_from_text(raw_content)

        if not data:
            logger.warning(
                f"Initial JSON generation failed for {response_model.__name__}. Executing self-repair retry..."
            )
            repair_prompt = user_prompt + (
                "\n\n[SYSTEM REPAIR NOTICE]: Your previous response failed to parse as valid JSON. "
                "This usually happens when your internal <think> scratchpad gets stuck in repetitive item-by-item verification loops, causing token truncation before the JSON object can be output. "
                "On this retry, you MUST keep your <think> reasoning extremely brief (under 300 tokens) and focus entirely on generating the complete valid JSON object inside ```json ... ``` before running out of tokens."
            )
            raw_content2 = self.generate(sys_enforced, repair_prompt)
            data = self._extract_json_from_text(raw_content2)
            if not data:
                logger.error(
                    f"JSON Parsing Failed after self-repair retry. Raw content:\n{raw_content2}"
                )
                raise ValueError(
                    f"Failed to generate valid JSON for {response_model.__name__} after self-repair retry."
                )

        try:
            return response_model.model_validate(data)
        except Exception as e:
            logger.warning(
                f"Pydantic Validation Failed for {response_model.__name__}: {e!s}. Attempting self-repair retry..."
            )
            repair_prompt = (
                user_prompt
                + f"\n\n[SYSTEM REPAIR NOTICE]: Your previous JSON failed schema validation with error: {e!s}.\nData parsed was:\n{json.dumps(data, indent=2)}\n\nYou MUST correct this and return ONLY valid JSON matching the exact schema."
            )
            raw_content2 = self.generate(sys_enforced, repair_prompt)
            data2 = self._extract_json_from_text(raw_content2)
            if not data2:
                raise e
            try:
                return response_model.model_validate(data2)
            except Exception as e2:
                logger.error(
                    f"Pydantic Validation Failed on retry for {response_model.__name__}: {e2!s}"
                )
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
                        rc_text = (
                            rc["text"]
                            if isinstance(rc, dict) and "text" in rc
                            else str(rc)
                        )
                        parts.append(f"<think>\n{rc_text}\n</think>\n")
                else:
                    parts.append(str(block))
            final_str = "\n".join(parts).strip()
        else:
            final_str = str(content).strip()

        in_t, out_t = 0, 0
        cache_creation, cache_read = 0, 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            in_t = response.usage_metadata.get("input_tokens", 0)
            out_t = response.usage_metadata.get("output_tokens", 0)
            cache_creation = response.usage_metadata.get("cache_creation_input_tokens", 0) or response.usage_metadata.get("cache_creation_tokens", 0) or 0
            cache_read = response.usage_metadata.get("cache_read_input_tokens", 0) or response.usage_metadata.get("cache_read_tokens", 0) or 0
        elif (
            hasattr(response, "response_metadata")
            and "usage" in response.response_metadata
        ):
            u = response.response_metadata["usage"]
            in_t = u.get("inputTokens", u.get("input_tokens", 0))
            out_t = u.get("outputTokens", u.get("output_tokens", 0))
            cache_creation = u.get("cache_creation_input_tokens", u.get("cache_creation_tokens", 0)) or 0
            cache_read = u.get("cache_read_input_tokens", u.get("cache_read_tokens", 0)) or 0

        if cache_read > 0 or cache_creation > 0:
            logger.info(f"[ContextCaching] Input: {in_t} | Cache Read: {cache_read} | Cache Creation: {cache_creation}")
        return final_str, in_t, out_t

    def generate(self, system_prompt: str, user_prompt: str, component: Optional[str] = None) -> str:
        """Simple text completion with exponential-backoff retry on transient Bedrock errors."""
        try:
            from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
            if DAB_CANCEL_FLAG or SPIDER_CANCEL_FLAG:
                raise KeyboardInterrupt("Run stopped by user")
        except Exception:
            pass

        # Block (not raise) until the circuit breaker clears or patience runs out.
        # This keeps the pipeline thread alive so the log keeps accumulating.
        _cb_wait_until_clear()

        # Hard safety cap: model context window is 131 072 tokens.
        # gpt-oss-safeguard-120b tokenises at ~2.48 chars/token, so:
        #   131 072 tokens × 2.48 = 325 058 chars max total.
        # Reserve ~12 000 tokens (≈29 760 chars) for response + system overhead,
        # leaving 280 000 chars as a safe combined cap.
        _MAX_PROMPT_CHARS = 280_000
        total_chars = len(system_prompt) + len(user_prompt)
        if total_chars > _MAX_PROMPT_CHARS:
            _keep = _MAX_PROMPT_CHARS - len(system_prompt)
            _head = _keep * 2 // 3
            _tail = _keep - _head
            user_prompt = (
                user_prompt[:_head]
                + f"\n\n[... {total_chars - _MAX_PROMPT_CHARS} chars truncated to fit context window ...]\n\n"
                + user_prompt[-_tail:]
            )
            logger.warning(
                f"[LLM] Prompt truncated: total {total_chars} chars exceeded {_MAX_PROMPT_CHARS} cap. "
                f"Kept {_head} head + {_tail} tail of user prompt."
            )

        logger.debug(
            f"LLM Prompt lengths | System: {len(system_prompt)} | User: {len(user_prompt)}"
        )

        # Bedrock prompt caching — models list is configurable in system_params.yaml (llm.prompt_caching_models)
        use_cache = len(system_prompt) > 4000 and any(m in self.model_id.lower() for m in self._caching_models)

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                if use_cache:
                    system_content = [
                        {"type": "text", "text": system_prompt},
                        {"cachePoint": {"type": "default"}}
                    ]
                else:
                    system_content = system_prompt

                messages = [
                    SystemMessage(content=system_content),
                    HumanMessage(content=user_prompt),
                ]

                response = self.llm.invoke(messages)
                final_str, in_t, out_t = self._parse_response(response)
                add_tokens(in_t, out_t, component=component)
                metrics = {"input_tokens": in_t, "output_tokens": out_t}
                full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
                agent_name = getattr(logger.logger, "name", "AGENT")
                logger.log_agent_call(agent_name, full_prompt, final_str, metrics)
                _cb_record_success()
                return final_str
            except Exception as e:
                # Failsafe: if cachePoint fails (e.g. parameter validation error), retry immediately without caching
                if use_cache:
                    logger.warning(f"Bedrock prompt caching failed: {e}. Retrying this attempt without cachePoint failsafe...")
                    use_cache = False
                    try:
                        messages = [
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=user_prompt),
                        ]
                        response = self.llm.invoke(messages)
                        final_str, in_t, out_t = self._parse_response(response)
                        add_tokens(in_t, out_t)
                        metrics = {"input_tokens": in_t, "output_tokens": out_t}
                        full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
                        agent_name = getattr(logger.logger, "name", "AGENT")
                        logger.log_agent_call(agent_name, full_prompt, final_str, metrics)
                        _cb_record_success()
                        return final_str
                    except Exception as fallback_e:
                        e = fallback_e

                last_exc = e
                if self._is_retryable(e) and attempt < self._max_retries:
                    delay = min(self._retry_base_delay * (2**attempt), 120.0)
                    logger.warning(
                        f"[LLM] Transient Bedrock error (attempt {attempt + 1}/{self._max_retries + 1}): "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    break
        if last_exc:
            if self._is_retryable(last_exc):
                _cb_record_failure()
            logger.error(
                f"[LLM] generate() exhausted {self._max_retries} retries: "
                f"{type(last_exc).__name__}: {last_exc}"
            )
            raise last_exc
        return ""

    async def agenerate_structured(
        self, system_prompt: str, user_prompt: str, response_model: Type[T]
    ) -> T:
        """
        Async version of generate_structured. Uses agenerate (ainvoke) internally so
        the event loop is never blocked by Bedrock I/O. Drop-in async replacement.
        """
        try:
            schema_str = SchemaCompactor.compact_json_schema(response_model)
        except Exception:
            schema_str = "Required fields and types matching " + response_model.__name__

        json_enforcer = (
            f"\n\nCRITICAL MANDATORY INSTRUCTION: You MUST format your entire output EXACTLY as pure valid JSON enclosed in ```json ... ``` adhering to this minimal JSON skeleton structure:\n```json\n{schema_str}\n```\n\n"
            "You MUST start your JSON response directly with ```json\n{\n... without any introductory text outside the JSON block. "
            "IMPORTANT FOR REASONING MODELS: If you use a <think> scratchpad, you MUST keep your internal thinking concise and summarized under 500 tokens. "
            "Do NOT engage in repetitive item-by-item loops. "
            "Exhaustive repetitive loops will cause token truncation before the JSON is generated, resulting in system failure."
        )
        sys_enforced = (
            system_prompt + json_enforcer
            if "CRITICAL MANDATORY INSTRUCTION" not in system_prompt
            else system_prompt
        )

        raw_content = await self.agenerate(sys_enforced, user_prompt)
        data = self._extract_json_from_text(raw_content)

        if not data:
            logger.warning(
                f"Async initial JSON generation failed for {response_model.__name__}. Executing self-repair retry..."
            )
            repair_prompt = user_prompt + (
                "\n\n[SYSTEM REPAIR NOTICE]: Your previous response failed to parse as valid JSON. "
                "Keep your <think> reasoning extremely brief (under 300 tokens) and output the complete valid JSON object inside ```json ... ```."
            )
            raw_content2 = await self.agenerate(sys_enforced, repair_prompt)
            data = self._extract_json_from_text(raw_content2)
            if not data:
                raise ValueError(
                    f"Async: Failed to generate valid JSON for {response_model.__name__} after self-repair retry."
                )

        try:
            return response_model.model_validate(data)
        except Exception as e:
            logger.warning(
                f"Async Pydantic Validation Failed for {response_model.__name__}: {e!s}. Attempting self-repair retry..."
            )
            repair_prompt = (
                user_prompt
                + f"\n\n[SYSTEM REPAIR NOTICE]: Your previous JSON failed schema validation with error: {e!s}.\nData parsed was:\n{json.dumps(data, indent=2)}\n\nYou MUST correct this and return ONLY valid JSON matching the exact schema."
            )
            raw_content2 = await self.agenerate(sys_enforced, repair_prompt)
            data2 = self._extract_json_from_text(raw_content2)
            if not data2:
                raise e
            try:
                return response_model.model_validate(data2)
            except Exception as e2:
                logger.error(f"Async Pydantic Validation Failed on retry for {response_model.__name__}: {e2!s}")
                raise e2

    async def agenerate(self, system_prompt: str, user_prompt: str, component: Optional[str] = None) -> str:
        """Asynchronous text completion with exponential-backoff retry."""
        try:
            from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
            if DAB_CANCEL_FLAG or SPIDER_CANCEL_FLAG:
                raise KeyboardInterrupt("Run stopped by user")
        except Exception:
            pass

        import asyncio
        # Async-safe CB wait: poll with asyncio.sleep so the event loop stays free.
        _waited = 0.0
        while _cb_is_open():
            if _waited >= CB_MAX_WAIT_S:
                raise RuntimeError(
                    f"LLM circuit breaker remained open for {CB_MAX_WAIT_S:.0f}s. "
                    "Giving up on this query."
                )
            _sleep = min(CB_RESET_AFTER_S + 5, CB_MAX_WAIT_S - _waited)
            logger.warning(
                f"[CircuitBreaker] async path — Bedrock unreachable, "
                f"sleeping {_sleep:.0f}s (waited {_waited:.0f}s so far) ..."
            )
            await asyncio.sleep(_sleep)
            _waited += _sleep

        _MAX_PROMPT_CHARS = 280_000
        total_chars = len(system_prompt) + len(user_prompt)
        if total_chars > _MAX_PROMPT_CHARS:
            _keep = _MAX_PROMPT_CHARS - len(system_prompt)
            _head = _keep * 2 // 3
            _tail = _keep - _head
            user_prompt = (
                user_prompt[:_head]
                + f"\n\n[... {total_chars - _MAX_PROMPT_CHARS} chars truncated to fit context window ...]\n\n"
                + user_prompt[-_tail:]
            )
            logger.warning(
                f"[LLM] Prompt truncated (async): total {total_chars} chars exceeded {_MAX_PROMPT_CHARS} cap."
            )

        logger.debug(f"LLM Prompt lengths | System: {len(system_prompt)} | User: {len(user_prompt)}")

        # Bedrock prompt caching — models list is configurable in system_params.yaml (llm.prompt_caching_models)
        use_cache = len(system_prompt) > 4000 and any(m in self.model_id.lower() for m in self._caching_models)

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                if use_cache:
                    system_content = [
                        {"type": "text", "text": system_prompt},
                        {"cachePoint": {"type": "default"}}
                    ]
                else:
                    system_content = system_prompt

                messages = [
                    SystemMessage(content=system_content),
                    HumanMessage(content=user_prompt),
                ]

                response = await self.llm.ainvoke(messages)
                final_str, in_t, out_t = self._parse_response(response)
                add_tokens(in_t, out_t, component=component)
                metrics = {"input_tokens": in_t, "output_tokens": out_t}
                full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
                agent_name = getattr(logger.logger, "name", "AGENT")
                logger.log_agent_call(agent_name, full_prompt, final_str, metrics)
                _cb_record_success()
                return final_str
            except Exception as e:
                # Failsafe: if cachePoint fails, retry immediately without caching
                if use_cache:
                    logger.warning(f"Bedrock async prompt caching failed: {e}. Retrying this attempt without cachePoint failsafe...")
                    use_cache = False
                    try:
                        messages = [
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=user_prompt),
                        ]
                        response = await self.llm.ainvoke(messages)
                        final_str, in_t, out_t = self._parse_response(response)
                        add_tokens(in_t, out_t)
                        metrics = {"input_tokens": in_t, "output_tokens": out_t}
                        full_prompt = f"=== SYSTEM PROMPT ===\n{system_prompt}\n\n=== USER PROMPT ===\n{user_prompt}"
                        agent_name = getattr(logger.logger, "name", "AGENT")
                        logger.log_agent_call(agent_name, full_prompt, final_str, metrics)
                        _cb_record_success()
                        return final_str
                    except Exception as fallback_e:
                        e = fallback_e

                last_exc = e
                if self._is_retryable(e) and attempt < self._max_retries:
                    delay = min(self._retry_base_delay * (2**attempt), 120.0)
                    logger.warning(
                        f"[LLM] Transient Bedrock error async (attempt {attempt + 1}/{self._max_retries + 1}): "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    break
        if last_exc:
            if self._is_retryable(last_exc):
                _cb_record_failure()
            logger.error(
                f"[LLM] agenerate() exhausted {self._max_retries} retries: "
                f"{type(last_exc).__name__}: {last_exc}"
            )
            raise last_exc
        return ""
