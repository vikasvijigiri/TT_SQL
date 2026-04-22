import os
import threading
from pathlib import Path
import datetime

class Logger:
    """
    Centralized logger for the Text2SQL pipeline.
    Manages thread-local instance logs and global master history.
    """
    _storage = threading.local()
    _enabled = True
    _verbose = False
    _master_log_file = None
    _write_lock = threading.Lock()

    COLORS = {"DEBUG": "\033[94m", "INFO": "\033[92m", "WARNING": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    MD_COLORS = {"DEBUG": "blue", "INFO": "green", "WARNING": "orange", "ERROR": "red"}

    @classmethod
    def register_listener(cls, callback):
        cls._get_listeners().append(callback)

    @classmethod
    def clear_listeners(cls):
        cls._get_listeners().clear()

    @classmethod
    def set_master_log_file(cls, filename: str):
        """Initializes global master log."""
        cls._master_log_file = os.path.abspath(filename)
        if not os.path.exists(cls._master_log_file) or os.path.getsize(cls._master_log_file) == 0:
            os.makedirs(os.path.dirname(cls._master_log_file), exist_ok=True)
            with open(cls._master_log_file, "w", encoding="utf-8") as f:
                f.write("# Master Execution History\n\n")

    @classmethod
    def set_log_file(cls, filename: str):
        """Initializes thread-local instance log."""
        cls._storage.log_file = os.path.abspath(filename)
        os.makedirs(os.path.dirname(cls._storage.log_file), exist_ok=True)
        with open(cls._storage.log_file, "w", encoding="utf-8") as f:
            f.write("# Query Execution Trace\n\n")

    @classmethod
    def log(cls, message: str, level: str = "INFO", agent_name: str = None):
        if not cls._enabled: return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if cls._verbose:
            print(f"[{timestamp}] {cls.COLORS.get(level.upper(), '')}[{level}]{cls.COLORS['RESET']} {message}")
            
        display_message = f"[{agent_name}]: {message}" if agent_name else message
        color = cls.MD_COLORS.get(level.upper(), "black")
        entry = f"- **[{timestamp}]** <font color=\"{color}\">**[{level}]**</font> {display_message}\n"
        
        cls._write_to_files(entry)
        for listener in cls._get_listeners():
            if callable(listener):
                listener(message, "log", level)

    @classmethod
    def log_section(cls, title: str):
        cls._write_to_files(f"\n### {title}\n")
        cls._notify_listeners(title, "section")

    @classmethod
    def log_divider(cls):
        cls._write_to_files("\n" + "-" * 50 + "\n\n")

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        cls._write_to_files(f"```{language}\n{code}\n```\n\n")
        cls._notify_listeners(code, "code")

    @classmethod
    def _write_to_files(cls, content: str):
        with cls._write_lock:
            for target in [cls._storage.log_file if hasattr(cls._storage, 'log_file') else None, cls._master_log_file]:
                if target:
                    try:
                        with open(target, "a", encoding="utf-8") as f:
                            f.write(content)
                    except Exception: pass

    @classmethod
    def _get_listeners(cls):
        if not hasattr(cls._storage, "listeners"): cls._storage.listeners = []
        return cls._storage.listeners

    @classmethod
    def _notify_listeners(cls, message, msg_type):
        for listener in cls._get_listeners():
            if callable(listener):
                listener(message, msg_type, "INFO")
