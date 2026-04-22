import os
import threading
from pathlib import Path

class Logger:
    """
    Centralized logger for the Text2SQL pipeline.
    Supports both thread-local instance logs and a global master history log.
    """
    _storage = threading.local()
    _enabled = True
    _verbose = False
    _master_log_file = None

    @classmethod
    def register_listener(cls, callback):
        cls._get_listeners().append(callback)

    @classmethod
    def clear_listeners(cls):
        cls._get_listeners().clear()

    @classmethod
    def bind_log_file(cls, filename: str):
        cls._storage.log_file = os.path.abspath(filename)

    @classmethod
    def set_master_log_file(cls, filename: str):
        """Sets the global master log file path and initializes it if new."""
        cls._master_log_file = os.path.abspath(filename)
        # Only write header if file is new or empty
        if not os.path.exists(cls._master_log_file) or os.path.getsize(cls._master_log_file) == 0:
            os.makedirs(os.path.dirname(cls._master_log_file), exist_ok=True)
            with open(cls._master_log_file, "w", encoding="utf-8") as f:
                f.write("# Text2SQL Master Execution History\n\n")

    @classmethod
    def set_log_file(cls, filename: str):
        """Sets the thread-local instance log file and initializes it."""
        cls._storage.log_file = os.path.abspath(filename)
        os.makedirs(os.path.dirname(cls._storage.log_file), exist_ok=True)
        with open(cls._storage.log_file, "w", encoding="utf-8") as f:
            f.write("# Query Execution Trace\n\n")

    _write_lock = threading.Lock()

    @classmethod
    def _write_to_files(cls, content: str):
        """Internal helper to write to both available log targets with thread safety."""
        with cls._write_lock:
            # 1. Write to instance log
            instance_log = cls._get_log_file()
            try:
                with open(instance_log, "a", encoding="utf-8") as f:
                    f.write(content)
            except Exception: pass
            
            # 2. Write to master log
            if cls._master_log_file:
                try:
                    with open(cls._master_log_file, "a", encoding="utf-8") as f:
                        f.write(content)
                except Exception: pass

    @classmethod
    def log(cls, message: str, level: str = "INFO", agent_name: str = None):
        if not cls._enabled: return
        import datetime
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        
        if cls._verbose:
            level_color = cls.COLORS.get(level.upper(), cls.COLORS["RESET"])
            try: print(f"[{timestamp}] {level_color}[{level}]{cls.COLORS['RESET']} {message}", flush=True)
            except: pass
            
        color = cls.MD_COLORS.get(level.upper(), "black")
        display_message = f"[{agent_name}]: {message}" if agent_name else message
        
        entry = f"- **[{timestamp}]** <font color=\"{color}\">**[{level}]**</font> {display_message}\n"
        cls._write_to_files(entry)
        
        for listener in cls._get_listeners():
            if callable(listener):
                try: listener(message, "log", level)
                except: pass

    @classmethod
    def log_section(cls, title: str):
        cls._write_to_files(f"\n### {title}\n")
        for listener in cls._get_listeners():
            if callable(listener):
                try: listener(title, "section", "INFO")
                except: pass

    @classmethod
    def log_divider(cls):
        cls._write_to_files("\n" + "-" * 50 + "\n" + "-" * 50 + "\n\n")

    @classmethod
    def log_stage_header(cls, title: str):
        entry = "\n" + "-" * 50 + "\n" + f"## {title}\n" + "-" * 50 + "\n\n"
        cls._write_to_files(entry)
        cls.log_section(title)

    @classmethod
    def log_title(cls, title: str):
        cls._write_to_files(f"\n{title}\n")
        for listener in cls._get_listeners():
            if callable(listener):
                try: listener(title, "title", "INFO")
                except: pass

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        entry = f"```{language}\n{code}\n```\n\n"
        cls._write_to_files(entry)
        for listener in cls._get_listeners():
            if callable(listener):
                try: listener(code, "code", "INFO")
                except: pass

    # --- Private Methods & Constants ---

    COLORS = {"DEBUG": "\033[94m", "INFO": "\033[92m", "WARNING": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    MD_COLORS = {"DEBUG": "blue", "INFO": "green", "WARNING": "orange", "ERROR": "red"}

    @classmethod
    def _get_listeners(cls):
        if not hasattr(cls._storage, "listeners"): cls._storage.listeners = []
        return cls._storage.listeners

    @classmethod
    def _get_log_file(cls):
        if not hasattr(cls._storage, "log_file"):
            import tempfile
            cls._storage.log_file = str(Path(tempfile.gettempdir()) / "nquire_execution.log")
        return cls._storage.log_file

