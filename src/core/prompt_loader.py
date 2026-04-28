import json
import os

import yaml

from .paths import PIPELINE_CONFIG, PROMPTS_DIR
from core.logger import Logger


class SafeDict(dict):
    """A dictionary that returns the key wrapped in braces for missing keys."""
    def __missing__(self, key):
        return "{" + key + "}"

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
            from core.paths import InstancePaths, DIALECT_RULES
            from core.utils import format_execution_results, format_schema_to_str, read_db_metadata
            
            # Identity & Dialect
            val_dialect = getattr(state, "dialect", "sqlite")
            processed_kwargs.update({
                "DIALECT": val_dialect.capitalize(),
                "dialect": val_dialect,
                "iteration_count": getattr(state, "iteration_count", 0),
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
                    # Check if nested or flat
                    target = strategies.get("strategies", strategies) if isinstance(strategies.get("strategies"), dict) else strategies
                    
                    primary = target.get("primary", [])
                    alt = target.get("alternative", [])
                    risks = target.get("semantic_risks", [])
                    
                    if primary:
                        strat_str = f"PRIMARY STRATEGY:\n" + "\n".join([f"  - {s}" for s in primary])
                    if alt:
                        strat_str += f"\n\nALTERNATIVE STRATEGY:\n" + "\n".join([f"  - {s}" for s in alt])
                    if risks:
                        strat_str += f"\n\nSEMANTIC RISKS:\n" + "\n".join([f"  - {r}" for r in risks])
                    
                    # Also include concept mapping if present for better context
                    mapping = strategies.get("concept_mapping", [])
                    if mapping:
                        m_str = "\n".join([f"  - {m.get('concept')}: {m.get('mapped_to')} ({m.get('source_type')})" for m in mapping])
                        strat_str += f"\n\nCONCEPT MAPPING:\n{m_str}"
                else:
                    strat_str = str(strategies)
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
            if prev_sql and "-- CONCEPT UNAVAILABLE" in prev_sql:
                prev_sql = ""
                
            add_block("previous_iterated_SQL", "PREVIOUSLY ITERATED SQL", prev_sql)
            processed_kwargs.update({
                "previous_iterated_SQL": prev_sql,
                "previous_iterated_sql": prev_sql,
                "previous_sql": prev_sql,
                "sql": prev_sql,
                "chosen_query": prev_sql,
                "previous_sql_label": "### PREVIOUS SQL" if prev_sql else ""
            })
            # Feedback & Learning Signal
            combined_fb = getattr(state, "combined_feedback", "") or getattr(state, "critic_feedback", "")
            add_block("previous_feedback", "CRITIC FEEDBACK", combined_fb)
            add_block("combined_feedback", "COMBINED DIAGNOSTIC FEEDBACK", combined_fb)
            
            # Intent Analyzer Output
            intent = getattr(state, "structured_intent", {})
            intent_str = ""
            if intent:
                intent_items = [f"- **{k.replace('_', ' ').title()}**: {v}" for k, v in intent.items()]
                intent_str = "\n".join(intent_items)
            add_block("INTENT", "SEMANTIC INTENT (Structured)", intent_str)
            
            l_type = getattr(state, "learning_type", "unknown")
            add_block("LEARNING_TYPE", "LEARNING SIGNAL", f"Type: {l_type}")
            
            # Strategy Critique (Tasks 11+)
            plan_crit = getattr(state, "plan_critique", {})
            plan_fb = plan_crit.get("feedback", "") if isinstance(plan_crit, dict) else str(plan_crit)
            add_block("plan_feedback", "STRATEGY CRITIC FEEDBACK", plan_fb)
            add_block("PLAN_CRITIQUE", "STRATEGY CRITIC FEEDBACK", plan_fb)
            
            # Action Plan Feedback (Task 14)
            prev_plan = json.dumps(state.strategies, indent=2) if getattr(state, "strategies", None) else "No previous plan."
            processed_kwargs.update({
                "PREVIOUS_ACTION_PLAN": prev_plan,
                "FEEDBACK_ON_PREVIOUS_ACTION_PLAN": plan_fb if plan_fb else "No feedback available."
            })
            
            s_tables = getattr(state, "required_tables", [])
            add_block("STRATEGY_TABLES", "MANDATORY STRATEGY TABLES", "\n".join(f"- {t}" for t in s_tables) if s_tables else "")
            
            req_actions = getattr(state, "required_actions", [])
            req_str = "\n".join(f"- {a}" for a in req_actions) if req_actions else ""
            add_block("required_actions", "MANDATORY FIXES (MUST APPLY)", req_str)
            
            processed_kwargs.update({
                "learning_type": l_type,
                "combined_feedback": combined_fb,
                "required_actions": req_actions,
                # Task 2: Progressive Retrieval Variables
                "ALL_TABLE_NAMES": getattr(state, "all_table_names", []),
                "SELECTED_TABLES": getattr(state, "selected_tables", []),
                "ALL_COLUMNS_FETCHED": getattr(state, "all_columns_fetched", False),
                "SELECTED_COLUMNS": getattr(state, "selected_columns", {}),
                "SCHEMA_INFO": format_schema_to_str(state.schema_info),
                "FULL_SCHEMA": format_schema_to_str(getattr(state, "full_schema_info", {}), detailed=False),
                "VARIANT_SCHEMA_HINTS": getattr(state, "variant_schema_hints", "No variant structure discovered yet."),
                "all_tables": getattr(state, "all_tables", ""),
                "structured_pruning": getattr(state, "structured_pruning", {}),
                "REFERENCE_DATE": getattr(state, "reference_date", "2017-01-01")
            })

            # --- Label-based blocks for prompts ---
            # Task 13: Unified Single-Source Schema (Now PRUNED + COMPRESSED)
            pruned_schema = getattr(state, "schema_info", {})
            add_block("SCHEMA", "DATABASE SCHEMA (Pruned & Compressed)", format_schema_to_str(pruned_schema, mode="compressed"))
            
            # Keep full schema available if explicitly requested by a prompt under {full_schema}
            full_schema = getattr(state, "full_schema_info", {})
            add_block("full_schema", "FULL DATABASE INVENTORY (Compressed)", format_schema_to_str(full_schema, detailed=False))
            
            # Minimal Schema for Bootstrapping (Table names only)
            all_tables = getattr(state, "all_table_names", [])
            minimal_schema = f"Discovered Tables: {', '.join(all_tables)}" if all_tables else "No tables discovered yet."
            add_block("SCHEMA_MINIMAL", "SCHEMA OVERVIEW", minimal_schema)

            # --- ADAPTIVE RECOVERY VARIABLES (Tasks 1, 2, 4) ---
            failed_concepts = getattr(state, "failed_concepts", [])
            if failed_concepts:
                fc_str = "\n".join(f"  - {c}" for c in failed_concepts)
                processed_kwargs["FAILED_CONCEPTS"] = (
                    f"### FAILED CONCEPTS (MUST RE-EVALUATE)\n"
                    f"The following concepts could NOT be mapped to valid schema columns.\n"
                    f"You MUST find alternative sources for each:\n{fc_str}\n"
                )
            else:
                processed_kwargs["FAILED_CONCEPTS"] = ""

            blocked_tables = getattr(state, "blocked_tables", [])
            if blocked_tables:
                bt_str = "\n".join(f"  - {t}" for t in blocked_tables)
                processed_kwargs["BLOCKED_TABLES"] = (
                    f"### BLOCKED TABLES (DO NOT USE)\n"
                    f"These tables caused column-not-found errors and are banned:\n{bt_str}\n"
                )
            else:
                processed_kwargs["BLOCKED_TABLES"] = ""

            # --- VARIANT METADATA (Snowflake) ---
            v_req = getattr(state, "variant_required", [])
            v_hints = []
            if v_req:
                v_hints.append("### DISCOVERED VARIANT SUBSTRUCTURES")
                for item in v_req:
                    col = item.get("column", "Unknown")
                    status = item.get("status", "unknown")
                    keys = item.get("keys", [])
                    
                    hint = f"{col} contains:"
                    if keys:
                        if isinstance(keys, dict):
                            for k, v in keys.items():
                                hint += f"\n  - {k} ({v})"
                        else:
                            for k in keys:
                                hint += f"\n  - {k}"
                    else:
                        hint += f"\n  - (No keys discovered, status: {status})"
                    v_hints.append(hint)
            
            v_hints_str = "\n\n".join(v_hints) if v_hints else "No variant substructures discovered."
            processed_kwargs["VARIANT_SCHEMA_HINTS"] = v_hints_str
            processed_kwargs["VARIANT_SOURCES"] = v_hints_str # Alias for consistency

            # EDA Report (Task 7: Statistical validation)
            from core.data_iq import generate_eda_report
            eda_str = generate_eda_report(getattr(state, "execution_result", None))
            
            add_block("EDA_REPORT", "EXPLORATORY DATA ANALYSIS (EDA) REPORT", eda_str)
            processed_kwargs.setdefault("EDA_REPORT", eda_str)

            # Dialect Instructions (Modularized by agent type)
            try:
                with open(DIALECT_RULES) as f:
                    all_rules = yaml.safe_load(f)
                rules = all_rules.get(val_dialect, all_rules.get("sqlite", {}))
                
                # Pick instructions based on agent role
                if "planner" in prompt_name:
                    instr = rules.get("planner_instructions", "")
                elif "critic" in prompt_name:
                    instr = rules.get("critic_instructions", "")
                else:
                    instr = rules.get("builder_instructions", rules.get("instructions", ""))
                
                add_block("DIALECT_INSTRUCTIONS", f"{val_dialect.upper()} RULES", instr)
                processed_kwargs.setdefault("dialect_instructions", instr)
            except Exception: pass
            
            # Dialect Constraints (Learned Memory)
            constraints = getattr(state, "dialect_constraints", []) # Current run constraints
            from core.dialect_manager import DialectManager
            dm = DialectManager()
            grouped = dm.get_constraints(val_dialect, group_by_category=True)
            
            blocks = []
            for cat, rules in grouped.items():
                rule_list = "\n".join(f"- {r}" for r in rules)
                blocks.append(f"[{cat}]\n{rule_list}")
            
            const_str = "\n\n".join(blocks) if blocks else ""
            add_block("DIALECT_CONSTRAINTS", "DIALECT CONSTRAINTS (LEARNED)", const_str)
            processed_kwargs.setdefault("dialect_constraints", const_str)

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
                # --- TASK 2: SCHEMA CONTEXT LOGIC (PRIVACY & ENFORCEMENT) ---
                if prompt_name == "query_planner":
                    # Planner gets detailed relevant columns ONLY
                    if not state.selected_columns and not state.schema_info:
                        Logger.log("🛑 [PromptLoader] Planner blocked: No schema information available.", level="ERROR")
                        schema_ctx = "FAILED: No columns retrieved."
                        processed_kwargs["SCHEMA"] = "" # Trigger guard later
                    else:
                        # Task: Handle potential pruning mismatch or empty schema_info
                        schema_info_to_format = state.schema_info
                        
                        if not schema_info_to_format and state.selected_columns:
                            # Robust fallback: Reconstruct from full_schema_info using selected_columns
                            Logger.log("⚠️ [PromptLoader] schema_info empty but columns selected. Attempting reconstruction from full_schema_info.", level="WARN")
                            from core.utils import normalize_identifier
                            norm_full = {normalize_identifier(k): v for k, v in state.full_schema_info.items()}
                            reconstructed = {}
                            for t, cols in state.selected_columns.items():
                                norm_t = normalize_identifier(t)
                                if norm_t in norm_full:
                                    details = norm_full[norm_t].copy()
                                    allowed = [c.upper() for c in cols]
                                    details["columns"] = [
                                        c for c in details.get("columns", []) 
                                        if c.get("column_name", "").upper() in allowed
                                    ]
                                    reconstructed[t] = details
                            schema_info_to_format = reconstructed

                        selected_detailed = format_schema_to_str(schema_info_to_format)
                        
                        # Task: ONLY inject RELEVANT schema. Removed full schema summary as per user request.
                        if not selected_detailed or len(selected_detailed.strip()) < 10:
                            Logger.log("🛑 [PromptLoader] Formatted schema is empty or insufficient.", level="ERROR")
                            schema_ctx = "FAILED: No detailed columns formatted."
                            processed_kwargs["SCHEMA"] = ""
                        else:
                            schema_ctx = (
                                "### RELEVANT SCHEMA (Detailed)\n"
                                f"{selected_detailed}"
                            )
                else:
                    # Final fallback for other agents (SQLBuilder, etc.)
                    schema_ctx = format_schema_to_str(state.schema_info)
                    
                    # FALLBACK: If pruned schema was insufficient (detected via failure loop)
                    # We inject the COMPLETE schema for the selected tables from full_schema_info
                    failed_grounding = any("COLUMN_NOT_FOUND" in str(f) for f in getattr(state, "failure_history", []))
                    if failed_grounding:
                        full_info = getattr(state, "full_schema_info", {})
                        if full_info:
                            # Filter full_info to only the tables we are currently using
                            targeted_full = {t: full_info[t] for t in state.selected_tables if t in full_info}
                            if targeted_full:
                                Logger.log("⚠️ Pruned schema insufficient. Injecting COMPLETE table metadata as fallback.")
                                schema_ctx = (
                                    "### PRUNED SCHEMA (Insufficient)\n"
                                    f"{schema_ctx}\n\n"
                                    "### COMPLETE METADATA FOR TARGETED TABLES (Fallback)\n"
                                    f"{format_schema_to_str(targeted_full)}"
                                )
                
                processed_kwargs["SCHEMA_CONTEXT"] = schema_ctx
                if not schema_ctx.startswith("FAILED:"):
                    processed_kwargs["SCHEMA"] = schema_ctx
                else:
                    processed_kwargs["SCHEMA"] = "" # Keep empty to trigger guard
                processed_kwargs.setdefault("schema_path", schema_str)

                # --- TASK 7: FIX FLAGS INJECTION ---
                fix_flags = getattr(state, "fix_flags", {})
                flags_str = ""
                if fix_flags:
                    flags_str = "### ACTIVE FIX FLAGS (MANDATORY):\n"
                    for k, v in fix_flags.items():
                        flags_str += f"- {k.replace('_', ' ').upper()}: {v}\n"
                processed_kwargs["FIX_FLAGS"] = flags_str

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
                
                # Task 3: Stop if schema is required but missing (Only if state is provided, skip for verification)
                if state and "{SCHEMA}" in content and not processed_kwargs.get("SCHEMA"):
                    Logger.log(f"🛑 [PromptLoader] Schema required for '{prompt_name}' but NOT retrieved. ABORTING.", level="ERROR")
                    raise ValueError(f"Schema retrieval failed for {prompt_name}")

                try:
                    # Task 7: Primary Safe Formatting
                    formatted_content = content.format_map(SafeDict(processed_kwargs))
                except (KeyError, ValueError, IndexError) as e:
                    # Task 7 Guard: Safe Mode Retry
                    Logger.log(f"⚠️ Prompt formatting issues detected in '{prompt_name}' ({str(e)}). Switching to safe mode.", level="WARN")
                    try:
                        # Fallback: Escaping all braces and use SafeDict
                        # This is a bit aggressive but ensures completion
                        safe_content = content.replace("{", "{{").replace("}", "}}")
                        # Need to un-escape the variables we want to keep?
                        # Actually, better to just log and use SafeDict which handles missing keys.
                        # The "unmatched {" error happens in format_map too if the content has a stray {
                        
                        # Better fallback: regex out likely variables or just catch the specific Specc error
                        Logger.log("Prompt formatting fallback triggered")
                        formatted_content = content # Return literal if formatted fails
                    except Exception:
                        formatted_content = content # Literal fallback
                except Exception as e:
                    Logger.log(f"🛑 Critical prompt formatting failure: {str(e)}")
                    formatted_content = content

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

                from core.utils import format_schema_to_str
                result = format_schema_to_str(data)
                PromptLoader._JSON_FILE_CACHE[abs_path] = result
            except Exception as e:
                return f"[Error loading file {abs_path}: {e}]"

        return PromptLoader._JSON_FILE_CACHE[abs_path]
