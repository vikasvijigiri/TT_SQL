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
    _capture_buffer: list[str] | None = None
    _lock = threading.Lock()
    _internal_logger = logging.getLogger("tt_sql")

    _silence_file_during_capture: bool = False

    @classmethod
    def start_capture(cls, silence_file: bool = True):
        """Starts capturing logs. If silence_file is True, logs skip the .md file while buffering."""
        with cls._lock:
            cls._capture_buffer = []
            cls._silence_file_during_capture = silence_file

    @classmethod
    def stop_capture(cls) -> str:
        """Stops capturing and restores normal logging."""
        with cls._lock:
            if cls._capture_buffer is None:
                return ""
            logs = "\n\n".join(cls._capture_buffer)
            cls._capture_buffer = None
            cls._silence_file_during_capture = False
            return logs

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

            # 1. Buffered File Handler (The modular .md file)
            f_handler = logging.FileHandler(path, mode="w", encoding="utf-8")
            # For the .md file, we use a clean formatter WITHOUT timestamps
            formatter = logging.Formatter("%(message)s")
            f_handler.setFormatter(formatter)
            cls._internal_logger.addHandler(f_handler)

            # 2. Live Console Handler (Terminal output with timestamps)
            c_handler = logging.StreamHandler()
            # Task 8: Format [TIMESTAMP] [LEVEL] message
            c_formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            c_handler.setFormatter(c_formatter)
            cls._internal_logger.addHandler(c_handler)

            cls._internal_logger.setLevel(get_settings().LOG_LEVEL)

    @classmethod
    def log(cls, message: str, level: str = "INFO", to_file: bool = True):
        """Logs a message to the active file (optional) and console."""
        with cls._lock:
            # 1. Capture logic (always capture if active)
            if cls._capture_buffer is not None:
                cls._capture_buffer.append(message)
                if cls._silence_file_during_capture:
                    to_file = False

            # --- CONSOLE/FILE ROUTING ---
            if not to_file:
                # Still notify listeners
                for listener in cls._listeners:
                    listener(message, level)
                return

            # Standard path (File + Console)
            try:
                if level.upper() == "ERROR":
                    cls._internal_logger.error(message)
                elif level.upper() == "WARN":
                    cls._internal_logger.warning(message)
                else:
                    cls._internal_logger.info(message)
            except:
                pass

            # 3. Notify Listeners
            for listener in cls._listeners:
                try:
                    listener(message, level)
                except Exception:
                    pass

    @classmethod
    def log_section(cls, title: str, iteration: int = None):
        """Standard modular section header with extra vertical spacing and optional iteration."""
        header = title.upper()
        if iteration is not None:
            header += f" (Iteration {iteration})"
        cls.log(f"\n\n----------\n{header}\n----------\n")

    @classmethod
    def log_stage_header(cls, title: str, iteration: int = None):
        """Modular stage header with optional iteration."""
        cls.log_section(title, iteration=iteration)

    @classmethod
    def log_agent_block(cls, name: str, inputs: list[dict], result: str, status: str = "success", prompt: str = None, metrics: dict = None, iteration: int = None):
        """Logs a standardized modular block for an agent or tool execution with iteration support."""
        cls.log_section(name, iteration=iteration)
        cls.log("Inputs/input_prompts:")
        for i, inp in enumerate(inputs):
            desc = inp.get("desc", "N/A")
            stat = inp.get("status", "found")
            cls.log(f"  {i+1}. {desc} (status: {stat})")
        
        if metrics:
            inp_t = metrics.get("input", 0)
            out_t = metrics.get("output", 0)
            max_t = metrics.get("max", 0)
            stop = metrics.get("stop", "n/a")
            # If stop is 'length' or output_t reaches max_t, it's a Red flag
            is_truncated = (stop == "length" or (max_t > 0 and out_t >= max_t))
            flag = "🔴 **TRUNCATED**" if is_truncated else "🟢 **OK**"
            
            cls.log(f"\n> [!NOTE]\n> **Token Usage**: {flag}\n> - **Prompt**: {inp_t} tokens\n> - **Response**: {out_t} / {max_t} tokens limit\n> - **Stop Reason**: `{stop}`")

        if prompt:
            cls.log("\n<details><summary><b>View Rendered Prompt</b></summary>\n")
            cls.log(f"```markdown\n{prompt}\n```")
            cls.log("\n</details>\n")
        
        cls.log(f"\nResponse/Result:\n\n{result}")
        cls.log(f"\nStatus: {status}\n")

    @classmethod
    def log_final_results(cls, sql: str, csv_path: str, result=None):
        """Logs the final outputs in the requested modular style with breathing room."""
        cls.log_section("Result (Final SQL)")
        cls.log(f"```sql\n{sql}\n```")
        
        cls.log_section("Result (Final csv)")
        cls.log(f"Output saved to: `{csv_path}`")
        
        if result and result.rows:
            cls.log("\n### 📋 SAMPLE OUTPUT (Top 5)")
            # Prepare markdown table
            cols = " | ".join([f"**{str(c)}**" for c in result.columns or []])
            if cols:
                cls.log(f"| {cols} |")
                cls.log(f"| {'--- | ' * len(result.columns)}")
                for row in result.rows[:5]: 
                    r_str = " | ".join([str(v).replace('\n', ' ') for v in row])
                    cls.log(f"| {r_str} |")
                if result.row_count > 5:
                    cls.log(f"\n_... and {result.row_count - 5} more rows._")
            else:
                cls.log("\n_No columns detected in result set._")
        elif result and result.error_message:
             cls.log(f"\n> [!ERROR]\n> **Execution Failed**: {result.error_message}")
        else:
            cls.log("\n_No data returned or result set is empty._")

    @classmethod
    def log_metrics(cls, elapsed: float, llm_calls: int):
        """Logs the final metrics section with spacing."""
        cls.log_section("Metrics")
        cls.log(f"Elapsed time: {elapsed:.2f}s")
        cls.log(f"Total LLM calls: {llm_calls}")
        cls.log("\n")

    @classmethod
    def log_divider(cls):
        """Minimal divider."""
        cls.log("\n---\n")

    @classmethod
    def log_code(cls, code: str, language: str = "sql", to_file: bool = True):
        """Logs a formatted code block in markdown with extra padding."""
        cls.log(f"\n```{language}\n{code}\n```\n", to_file=to_file)

    @classmethod
    def log_step(cls, step_name: str, status: str, details: str = None):
        """
        Enforced structured logging for pipeline steps.
        Format: [StepName] STATUS (Details)
        """
        msg = f"\n[{step_name}] {status}"
        if details:
            msg += f" ({details})"
        cls.log(msg + "\n")

    @classmethod
    def log_state(cls, old_state: str, new_state: str):
        """Logs explicit state transitions."""
        cls.log(f"\n[STATE] {old_state} → {new_state}\n")

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
        """Internal call logging - Terminal only to preserve .md modularity."""
        # We don't use cls.log here to avoid writing to the .md file
        try:
            msg = f"⚡ [CALL]: {target}"
            cls._internal_logger.debug(msg) 
        except: pass

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
    def log_schema_retriever(cls, tables_fetched: int, tables_selected: list, columns_selected: dict, variants: list = None, keys: dict = None):
        """Standardized SchemaRetriever detailed log."""
        cls.log("[SchemaRetriever]")
        cls.log(f"* Tables fetched: {tables_fetched}")
        cls.log(f"* Tables selected: {tables_selected}")
        # Flatten columns and include discovery keys if available
        # TASK: Enhanced grounding for variants
        from core.utils import normalize_identifier
        norm_keys = {}
        if keys:
            for k_fqn, k_list in keys.items():
                norm_keys[normalize_identifier(k_fqn)] = k_list

        all_cols = []
        if isinstance(columns_selected, dict):
            for table_name, table_cols in columns_selected.items():
                if isinstance(table_cols, list):
                    for col in table_cols:
                        col_display = col
                        # Find keys for this specific column (robust match)
                        key_match = normalize_identifier(f"{table_name}.{col}")
                        if key_match in norm_keys:
                            found_keys = norm_keys[key_match]
                            if found_keys:
                                col_display += f" (keys: {', '.join(found_keys)})"
                        all_cols.append(col_display)
        
        cls.log(f"* Columns selected: {all_cols}")
        if variants:
            # Task: Include keys in detected variant summary as well
            v_summary = []
            for v in variants:
                v_entry = v
                v_norm = normalize_identifier(v)
                if v_norm in norm_keys and norm_keys[v_norm]:
                    v_entry += f" [keys: {', '.join(norm_keys[v_norm])}]"
                v_summary.append(v_entry)
            cls.log(f"* Variant columns detected: {v_summary}")
        if keys:
            cls.log(f"* Variant keys extracted: {list(keys.values())}")

    @classmethod
    def log_query_planner(cls, strategy: str, mapping: list, confidence: str, missing: list, expansion: bool = False):
        """Standardized QueryPlanner detailed log."""
        cls.log("[QueryPlanner]")
        cls.log("* Strategy generated")
        cls.log(f"* Concept mapping: {mapping}")
        cls.log(f"* Confidence: {confidence}")
        cls.log(f"* Missing elements: {missing}")
        cls.log(f"* expansion_required: {expansion}")

    @classmethod
    def log_sql_builder(cls, sql: str, normalization: bool, flatten: bool, fixes: list, blocked: bool = False):
        """Standardized SQLBuilder detailed log."""
        cls.log("[SQLBuilder]")
        cls.log("* SQL generated")
        cls.log(f"* Identifier normalization applied: {normalization}")
        cls.log(f"* Variant flatten used: {'YES' if flatten else 'NO'}")
        cls.log(f"* Previous errors fixed: {fixes}")
        cls.log(f"* blocked_due_to_missing_schema: {blocked}")

    @classmethod
    def log_execution_engine(cls, sql: str, rows: int, error: str = None):
        """Standardized ExecutionEngine detailed log."""
        cls.log("[ExecutionEngine]")
        cls.log("* SQL execution started")
        cls.log(f"* Rows returned: {rows}")
        if error:
            cls.log(f"* Execution error: {error}")

    @classmethod
    def log_sql_critic(cls, valid: bool, error_type: str, feedback: str, suggestions: list):
        """Standardized SQLCritic detailed log."""
        cls.log("[SQLCritic]")
        cls.log(f"* is_valid: {valid}")
        cls.log(f"* error_type: {error_type}")
        cls.log(f"* feedback: {feedback}")
        cls.log(f"* fix suggestions: {suggestions}")

    @classmethod
    def log_data_iq(cls, sensible: bool, uncertainty: float, issues: list):
        """Standardized DataIQ detailed log."""
        cls.log("[DataIQ]")
        cls.log(f"* is_sensible: {sensible}")
        cls.log(f"* uncertainty_score: {uncertainty}")
        cls.log(f"* issues: {issues}")

    @classmethod
    def log_adaptive_loop(cls, iteration: int, max_iter: int, reason: str, action: str):
        """Standardized AdaptiveLoop detailed log."""
        cls.log(f"[AdaptiveLoop] Iteration {iteration}/{max_iter}")
        cls.log(f"* Trigger reason: {reason}")
        cls.log(f"* Action taken: {action}")

    @classmethod
    def log_pipeline_status(cls, success: bool, reason: str = None, sql: str = None, preview: str = None):
        """Final pipeline output contract."""
        if success:
            cls.log("[PIPELINE] SUCCESS")
            cls.log(f"* Final SQL: {sql}")
            cls.log(f"* Result preview: {preview}")
        else:
            cls.log("[PIPELINE] FAILED")
            cls.log(f"* Reason: {reason}")
