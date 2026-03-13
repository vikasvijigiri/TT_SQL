import os
import threading

class Logger:
    """
    Centralized logger for the Text2SQL pipeline.
    Uses thread-local storage to support parallel batch processing.
    """
    _storage = threading.local()
    _enabled = True
    _verbose = False

    @classmethod
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
    def set_log_file(cls, filename: str):
        cls._storage.log_file = os.path.abspath(filename)
        with open(cls._storage.log_file, "w", encoding="utf-8") as f:
            f.write("# Text2SQL Execution Log\n\n")

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
        log_file = cls._get_log_file()
        display_message = f"[{agent_name}]: {message}" if agent_name else message
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"- **[{timestamp}]** <font color=\"{color}\">**[{level}]**</font> {display_message}\n")
        except Exception: pass
        for listener in cls._get_listeners():
            try: listener(message, "log", level)
            except: pass

    @classmethod
    def log_section(cls, title: str):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"\n### {title}\n")
        except Exception: pass
        for listener in cls._get_listeners():
            try: listener(title, "section", "INFO")
            except: pass

    @classmethod
    def log_divider(cls):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f: f.write("\n" + "-" * 50 + "\n" + "-" * 50 + "\n\n")
        except Exception: pass

    @classmethod
    def log_stage_header(cls, title: str):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n" + "-" * 50 + "\n" + f"## {title}\n" + "-" * 50 + "\n\n")
        except Exception: pass
        cls.log_section(title)

    @classmethod
    def log_title(cls, title: str):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"\n{title}\n")
        except Exception: pass
        for listener in cls._get_listeners():
            try: listener(title, "title", "INFO")
            except: pass

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"```{language}\n{code}\n```\n\n")
        except Exception: pass
        for listener in cls._get_listeners():
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
            import tempfile; from pathlib import Path
            cls._storage.log_file = str(Path(tempfile.gettempdir()) / "nquire_execution.log")
        return cls._storage.log_file

