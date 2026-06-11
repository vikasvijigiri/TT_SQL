import logging
import sys
import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict
from logging.handlers import RotatingFileHandler


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    Subclass of RotatingFileHandler that catches PermissionError on Windows.
    If the log file is locked by another process (e.g. uvicorn web server),
    rollover will fail. We catch the exception and keep writing to the same file
    to prevent flooding stderr/console with tracebacks.
    """

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            if self.stream is None:
                self.stream = self._open()


class ThreadLocalFilter(logging.Filter):
    """
    Filter to prevent logging from thread-local runs to go to the global log file.
    """

    def filter(self, record):
        return not hasattr(task_local, "live_file")


# Thread-local storage for task-specific logs
task_local = threading.local()


class CustomLogger:
    def __init__(self, name: str = "SemanticDIN"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.name = name

        # Extended ANSI Color Codes for beautiful logging
        self.GREEN = "\033[38;2;46;204;113m"  # Emerald Green
        self.YELLOW = "\033[38;2;241;196;15m"  # Sunflower Yellow
        self.RED = "\033[38;2;231;76;60m"  # Alizarin Red
        self.BLUE = "\033[38;2;52;152;219m"  # Peter River Blue
        self.MAGENTA = "\033[38;2;155;89;182m"  # Amethyst
        self.CYAN = "\033[38;2;26;188;156m"  # Turquoise
        self.ORANGE = "\033[38;2;230;126;34m"  # Carrot Orange
        self.GRAY = "\033[38;2;149;165;166m"  # Concrete Gray

        # Styles
        self.BOLD = "\033[1m"
        self.UNDERLINE = "\033[4m"
        self.RESET = "\033[0m"

        # Console handler
        self.ch = logging.StreamHandler(sys.stdout)
        self.ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            f"{self.GRAY}%(asctime)s{self.RESET} | {self.BOLD}{self.MAGENTA}%(name)-12s{self.RESET} | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
        self.ch.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(self.ch)

            # Global file handler for detailed logs (keeps clean of ANSI)
            from backend.app.core.config import LOGS_DIR

            # Determine entry point suffix to avoid multi-process lock contention on Windows
            entrypoint = "main"
            if len(sys.argv) > 0 and sys.argv[0]:
                base_script = os.path.basename(sys.argv[0]).lower()
                if (
                    "uvicorn" in base_script
                    or "gunicorn" in base_script
                    or "api" in base_script
                ):
                    entrypoint = "api"
                elif "run_batch" in base_script:
                    entrypoint = "batch"
                elif "evolver" in base_script:
                    entrypoint = "evolver"
                elif "pytest" in base_script or "test" in base_script:
                    entrypoint = "test"
                else:
                    name_part = os.path.splitext(base_script)[0]
                    if name_part:
                        entrypoint = name_part

            log_filename = f"{entrypoint}.log"
            main_log_path = LOGS_DIR / log_filename
            self.fh = WindowsSafeRotatingFileHandler(
                str(main_log_path),
                mode="a",
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            self.fh.setLevel(logging.DEBUG)
            self.fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
            self.fh.addFilter(ThreadLocalFilter())
            self.logger.addHandler(self.fh)

    def set_agent(self, name: str):
        """Sets the current agent name for logging context."""
        self.logger.name = name.upper()

    def reset_agent(self):
        """Resets the logger name to default."""
        self.logger.name = "ORCHESTRATOR"

    def start_live_task_log(self, file_path: str):
        """Starts real-time logging to a specific file for the current thread."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            task_local.live_file = open(file_path, "w", encoding="utf-8", buffering=1)
            task_local.live_file.write(
                f"\n{'=' * 80}\n--- EXECUTION STARTED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n{'=' * 80}\n\n"
            )

            # Create a run-specific .log file in the same directory
            log_file_path = os.path.splitext(file_path)[0] + ".log"
            task_local.log_file = open(
                log_file_path, "w", encoding="utf-8", buffering=1
            )
            task_local.log_file.write(
                f"--- DETAILED LOG STARTED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )
        except Exception as e:
            self.logger.error(f"Failed to start live task log at {file_path}: {e}")

    def stop_live_task_log(self):
        """Stops real-time logging for the current thread."""
        if hasattr(task_local, "live_file"):
            try:
                task_local.live_file.write(
                    f"\n--- EXECUTION FINISHED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                task_local.live_file.close()
            finally:
                del task_local.live_file
        if hasattr(task_local, "log_file"):
            try:
                task_local.log_file.write(
                    f"--- DETAILED LOG FINISHED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                task_local.log_file.close()
            finally:
                del task_local.log_file

    def _write_live(self, level: str, msg: str):
        """Internal helper to write to the live task file if active."""
        if hasattr(task_local, "live_file"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_msg = re.sub(r"\033\[[0-9;]*m", "", msg)
            task_local.live_file.write(
                f"{timestamp} - {self.logger.name} - {level} - {clean_msg}\n"
            )
        if hasattr(task_local, "log_file"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_msg = re.sub(r"\033\[[0-9;]*m", "", msg)
            task_local.log_file.write(
                f"{timestamp} - {self.logger.name} - {level} - {clean_msg}\n"
            )

    def info(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.info(sanitized)
        self._write_live("INFO", sanitized)

    def success(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.info(f"{self.GREEN}{self.BOLD}SUCCESS: {sanitized}{self.RESET}")
        self._write_live("SUCCESS", f"SUCCESS: {sanitized}")

    def debug(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.debug(f"{self.GRAY}{sanitized}{self.RESET}")
        self._write_live("DEBUG", sanitized)

    def error(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.error(f"{self.RED}{self.BOLD}{sanitized}{self.RESET}")
        self._write_live("ERROR", sanitized)

    def warning(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.warning(f"{self.ORANGE}{self.BOLD}{sanitized}{self.RESET}")
        self._write_live("WARNING", sanitized)

    def log_section(self, title: str, color: str | None = None):
        """Creates a beautiful, separated section header in the logs."""
        color_code = color or self.CYAN
        width = 80
        separator = f"{color_code}{self.BOLD}-{self.RESET}" * width

        self.info(f"\n{separator}")
        self.info(f"{color_code}{self.BOLD}> {title.upper()}{self.RESET}")
        self.info(f"{separator}\n")

    def log_parsed_data(self, label: str, data: Any):
        """Logs structured Pydantic models or dicts beautifully."""
        self.info(f"{self.BLUE}{self.BOLD}[{label}]{self.RESET}")
        if hasattr(data, "model_dump"):  # Pydantic v2
            formatted = json.dumps(data.model_dump(), indent=2, default=str)
        elif hasattr(data, "dict"):  # Pydantic v1
            formatted = json.dumps(data.dict(), indent=2, default=str)
        elif isinstance(data, (dict, list)):
            formatted = json.dumps(data, indent=2, default=str)
        else:
            formatted = str(data)

        indented = "\n".join(
            [f"  {self.GRAY}|{self.RESET} {line}" for line in formatted.split("\n")]
        )
        self.info(f"{indented}\n")

    def log_agent_call(
        self, name: str, prompt: str, result: str, metrics: Dict[str, Any] | None = None
    ):
        """Standardized format for all LLM agent inputs/outputs."""
        self.log_section(f"Agent Execution: {name}", color=self.MAGENTA)

        if metrics:
            inp_t = metrics.get("input_tokens", 0)
            out_t = metrics.get("output_tokens", 0)
            self.info(f"{self.YELLOW}Tokens: {inp_t} In / {out_t} Out{self.RESET}")

        self.debug(f"{self.BLUE}{self.BOLD}v PROMPT{self.RESET}")
        indented_prompt = "\n".join(
            [
                f"  {self.GRAY}|{self.RESET} {line}"
                for line in prompt.strip().split("\n")
            ]
        )
        self.debug(f"{indented_prompt}\n")

        self.info(f"{self.GREEN}{self.BOLD}v RESPONSE{self.RESET}")
        indented_result = "\n".join(
            [
                f"  {self.GRAY}|{self.RESET} {line}"
                for line in result.strip().split("\n")
            ]
        )
        self.info(f"{indented_result}\n")

    def log_final_results(
        self, sql: str, row_count: int, error: str | None = None, latency: str | None = None
    ):
        self.log_section(
            "Final Pipeline Results", color=self.GREEN if not error else self.RED
        )
        if latency:
            self.info(f"Latency: {latency}")

        if error:
            self.error(f"Execution Error: {error}")
        else:
            self.success(f"Generated SQL executed successfully! ({row_count} rows)")
            self.info(f"{self.BLUE}{self.BOLD}v SQL{self.RESET}\n{sql}\n")

    def _sanitize(self, message: str) -> str:
        """Sanitizes the message to ASCII for console compatibility."""
        return "".join(c if ord(c) < 128 else " " for c in str(message))


logger = CustomLogger()
