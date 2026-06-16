import logging
import sys
import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

# Thread-local storage for task-specific logs
task_local = threading.local()

class CustomLogger:
    def __init__(self, name: str = "text2sql"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.name = name
        
        # ANSI Color Codes
        self.GREEN = "\033[92m"
        self.YELLOW = "\033[93m"
        self.RED = "\033[91m"
        self.BLUE = "\033[94m"
        self.MAGENTA = "\033[95m"
        self.CYAN = "\033[96m"
        self.BOLD = "\033[1m"
        self.RESET = "\033[0m"

        # Console handler
        self.ch = logging.StreamHandler(sys.stdout)
        self.ch.setLevel(logging.INFO)
        formatter = logging.Formatter(f'%(asctime)s - {self.BOLD}%(name)s{self.RESET} - %(levelname)s - %(message)s')
        self.ch.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(self.ch)
            
            # Global file handler for detailed logs
            self.fh = logging.FileHandler("log.txt", mode='a')
            self.fh.setLevel(logging.DEBUG)
            self.fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(self.fh)

    def set_agent(self, name: str):
        """Sets the current agent name for logging."""
        self.logger.name = name.upper()

    def reset_agent(self):
        """Resets the logger name to default."""
        self.logger.name = "text2sql"

    def start_live_task_log(self, file_path: str):
        """Starts real-time logging to a specific file for the current thread."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # Open file in append mode with line buffering
            task_local.live_file = open(file_path, 'a', encoding='utf-8', buffering=1)
            task_local.live_file.write(f"\n--- EXECUTION STARTED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n\n")
        except Exception as e:
            self.logger.error(f"Failed to start live task log at {file_path}: {e}")

    def stop_live_task_log(self):
        """Stops real-time logging for the current thread."""
        if hasattr(task_local, "live_file"):
            try:
                task_local.live_file.write(f"\n--- EXECUTION FINISHED AT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                task_local.live_file.close()
            finally:
                del task_local.live_file

    def _write_live(self, level: str, msg: str):
        """Internal helper to write to the live task file if active."""
        if hasattr(task_local, "live_file"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clean_msg = re.sub(r'\033\[[0-9;]*m', '', msg)
            task_local.live_file.write(f"{timestamp} - {self.logger.name} - {level} - {clean_msg}\n")

    def info(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.info(sanitized)
        self._write_live("INFO", sanitized)

    def success(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.info(f"{self.GREEN}SUCCESS: {sanitized}{self.RESET}")
        self._write_live("SUCCESS", f"SUCCESS: {sanitized}")

    def debug(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.debug(sanitized)
        self._write_live("DEBUG", sanitized)

    def error(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.error(f"{self.RED}{sanitized}{self.RESET}")
        self._write_live("ERROR", sanitized)

    def warning(self, msg: str):
        sanitized = self._sanitize(msg)
        self.logger.warning(f"{self.YELLOW}{sanitized}{self.RESET}")
        self._write_live("WARNING", sanitized)

    def log(self, msg: str, level: str = "INFO"):
        sanitized = self._sanitize(msg)
        lvl = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(lvl, sanitized)
        self._write_live(level.upper(), sanitized)

    def _sanitize(self, message: str) -> str:
        """STRICT ASCII-ONLY FOR PRODUCTION DIAGNOSTICS."""
        replacements = {
            "→": "->", "💎": "-", "✨": "-", "📊": "RESULT",
            "🎉": "SUCCESS", "⚡": "CALL", "❌": "ERROR",
            "🔴": "[TRUNCATED]", "🟢": "[OK]", "💡": "INFO",
            "📦": "DATA", "📝": "RESPONSE", "🎯": "RESULT",
            "🔍": "AUDIT", "🟡": "[WARN]", "🛑": "STOP",
            "🚀": "START", "✅": "PASS", "⌛": "TIME",
            "📋": "LIST", "🧪": "TEST"
        }
        sanitized = str(message)
        for emoji, text in replacements.items():
            sanitized = sanitized.replace(emoji, text)
        
        sanitized = re.sub(r'[^\x00-\x7F]+', '?', sanitized)
        return sanitized

    def log_section(self, title: str):
        width = 60
        separator = "=" * width
        self.info(f"\n{separator}")
        self.info(f"{title.center(width).upper()}")
        self.info(f"{separator}\n")

    def log_parsed_data(self, label: str, data: Any):
        self.info(f"[{label}]")
        if hasattr(data, "model_dump"): # Pydantic v2
            formatted = json.dumps(data.model_dump(), indent=2, default=str)
        elif hasattr(data, "dict"): # Pydantic v1
            formatted = json.dumps(data.dict(), indent=2, default=str)
        elif isinstance(data, (dict, list)):
            formatted = json.dumps(data, indent=2, default=str)
        else:
            formatted = str(data)
        
        indented = "\n".join([f"  {line}" for line in formatted.split("\n")])
        self.info(f"{indented}\n")

    def log_agent_block(self, name: str, prompt: str, result: str, metrics: Dict[str, Any] = None):
        self.log_section(f"Agent: {name}")
        if metrics:
            inp_t = metrics.get("input_tokens", 0)
            out_t = metrics.get("output_tokens", 0)
            self.info(f"Token Usage: Prompt={inp_t}, Response={out_t}")
        
        self.info(f"\nPROMPT:\n{prompt}\n")
        self.info(f"RESPONSE:\n{result}\n")

    def log_step(self, step_name: str, data: Dict[str, Any]):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "step": step_name,
            "data": data
        }
        self.debug(f"STEP_DATA: {json.dumps(log_entry)}")

    def log_final_results(self, sql: str, row_count: int, error: str = None):
        self.log_section("Final Results")
        if error:
            self.error(f"Execution Error: {error}")
        else:
            self.info(f"Generated SQL:\n{sql}")
            self.info(f"Row Count: {row_count}")

logger = CustomLogger()
