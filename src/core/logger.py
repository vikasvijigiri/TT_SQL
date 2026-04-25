import logging
import os
import threading
from collections.abc import Callable

from .config import get_settings


class Logger:
    """
    Standardized logging service for the Text2SQL pipeline.
    Uses buffered file handling for performance and thread safety.
    """

    _current_log_file: str | None = None
    _listeners: list[Callable[[str, str], None]] = []
    _lock = threading.Lock()
    _internal_logger = logging.getLogger("tt_sql")

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

            # 1. Buffered File Handler
            f_handler = logging.FileHandler(path, mode="w", encoding="utf-8")
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            f_handler.setFormatter(formatter)
            cls._internal_logger.addHandler(f_handler)

            # 2. Live Console Handler (Always mirror to terminal)
            c_handler = logging.StreamHandler()
            c_handler.setFormatter(formatter)
            cls._internal_logger.addHandler(c_handler)

            cls._internal_logger.setLevel(get_settings().LOG_LEVEL)

    @classmethod
    def log(cls, message: str, level: str = "INFO"):
        """Logs a message to the active file and all listeners."""
        with cls._lock:
            # 1. Internal Logger (buffered file I/O)
            if level.upper() == "ERROR":
                cls._internal_logger.error(message)
            elif level.upper() == "WARN":
                cls._internal_logger.warning(message)
            elif level.upper() == "DEBUG":
                cls._internal_logger.debug(message)
            else:
                cls._internal_logger.info(message)

            # 2. Notify Listeners
            for listener in cls._listeners:
                try:
                    listener(message, level)
                except Exception:
                    pass

    @classmethod
    def log_section(cls, title: str):
        """Minimal section header."""
        cls.log(f"\n## 🏛️ {title.upper()}\n")

    @classmethod
    def log_stage_header(cls, title: str):
        """Minimal stage header."""
        cls.log(f"\n### ⚙️ {title.upper()}\n")

    @classmethod
    def log_divider(cls):
        """Minimal divider."""
        cls.log("\n---\n")

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        """Logs a formatted code block in markdown with extra padding."""
        cls.log(f"\n```{language}\n{code}\n```\n")

    @classmethod
    def log_step(cls, step: str):
        """Logs a step with an icon and bolding."""
        cls.log(f"📌 **{step}**")

    @classmethod
    def log_error(cls, error: str):
        """Logs an error block with a prominent caution callout."""
        cls.log(f"\n> [!CAUTION]\n> ### ❌ **ERROR**\n> {error}\n")

    @classmethod
    def log_completion(cls, status: str):
        """Logs the final completion state with a celebratory banner."""
        cls.log("\n" + "💎" * 30)
        cls.log(f"# 🎉 PIPELINE {status.upper()}")
        cls.log("💎" * 30 + "\n")

    @classmethod
    def log_call(cls, target: str, params: dict = None):
        """Logs a trace entry for function/agent execution (Collapsed)."""
        if params:
            cls.log(f"<details><summary>⚡ <b>[CALL]</b>: <code>{target}</code></summary>\n\n  * _parameters_: `{params}`\n\n</details>")
        else:
            cls.log(f"⚡ **[CALL]**: `{target}`")

    @classmethod
    def log_execution(cls, sql: str, result):
        """Logs the execution result with premium demarcation."""
        cls.log("\n" + "✨" * 30)
        cls.log("### 📊 SQL EXECUTION AUDIT")
        cls.log("✨" * 30)
        
        # SQL with collapsible option if too long
        if len(sql) > 500:
            cls.log(f"<details><summary><b>View SQL Statement</b></summary>\n\n```sql\n{sql}\n```\n</details>")
        else:
            cls.log(f"#### 🔍 SQL QUERY:\n```sql\n{sql}\n```")
        
        if result.error_message:
            cls.log(f"\n> [!ERROR]\n> **Execution Failed**: {result.error_message}")
        else:
            cls.log(f"\n> [!IMPORTANT]\n> **SUCCESS**: {result.row_count} rows retrieved.")
            if result.rows:
                cls.log("\n#### 📋 SAMPLE DATA:")
                # Prepare markdown table
                cols = " | ".join([f"**{str(c)}**" for c in result.columns])
                cls.log(f"| {cols} |")
                cls.log(f"| {'--- | ' * len(result.columns)}")
                for row in result.rows[:5]: 
                    r_str = " | ".join([str(v) for v in row])
                    cls.log(f"| {r_str} |")
                if result.row_count > 5:
                    cls.log(f"\n_... and {result.row_count - 5} more rows._")
        cls.log("\n" + "―" * 40 + "\n")

    @classmethod
    def log_status_banner(cls, component: str, success: bool, message: str = ""):
        """Logs a large, color-coded status banner for a component/task."""
        char = "🟩" if success else "🟥"
        status = "PASSED" if success else "FAILED"
        banner_msg = f"{char} {component.upper()}: {status} {char}"
        
        cls.log("\n" + char * 35)
        cls.log(f"{char} {banner_msg.center(64)} {char}")
        if message:
            cls.log(f"{char} {'- ' + message[:60].center(64)} {char}")
        cls.log(char * 35 + "\n")

    @classmethod
    def log_comparison(cls, is_passed: bool):
        """Logs a large visual flag for Ground Truth comparison (Premium Style)."""
        cls.log_status_banner("GROUND TRUTH", is_passed)
