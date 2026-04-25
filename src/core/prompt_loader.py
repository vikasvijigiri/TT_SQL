import json
import os

import yaml

from .paths import PIPELINE_CONFIG, PROMPTS_DIR


class PromptLoader:
    """
    Loads prompt templates from YAML files in the prompts directory.
    Uses centralized paths from paths.py module and caches results.
    """

    # Class-level caches for shared across instances/threads
    _TEMPLATE_CACHE = {}  # prompt_name -> template_data
    _GLOBAL_CONFIG_CACHE = None
    _JSON_FILE_CACHE = {}  # path -> parsed_string

    def __init__(self, prompts_dir: str = None):
        self.prompts_dir = prompts_dir or str(PROMPTS_DIR)

        # 1. Warm global config cache if not already loaded
        if PromptLoader._GLOBAL_CONFIG_CACHE is None:
            PromptLoader._GLOBAL_CONFIG_CACHE = {}
            if os.path.exists(PIPELINE_CONFIG):
                try:
                    with open(PIPELINE_CONFIG) as f:
                        cfg = yaml.safe_load(f)
                        PromptLoader._GLOBAL_CONFIG_CACHE = cfg.get("prompts", {}).get(
                            "global", {}
                        )
                        # Also include general labels
                        PromptLoader._GLOBAL_CONFIG_CACHE.update(cfg.get("labels", {}))
                except Exception:
                    pass  # Fallback to empty if config fails

    def load_prompt(self, prompt_name: str, state: any = None, **kwargs) -> list[dict[str, str]]:
        """
        Loads a prompt by name, formats it with state metadata and kwargs.
        
        Metadata auto-injection:
        If 'state' is provided, it automatically populates:
        - {SCHEMA}: Formatted column list for the current DB
        - {DB_NAME}: The database identifier
        - {DIALECT}: sqlite, snowflake, etc.
        - {USER_QUERY}: The original natural language question
        """
        # 1. Get or Load template data
        if prompt_name not in PromptLoader._TEMPLATE_CACHE:
            filename = f"{prompt_name}.yaml"
            file_path = os.path.join(self.prompts_dir, filename)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Prompt file not found: {file_path}")

            with open(file_path, encoding="utf-8") as f:
                PromptLoader._TEMPLATE_CACHE[prompt_name] = yaml.safe_load(f)

        template_data = PromptLoader._TEMPLATE_CACHE[prompt_name]

        # 2. Merge global configuration variables
        processed_kwargs = PromptLoader._GLOBAL_CONFIG_CACHE.copy()

        # 3. Implicit State Injection
        if state:
            from .paths import InstancePaths, DIALECT_RULES
            from .utils import format_execution_results, format_schema_to_str, read_db_metadata
            
            # Identity & Dialect
            val_dialect = getattr(state, "dialect", "sqlite")
            processed_kwargs.update({
                "DIALECT": val_dialect.capitalize(),
                "dialect": val_dialect,
                "DB_NAME": getattr(state, "db_name", ""),
                "USER_QUERY": getattr(state, "user_query", "")
            })
            
            # --- Conditional Metadata Blocks ---
            def add_block(key, label, value, fallback=""):
                if value and value != "None." and value != "No plan.":
                    processed_kwargs[key] = f"### {label}\n{value}\n"
                else:
                    processed_kwargs[key] = fallback

            # Action Plan
            plan = getattr(state, "step_by_step_plan", [])
            plan_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan)) if plan else ""
            add_block("ACTION_PLAN", "STRATEGY GUIDE", plan_str)
            add_block("action_plan", "STRATEGY GUIDE", plan_str)

            # Strategies (Advanced Tree-of-Thought)
            strategies = getattr(state, "strategies", None)
            strat_str = ""
            if strategies:
                if isinstance(strategies, dict):
                    primary = strategies.get("primary", [])
                    alt = strategies.get("alternative", [])
                    risks = strategies.get("semantic_risks", [])
                    strat_str = f"PRIMARY STRATEGY:\n" + "\n".join([f"  - {s}" for s in primary])
                    if alt: strat_str += f"\n\nALTERNATIVE STRATEGY:\n" + "\n".join([f"  - {s}" for s in alt])
                    if risks: strat_str += f"\n\nSEMANTIC RISKS:\n" + "\n".join([f"  - {r}" for r in risks])
                else: strat_str = str(strategies)
            add_block("STRATEGIES", "STRATEGIC OPTIONS", strat_str)

            # Ensemble Audit Context
            audit_ctx = getattr(state, "audit_context", "")
            add_block("AUDIT_CONTEXT", "SQL CANDIDATES FOR EVALUATION", audit_ctx)

            # Discovered Values (Semantic matching results)
            disc_values = getattr(state, "discovered_values", [])
            disc_str = "\n".join(f"  - {v}" for v in disc_values) if disc_values else ""
            add_block("DISCOVERED_VALUES", "DISCOVERED DATA VALUES", disc_str)

            # Execution Results
            res = getattr(state, "execution_result", None)
            res_str = format_execution_results(res) if res else ""
            add_block("EXECUTION_RESULTS", "PREVIOUS EXECUTION RESULTS", res_str)
            add_block("execution_results", "PREVIOUS EXECUTION RESULTS", res_str)

            # Failure History
            history = getattr(state, "execution_error_history", [])
            history_str = "\n".join(f"- {e}" for e in history) if history else ""
            add_block("FAILURE_HISTORY", "PREVIOUS FAILURES", history_str)

            # SQL Context
            prev_sql = getattr(state, "chosen_query", "")
            add_block("sql_context", "CURRENT SQL", prev_sql)
            processed_kwargs.setdefault("previous_sql", prev_sql) # for backward compat
            processed_kwargs.setdefault("sql", prev_sql)
            processed_kwargs.setdefault("chosen_query", prev_sql)
            processed_kwargs.setdefault("previous_sql_label", "### PREVIOUS SQL" if prev_sql else "")
            
            # Feedback
            add_block("previous_feedback", "CRITIC FEEDBACK", getattr(state, "critic_feedback", ""))

            # Dialect Instructions
            try:
                with open(DIALECT_RULES) as f:
                    all_rules = yaml.safe_load(f)
                rules = all_rules.get(val_dialect, all_rules.get("sqlite", {}))
                instr = rules.get("builder_instructions", rules.get("instructions", ""))
                add_block("DIALECT_INSTRUCTIONS", f"{val_dialect.upper()} RULES", instr)
                processed_kwargs.setdefault("dialect_instructions", instr)
            except Exception: pass

            # Schema
            if getattr(state, "db_name", None):
                # Full schema
                schema_str = format_schema_to_str(state.schema_info)
                if not schema_str or len(schema_str) < 50:
                     metadata_path = str(InstancePaths.db_metadata(state.db_name))
                     schema_str = self._get_cached_json_schema(metadata_path)
                
                # Minimal schema (Table names only)
                table_names = list(state.schema_info.keys()) if state.schema_info else []
                if not table_names and getattr(state, "db_name", None):
                    full_meta = read_db_metadata(state.db_name)
                    if full_meta: table_names = list(full_meta.keys())
                
                schema_min = f"TABLES: {', '.join(table_names)}" if table_names else "No tables found."
                
                # Discovered Values (Semantic matching results)
                disc_values = getattr(state, "discovered_values", [])
                disc_str = "\n".join(disc_values) if disc_values else "No specific data values discovered yet."
                add_block("DISCOVERED_VALUES", "DISCOVERED DATA VALUES", disc_str)

                add_block("SCHEMA", "DATABASE SCHEMA", schema_str)
                add_block("SCHEMA_MINIMAL", "TABLE LIST", schema_min)
                processed_kwargs.setdefault("schema_path", schema_str)

        # 4. Process Keyword Arguments (with JSON file loading)
        for key, value in kwargs.items():
            if isinstance(value, str) and value.startswith("file://"):
                json_path = value.replace("file://", "")
                processed_kwargs[key] = self._get_cached_json_schema(json_path)
            else:
                processed_kwargs[key] = value

        # 5. Generate Messages
        messages = []
        if "messages" in template_data:
            for msg in template_data["messages"]:
                content = msg.get("content", "")
                try:
                    # Inject variables into template
                    formatted_content = content.format(**processed_kwargs)
                except KeyError as e:
                    raise KeyError(f"Missing argument for prompt '{prompt_name}': {e}")

                messages.append(
                    {"role": msg.get("role", "user"), "content": formatted_content}
                )
        return messages

    def _get_cached_json_schema(self, file_path: str) -> str:
        """Load a JSON file and return it as a formatted string, caching results."""
        abs_path = os.path.abspath(file_path)

        if abs_path not in PromptLoader._JSON_FILE_CACHE:
            if not os.path.exists(abs_path):
                return f"[File not found: {abs_path}]"

            try:
                with open(abs_path, encoding="utf-8") as f:
                    data = json.load(f)

                from .utils import format_schema_to_str
                result = format_schema_to_str(data)
                PromptLoader._JSON_FILE_CACHE[abs_path] = result
            except Exception as e:
                return f"[Error loading file {abs_path}: {e}]"

        return PromptLoader._JSON_FILE_CACHE[abs_path]
