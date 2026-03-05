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
    _listeners = []

    @classmethod
    def _get_log_file(cls):
        return getattr(cls._storage, "log_file", "execution_log.md")

    @classmethod
    def register_listener(cls, callback):
        """Register a callback function(message, level) for real-time logging."""
        cls._listeners.append(callback)

    @classmethod
    def clear_listeners(cls):
        cls._listeners = []

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
    def log(cls, message: str, level: str = "INFO"):
        if not cls._enabled:
            return

        if cls._verbose:
            # Wrap in try-except for terminal encoding issues
            try:
                print(f"[{level}] {message}")
            except:
                pass

        # File output only (no terminal spam)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"- **[{timestamp}] [{level}]** {message}\n")
        except Exception:
            pass

        # Notify listeners
        for listener in cls._listeners:
            try:
                listener(message, "log")
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

        for listener in cls._listeners:
            try:
                listener(title, "section")
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

    @classmethod
    def log_title(cls, title: str):
        """Title (e.g., Sub-Task headers)."""
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{title}\n")
        except Exception:
            pass
            
        for listener in cls._listeners:
            try:
                listener(title, "title")
            except: pass

    @classmethod
    def log_code(cls, code: str, language: str = "sql"):
        log_file = cls._get_log_file()
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"```{language}\n{code}\n```\n\n")
        except Exception:
            pass
            
        for listener in cls._listeners:
            try:
                listener(code, "code")
            except: pass
