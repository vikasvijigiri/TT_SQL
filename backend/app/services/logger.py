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
    def _get_listeners(cls):
        if not hasattr(cls._storage, "listeners"):
            cls._storage.listeners = []
        return cls._storage.listeners


    # Terminal ANSI Colors
    COLORS = {
        "DEBUG": "\033[94m",    # blue
        "INFO": "\033[92m",     # green
        "WARNING": "\033[93m",  # yellow
        "ERROR": "\033[91m",    # red
        "RESET": "\033[0m"
    }

    # Markdown HTML Colors
    MD_COLORS = {
        "DEBUG": "blue",
        "INFO": "green",
        "WARNING": "orange",
        "ERROR": "red"
    }

    @classmethod
    def _get_log_file(cls):
        if not hasattr(cls._storage, "log_file"):
            import tempfile
            from pathlib import Path
            cls._storage.log_file = str(Path(tempfile.gettempdir()) / "nquire_execution.log")
        return cls._storage.log_file

    @classmethod
    def register_listener(cls, callback):
        """Register a callback function(message, level) for real-time logging."""
        cls._get_listeners().append(callback)

    @classmethod
    def clear_listeners(cls):
        cls._get_listeners().clear()


    @classmethod
    def bind_log_file(cls, filename: str):
        """Bind logger to an existing file without truncating it (useful for threads)."""
        cls._storage.log_file = os.path.abspath(filename)

    @classmethod
    def set_log_file(cls, filename: str):
        cls._storage.log_file = os.path.abspath(filename)
        with open(cls._storage.log_file, "w", encoding="utf-8") as f:
            f.write("# Text2SQL Execution Log\n\n")

    @classmethod
    def log(cls, message: str, level: str = "INFO", agent_name: str = None):
        if not cls._enabled:
            return

        import datetime
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

        if cls._verbose:
            # Wrap in try-except for terminal encoding issues
            level_color = cls.COLORS.get(level.upper(), cls.COLORS["RESET"])
            reset = cls.COLORS["RESET"]
            try:
                print(f"[{timestamp}] {level_color}[{level}]{reset} {message}", flush=True)
            except:
                pass

        # File output (Markdown with HTML colors)
        color = cls.MD_COLORS.get(level.upper(), "black")
        log_file = cls._get_log_file()
        
        display_message = message
        if agent_name:
            display_message = f"[{agent_name}]: {message}"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"- **[{timestamp}]** <font color=\"{color}\">**[{level}]**</font> {display_message}\n")
        except Exception:
            pass

        # Notify listeners
        for listener in cls._get_listeners():
            try:
                listener(message, "log", level)
            except: pass


    @classmethod
    def log_section(cls, title: str):
        """Section header (e.g., Agent names)."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n### {title}\n")
        except Exception:
            pass

        for listener in cls._get_listeners():
            try:
                listener(title, "section", "INFO")
            except: pass


    @classmethod
    def log_divider(cls):
        """Visual divider line."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n" + "-" * 50 + "\n" + "-" * 50 + "\n\n")
        except Exception:
            pass

    @classmethod
    def log_stage_header(cls, title: str):
        """Stage header with dividers above and below."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n" + "-" * 50 + "\n")
                f.write(f"## {title}\n")
                f.write("-" * 50 + "\n\n")
        except Exception:
            pass
        
        # Link to log_section to notify listeners
        cls.log_section(title)

    @classmethod
    def log_title(cls, title: str):
        """Title (e.g., Sub-Task headers)."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{title}\n")
        except Exception:
            pass
            
        for listener in cls._get_listeners():
            try:
                listener(title, "title", "INFO")
            except: pass


    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"```{language}\n{code}\n```\n\n")
        except Exception:
            pass
            
        for listener in cls._get_listeners():
            try:
                listener(code, "code", "INFO")
            except: pass

