import logging
import os
import threading
import re
from collections.abc import Callable

from .config import get_settings


class Logger:
    """
    Standardized logging service for the Text2SQL pipeline.
    Uses buffered file handling for performance and thread safety.
    STRICT ASCII-ONLY FOR PRODUCTION DIAGNOSTICS.
    """

    _current_log_file: str | None = None
    _listeners: list[Callable[[str, str], None]] = []
    _capture_buffer: list[str] | None = None
    _lock = threading.Lock()
    _internal_logger = logging.getLogger("tt_sql")

    _silence_file_during_capture: bool = False

    @classmethod
    def start_capture(cls, silence_file: bool = True):
        """Starts capturing logs. If silence_file is True, logs skip the .md file while buffering."""
        with cls._lock:
            cls._capture_buffer = []
            cls._silence_file_during_capture = silence_file

    @classmethod
    def stop_capture(cls) -> str:
        """Stops capturing and restores normal logging."""
        with cls._lock:
            if cls._capture_buffer is None:
                return ""
            logs = "\n\n".join(cls._capture_buffer)
            cls._capture_buffer = None
            cls._silence_file_during_capture = False
            return logs

    @classmethod
    def reset(cls):
        """Resets the logger state, clearing listeners and log file path."""
        with cls._lock:
            cls._listeners = []
            cls._current_log_file = None
            # Clear handlers from internal logger
            for handler in cls._internal_logger.handlers[:]:
                cls._internal_logger.removeHandler(handler)

    @classmethod
    def register_listener(cls, listener: Callable[[str, str], None]):
        """Registers a callback for log events (e.g. for UI updates)."""
        with cls._lock:
            cls._listeners.append(listener)

    @classmethod
    def set_log_file(cls, path: str):
        """Sets the active log file and initializes the buffered handlers."""
        with cls._lock:
            cls._current_log_file = path
            # Remove old handlers
            for handler in cls._internal_logger.handlers[:]:
                cls._internal_logger.removeHandler(handler)

            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # 1. Buffered File Handler (The modular .md file)
            f_handler = logging.FileHandler(path, mode="w", encoding="utf-8")
            # For the .md file, we use a clean formatter WITHOUT timestamps
            formatter = logging.Formatter("%(message)s")
            f_handler.setFormatter(formatter)
            cls._internal_logger.addHandler(f_handler)

            # 2. Live Console Handler (Terminal output with timestamps)
            c_handler = logging.StreamHandler()
            c_formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            c_handler.setFormatter(c_formatter)
            cls._internal_logger.addHandler(c_handler)

            cls._internal_logger.setLevel(get_settings().LOG_LEVEL)

    @classmethod
    def log(cls, message: str, level: str = "INFO", to_file: bool = True):
        """Logs a message to the active file (optional) and console.
        Performs ASCII-only sanitization before output.
        """
        # --- ASCII SANITIZATION ---
        replacements = {
            "→": "->", "💎": "-", "✨": "-", "📊": "RESULT",
            "🎉": "SUCCESS", "⚡": "CALL", "❌": "ERROR",
            "🔴": "[TRUNCATED]", "🟢": "[OK]", "💡": "INFO",
            "📦": "DATA", "📝": "RESPONSE", "🎯": "RESULT",
            "🔍": "AUDIT", "🟡": "[WARN]", "🛑": "STOP",
            "🚀": "START", "✅": "PASS", "⌛": "TIME",
            "📋": "LIST", "🧪": "TEST"
        }
        sanitized = message
        for emoji, text in replacements.items():
            sanitized = sanitized.replace(emoji, text)
        
        # Remove any remaining non-ASCII
        sanitized = re.sub(r'[^\x00-\x7F]+', '?', sanitized)

        with cls._lock:
            # 1. Capture logic (always capture if active)
            if cls._capture_buffer is not None:
                cls._capture_buffer.append(sanitized)
                if cls._silence_file_during_capture:
                    to_file = False

            # --- CONSOLE/FILE ROUTING ---
            if not to_file:
                # Still notify listeners
                for listener in cls._listeners:
                    listener(sanitized, level)
                return

            # Standard path (File + Console)
            try:
                if level.upper() == "ERROR":
                    cls._internal_logger.error(sanitized)
                elif level.upper() == "WARN":
                    cls._internal_logger.warning(sanitized)
                else:
                    cls._internal_logger.info(sanitized)
            except:
                pass

            # 3. Notify Listeners
            for listener in cls._listeners:
                try:
                    listener(sanitized, level)
                except Exception:
                    pass

    @classmethod
    def log_section(cls, title: str, iteration: int = None):
        """Standard modular section header."""
        header = title.upper()
        if iteration is not None:
            header += f" (Iteration {iteration})"
        cls.log(f"\n\n----------\n{header}\n----------\n")

    @classmethod
    def log_stage_header(cls, title: str, iteration: int = None):
        cls.log_section(title, iteration=iteration)

    @classmethod
    def log_agent_block(cls, name: str, inputs: list[dict], result: str, status: str = "success", prompt: str = None, metrics: dict = None, iteration: int = None):
        cls.log_section(name, iteration=iteration)
        cls.log("Inputs/input_prompts:")
        for i, inp in enumerate(inputs):
            desc = inp.get("desc", "N/A")
            stat = inp.get("status", "found")
            cls.log(f"  {i+1}. {desc} (status: {stat})")
        
        if metrics:
            inp_t = metrics.get("input", 0)
            out_t = metrics.get("output", 0)
            max_t = metrics.get("max", 0)
            stop = metrics.get("stop", "n/a")
            is_truncated = (stop == "length" or (max_t > 0 and out_t >= max_t))
            flag = "[TRUNCATED]" if is_truncated else "[OK]"
            
            cls.log(f"\n> [!NOTE]\n> **Token Usage**: {flag}\n> - **Prompt**: {inp_t} tokens\n> - **Response**: {out_t} / {max_t} tokens limit\n> - **Stop Reason**: `{stop}`")

        if prompt:
            cls.log("\n<details><summary><b>View Rendered Prompt</b></summary>\n")
            cls.log(f"```markdown\n{prompt}\n```")
            cls.log("\n</details>\n")
        
        cls.log(f"\nResponse/Result:\n\n{result}")
        cls.log(f"\nStatus: {status}\n")

    @classmethod
    def log_final_results(cls, sql: str, csv_path: str, result=None):
        cls.log_section("Result (Final SQL)")
        cls.log(f"```sql\n{sql}\n```")
        
        cls.log_section("Result (Final csv)")
        cls.log(f"Output saved to: `{csv_path}`")
        
        if result and result.rows:
            cls.log("\n### SAMPLE OUTPUT (Top 5)")
            cols = " | ".join([f"**{str(c)}**" for c in result.columns or []])
            if cols:
                cls.log(f"| {cols} |")
                cls.log(f"| {'--- | ' * len(result.columns)}")
                for row in result.rows[:5]: 
                    r_str = " | ".join([str(v).replace('\n', ' ') for v in row])
                    cls.log(f"| {r_str} |")
                if result.row_count > 5:
                    cls.log(f"\n_... and {result.row_count - 5} more rows._")
        elif result and result.error_message:
             cls.log(f"\n> [!ERROR]\n> **Execution Failed**: {result.error_message}")

    @classmethod
    def log_metrics(cls, elapsed: float, llm_calls: int, agent_metrics: dict = None):
        cls.log_section("Metrics")
        cls.log(f"Elapsed time: {elapsed:.2f}s")
        
        # Calculate total calls from breakdown if provided to ensure they match exactly
        total_calls = llm_calls
        if agent_metrics:
            total_calls = sum(data.get("calls", 0) for data in agent_metrics.values())
        
        cls.log(f"Total LLM calls: {total_calls}")
        
        if agent_metrics:
            cls.log("\n### AGENT BREAKDOWN")
            for agent, data in agent_metrics.items():
                calls = data.get("calls", 0)
                tokens = data.get("tokens", [])
                cls.log(f"\n{agent}")
                cls.log(f" - Total LLM calls: {calls}")
                if tokens:
                    cls.log(f" - Tokens {tokens}")

    @classmethod
    def log_divider(cls):
        cls.log("\n---\n")

    @classmethod
    def log_code(cls, code: str, language: str = "sql", to_file: bool = True):
        cls.log(f"\n```{language}\n{code}\n```\n", to_file=to_file)

    @classmethod
    def log_step(cls, step_name: str, status: str, details: str = None):
        msg = f"\n[{step_name}] {status}"
        if details:
            msg += f" ({details})"
        cls.log(msg + "\n")

    @classmethod
    def log_state(cls, old_state: str, new_state: str):
        cls.log(f"\n[STATE] {old_state} -> {new_state}\n")

    @classmethod
    def log_error(cls, error: str):
        cls.log(f"\n> [!CAUTION]\n> ### ERROR\n> {error}\n")

    @classmethod
    def log_completion(cls, status: str):
        cls.log("\n" + "-" * 30)
        cls.log(f"# PIPELINE {status.upper()}")
        cls.log("-" * 30 + "\n")

    @classmethod
    def log_call(cls, target: str, params: dict = None):
        try:
            msg = f"CALL: {target}"
            cls._internal_logger.debug(msg) 
        except: pass

    @classmethod
    def log_execution(cls, sql: str, result):
        cls.log("\n" + "=" * 30)
        cls.log("### SQL EXECUTION AUDIT")
        cls.log("=" * 30)
        
        if len(sql) > 500:
            cls.log(f"<details><summary><b>View SQL Statement</b></summary>\n\n```sql\n{sql}\n```\n</details>")
        else:
            cls.log(f"#### SQL QUERY:\n```sql\n{sql}\n```")
        
        if result.error_message:
            cls.log(f"\n> [!ERROR]\n> **Execution Failed**: {result.error_message}")
        else:
            cls.log(f"\n> [!IMPORTANT]\n> **SUCCESS**: {result.row_count} rows retrieved.")
            if result.rows:
                cls.log("\n#### SAMPLE DATA:")
                cols = " | ".join([f"**{str(c)}**" for c in result.columns])
                cls.log(f"| {cols} |")
                cls.log(f"| {'--- | ' * len(result.columns)}")
                for row in result.rows[:5]: 
                    r_str = " | ".join([str(v).replace('\n', ' ') for v in row])
                    cls.log(f"| {r_str} |")
        cls.log("\n" + "-" * 40 + "\n")

    @classmethod
    def log_status_banner(cls, component: str, success: bool, message: str = ""):
        status = "PASSED" if success else "FAILED"
        banner_msg = f"{component.upper()}: {status}"
        cls.log("\n" + "=" * 35)
        cls.log(f" {banner_msg.center(33)} ")
        if message:
            cls.log(f" - {message[:60].center(31)} ")
        cls.log("=" * 35 + "\n")

    @classmethod
    def log_pipeline_status(cls, success: bool, reason: str = None, sql: str = None, preview: str = None):
        """Final pipeline output contract."""
        if success:
            cls.log("[PIPELINE] SUCCESS")
            cls.log(f"* Final SQL: {sql}")
            cls.log(f"* Result preview: {preview}")
        else:
            cls.log("[PIPELINE] FAILED")
            cls.log(f"* Reason: {reason}")
