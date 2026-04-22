import os
import threading
import logging
from typing import List, Optional, Callable
from .config import get_settings

class Logger:
    """
    Standardized logging service for the Text2SQL pipeline.
    Uses buffered file handling for performance and thread safety.
    """
    _current_log_file: Optional[str] = None
    _listeners: List[Callable[[str, str], None]] = []
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
        """Sets the active log file and initializes the buffered file handler."""
        with cls._lock:
            cls._current_log_file = path
            # Remove old file handlers
            for handler in cls._internal_logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    cls._internal_logger.removeHandler(handler)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Set up new buffered file handler
            handler = logging.FileHandler(path, mode='w', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            cls._internal_logger.addHandler(handler)
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
        """Logs a major section header in markdown."""
        cls.log(f"\n## 📥 {title.upper()}\n")

    @classmethod
    def log_title(cls, title: str):
        """Logs a major title (Deprecated: use log_section)."""
        cls.log_section(title)

    @classmethod
    def log_stage_header(cls, stage: str):
        """Logs a highlighted stage header."""
        cls.log(f"\n### 🛠️ STAGE: {stage.upper()}\n")

    @classmethod
    def log_divider(cls):
        """Logs a markdown horizontal rule."""
        cls.log("\n---\n")

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        """Logs a formatted code block in markdown."""
        cls.log(f"\n```{language}\n{code}\n```\n")

    @classmethod
    def log_step(cls, step: str):
        """Logs a step with an icon."""
        cls.log(f"✅ **{step}**")

    @classmethod
    def log_error(cls, error: str):
        """Logs an error block with a callout."""
        cls.log(f"\n> [!CAUTION]\n> **ERROR**: {error}\n")

    @classmethod
    def log_completion(cls, status: str):
        """Logs the final completion state."""
        cls.log(f"\n# 🏁 PIPELINE {status.upper()}\n")
