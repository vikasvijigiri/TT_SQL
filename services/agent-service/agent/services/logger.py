import logging

import sys

import json

import os

import re

import threading

from datetime import datetime

from typing import Any, Dict



# Thread-local storage for task-specific logs

task_local = threading.local()

task_local.telemetry = []





class CustomLogger:

    def __init__(self, name: str = "SemanticDIN"):

        self.logger = logging.getLogger(name)

        self.logger.setLevel(logging.DEBUG)

        self.name = name



        # Extended ANSI Color Codes for beautiful logging

        self.GREEN = "\033[38;2;46;204;113m"

        self.YELLOW = "\033[38;2;241;196;15m"

        self.RED = "\033[38;2;231;76;60m"

        self.BLUE = "\033[38;2;52;152;219m"

        self.MAGENTA = "\033[38;2;155;89;182m"

        self.CYAN = "\033[38;2;26;188;156m"

        self.ORANGE = "\033[38;2;230;126;34m"

        self.GRAY = "\033[38;2;149;165;166m"



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



    def set_agent(self, name: str):

        self.logger.name = name.upper()



    def reset_agent(self):

        self.logger.name = "ORCHESTRATOR"



    # -- MARKDOWN HELPERS ------------------------------------------------------



    @staticmethod

    def _strip_ansi(text: str) -> str:

        return re.sub(r"\033\[[0-9;]*m", "", text)



    @staticmethod

    def _md_cell(value: str) -> str:

        """Escape pipe chars and newlines for use inside a markdown table cell."""

        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", "")



    def _close_log_block(self) -> None:

        """Close the open ``` code fence if one is active. (Disabled for flat logging)"""

        pass



    def _open_log_block(self) -> None:

        """Open a ``` log code fence. (Disabled for flat logging)"""

        pass



    # -- LIFECYCLE -------------------------------------------------------------



    def start_live_task_log(self, file_path: str):

        """Open the .md log file and write the document header."""

        try:

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            task_local.live_file = open(file_path, "w", encoding="utf-8", buffering=1)

            task_local.in_log_block = False

            task_local.live_file.write(

                f"# Pipeline Execution Log\n\n"

                f"**Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

                f"-\n\n"

            )

        except Exception as e:

            self.logger.error(f"Failed to start live task log at {file_path}: {e}")



    def stop_live_task_log(self):

        """Close the .md log file with a footer."""

        if hasattr(task_local, "live_file"):

            try:

                self._close_log_block()

                task_local.live_file.write(

                    f"\n---\n\n**Finished:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                )

                task_local.live_file.close()

            finally:

                del task_local.live_file

                task_local.in_log_block = False

                task_local.telemetry = []



    # -- CORE WRITE ------------------------------------------------------------



    def _write_live(self, level: str, msg: str):

        """Write a fixed-width log line inside the active code-fence block.



        Format (monospace, left-right justified):

            HH:MM:SS  LEVEL    AGENT-NAME           message text

        """

        if not hasattr(task_local, "live_file"):

            return

        # Ensure we're inside a code block

        if not getattr(task_local, "in_log_block", False):

            return  # log block not yet opened; settings block writes directly



        ts    = datetime.now().strftime("%H:%M:%S")

        agent = self.logger.name

        clean = self._strip_ansi(msg).strip()

        if not clean:

            return



        for sub in clean.splitlines():

            sub = sub.strip()

            if not sub:

                continue

            # Fixed-width columns: time(8) level(9) agent(22) message

            task_local.live_file.write(

                f"{ts}  {level:<9}{agent:<22}{sub}\n"

            )



    # -- PUBLIC LOG METHODS ----------------------------------------------------



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



    def error(self, msg: str, **kwargs):

        sanitized = self._sanitize(msg)

        self.logger.error(f"{self.RED}{self.BOLD}{sanitized}{self.RESET}", **kwargs)

        self._write_live("ERROR", sanitized)



    def warning(self, msg: str):

        sanitized = self._sanitize(msg)

        self.logger.warning(f"{self.ORANGE}{self.BOLD}{sanitized}{self.RESET}")

        self._write_live("WARNING", sanitized)



    def log_section(self, title: str, color: str | None = None):

        """Section header: H3 in .md (closing/reopening code fence), colored line to console."""

        color_code = color or self.CYAN

        self.logger.info(f"{color_code}{self.BOLD}>>> {title.upper()}{self.RESET}")

        if hasattr(task_local, "live_file"):

            self._close_log_block()

            task_local.live_file.write(f"\n---\n\n### {title}\n\n")

            self._open_log_block()



    def log_parsed_data(self, label: str, data: Any):

        """Logs structured Pydantic models or dicts."""

        self.info(f"[{label}]")

        if hasattr(data, "model_dump"):

            formatted = json.dumps(data.model_dump(), indent=2, default=str)

        elif hasattr(data, "dict"):

            formatted = json.dumps(data.dict(), indent=2, default=str)

        elif isinstance(data, (dict, list)):

            formatted = json.dumps(data, indent=2, default=str)

        else:

            formatted = str(data)

        self.info(formatted)



    # -- STRUCTURED BLOCKS -----------------------------------------------------



    # No truncation - full prompt/response visibility required.

    _LOG_PROMPT_MAX = 0

    _LOG_RESPONSE_MAX = 0



    def log_run_settings(self, settings: dict) -> None:

        """Write a markdown table of run settings, then open the execution log code block."""

        # Console: plain key=value

        for key, value in settings.items():

            self.logger.info(f"  {key:<20}: {value}")



        if not hasattr(task_local, "live_file"):

            return



        # Close any open code fence before writing markdown headings/tables

        self._close_log_block()



        f = task_local.live_file

        # Settings table

        f.write("## Run Settings\n\n")

        f.write("| Setting              | Value                                          |\n")

        f.write("|:---------------------|:-----------------------------------------------|\n")

        for key, value in settings.items():

            k = f"{self._md_cell(str(key)):<20}"

            v = self._md_cell(str(value))

            f.write(f"| {k} | {v} |\n")

        f.write("\n")



        # Open the execution log code block

        f.write("---\n\n## Execution Log\n\n")

        f.write("```text\n")

        # Column header row inside the code block

        f.write(f"{'TIME':<10}{'LEVEL':<9}{'AGENT':<22}MESSAGE\n")

        f.write(f"{'-'*8}  {'-'*8} {'-'*20} {'-'*40}\n")

        task_local.in_log_block = True



    def log_agent_call(

        self, name: str, prompt: str, result: str, metrics: Dict[str, Any] | None = None

    ):

        """Write full agent prompt/response to .md; brief summary to console."""

        _prompt_len = len(prompt)

        _result_len = len(result)



        if hasattr(task_local, "live_file"):

            ts = datetime.now().strftime("%H:%M:%S")

            f = task_local.live_file



            # Close the running log code fence first

            self._close_log_block()



            # Agent section header

            metrics_str = ""

            if metrics:

                inp_t = metrics.get("input_tokens", 0)

                out_t = metrics.get("output_tokens", 0)

                metrics_str = f" | **Tokens:** {inp_t:,} In / {out_t:,} Out"

            

            f.write(f"\n================================================================================\n")

            f.write(f"AGENT EXECUTION: {name.upper()}\n")

            f.write(f"================================================================================\n")

            f.write(f"Time: {ts}{metrics_str}\n\n")



            f.write(f"- SYSTEM PROMPT & INPUT ---\n")

            f.write(f"{prompt.strip()}\n\n")



            import re

            

            # Plain flat text instead of markdown collapses

            f.write(f"- PARSED GENERATION OUTPUT ---\n")

            clean_res = result.strip()

            if clean_res.startswith("```json"): clean_res = clean_res[7:]

            if clean_res.endswith("```"): clean_res = clean_res[:-3]

            f.write(f"{clean_res.strip()}\n")

            f.write(f"================================================================================\n\n")



            task_local.in_log_block = True

            think_match = re.search(r'<think>(.*?)</think>', result, flags=re.DOTALL | re.IGNORECASE)

            clean_result = re.sub(r'<think>.*?</think>', "", result, flags=re.DOTALL | re.IGNORECASE).strip()

            

            if think_match:

                think_text = think_match.group(1).strip()

                blockquote_think = "\n".join(f"> {line}" for line in think_text.splitlines())

                f.write(f"###  Reasoning Track\n{blockquote_think}\n\n")

            

            if clean_result:

                f.write("### [OK] Final Action / Output\n")

                if "```json" in clean_result or "```sql" in clean_result:

                    f.write(f"{clean_result}\n\n")

                elif clean_result.startswith("{") or clean_result.startswith("["):

                    f.write(f"```json\n{clean_result}\n```\n\n")

                elif clean_result.upper().startswith("SELECT ") or clean_result.upper().startswith("WITH "):

                    f.write(f"```sql\n{clean_result}\n```\n\n")

                else:

                    f.write(f"```text\n{clean_result}\n```\n\n")



            # Re-open execution log block for subsequent log lines

            f.write("---\n\n###  Post-Agent Telemetry\n\n")

            f.write("```text\n")

            f.write(f"{'TIME':<10}{'LEVEL':<9}{'AGENT':<22}MESSAGE\n")

            f.write(f"{'-'*8}  {'-'*8} {'-'*20} {'-'*40}\n")

            task_local.in_log_block = True



        # Console: brief summary

        self.log_section(f"Agent: {name}", color=self.MAGENTA)

        if metrics:

            inp_t = metrics.get("input_tokens", 0)

            out_t = metrics.get("output_tokens", 0)

            self.logger.info(f"Tokens: {inp_t:,} in / {out_t:,} out")

        self.logger.info(f"Prompt: {_prompt_len:,} chars | Response: {_result_len:,} chars")

        raw_result = result.strip()
        preview = raw_result[:1000]
        if len(raw_result) > 1000:
            preview += "\n... [Console Preview Truncated for Brevity. Full response is complete and logged to markdown file.]"
        if preview:
            self.logger.info(f"Response preview:\n{preview}")



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

            self.info(f"SQL:\n{sql}\n")



    def record_agent_telemetry(

        self,

        agent_name: str,

        tokens_in: int,

        tokens_out: int,

        latency_ms: float,

        confidence: float,

        retry_count: int = 0

    ):

        """Record observability metrics for a single agent execution."""

        if not hasattr(task_local, "telemetry"):

            task_local.telemetry = []

            

        record = {

            "timestamp": datetime.now().isoformat(),

            "agent_name": agent_name,

            "tokens_in": tokens_in,

            "tokens_out": tokens_out,

            "latency_ms": latency_ms,

            "confidence": confidence,

            "retry_count": retry_count

        }

        task_local.telemetry.append(record)



    def dump_telemetry(self, output_dir: str, run_id: str):

        """Export accumulated telemetry to JSON and CSV."""

        if not hasattr(task_local, "telemetry") or not task_local.telemetry:

            return

            

        os.makedirs(output_dir, exist_ok=True)

        

        # Dump JSON

        json_path = os.path.join(output_dir, f"{run_id}_telemetry.json")

        try:

            with open(json_path, "w", encoding="utf-8") as f:

                json.dump(task_local.telemetry, f, indent=2)

        except Exception as e:

            self.logger.error(f"Failed to dump JSON telemetry: {e}")

            

        # Dump CSV

        csv_path = os.path.join(output_dir, f"{run_id}_telemetry.csv")

        try:

            import csv

            with open(csv_path, "w", encoding="utf-8", newline="") as f:

                writer = csv.DictWriter(f, fieldnames=[

                    "timestamp", "agent_name", "tokens_in", "tokens_out", 

                    "latency_ms", "confidence", "retry_count"

                ])

                writer.writeheader()

                writer.writerows(task_local.telemetry)

        except Exception as e:

            self.logger.error(f"Failed to dump CSV telemetry: {e}")



    def _sanitize(self, message: str) -> str:

        """Sanitizes the message to ASCII for console compatibility."""

        return "".join(c if ord(c) < 128 else " " for c in str(message))





logger = CustomLogger()

