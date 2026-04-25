import yaml
import os
import importlib
from core.agent_base import AgentState, BaseAgent
from agents.generic_agent import GenericAgent
from core.logger import Logger
from core.utils import read_db_metadata

class WorkflowEngine:
    """
    Orchestrates the execution of multiple agents based on a YAML workflow configuration.
    """

    def __init__(self, workflow_path: str, llm_service):
        self.workflow_path = workflow_path
        self.llm = llm_service
        self.workflow = self._load_workflow()
        self.agent_cache = {}

    def _load_workflow(self):
        if not os.path.exists(self.workflow_path):
            raise FileNotFoundError(f"Workflow file not found: {self.workflow_path}")
        with open(self.workflow_path, "r") as f:
            return yaml.safe_load(f)

    def _get_agent(self, step_config):
        step_id = step_config["id"]
        
        # 1. Specialized Agent Class
        if "agent_class" in step_config:
            class_name = step_config["agent_class"]
            # Search in common locations
            modules = ["agents.query_planner", "agents.table_selector", "agents.sql_builder"]
            for mod_name in modules:
                try:
                    module = importlib.import_module(mod_name)
                    agent_cls = getattr(module, class_name)
                    return agent_cls(self.llm)
                except (ImportError, AttributeError):
                    continue
            raise ValueError(f"Could not find agent class {class_name}")

        # 2. Generic Prompt-Driven Agent
        elif "prompt" in step_config:
            return GenericAgent(
                step_id=step_id,
                prompt_name=step_config["prompt"],
                output_key=step_config.get("output_key"),
                state_field=step_config.get("state_field"),
                llm_service=self.llm,
                max_tokens=step_config.get("max_tokens")
            )
        
        raise ValueError(f"Step {step_id} must have either 'agent_class' or 'prompt'")

    def _run_sanity_check(self, state):
        Logger.log_stage_header("🔍 SANITARY CHECK & PRE-FLIGHT")
        
        # 1. System Config
        pipeline = self.workflow.get("pipeline", [])
        Logger.log(f"🟢 **MECHANISM**: `Prompt-Driven Tool-Agentic`")
        Logger.log(f"🟢 **PIPELINE**: `{' -> '.join([s['id'] for s in pipeline])}`")
        Logger.log(f"🟢 **MODEL**: `{state.model_name}`")
        
        # 2. Database & Resource Paths
        db_path = getattr(state, "db_path", "N/A")
        from core.paths import InstancePaths
        meta_path = str(InstancePaths.db_metadata(state.db_name))
        
        Logger.log(f"🟢 **DB PATH**: `{db_path}`")
        if os.path.exists(meta_path):
            Logger.log(f"🟢 **METADATA**: `Loaded ({state.db_name})`")
        else:
            Logger.log(f"🟡 **METADATA**: `Missing - Will Generate`", "WARN")

        # 3. Schema Stats
        schema = state.schema_info or state.full_schema_info
        if not schema:
            from core.utils import read_db_metadata
            schema = read_db_metadata(state.db_name)
        
        if schema:
            tbl_count = len(schema.get("tables", [])) if isinstance(schema, dict) else len(schema)
            Logger.log(f"🟢 **SCHEMA**: `{tbl_count} tables detected`")
        
        Logger.log("\n" + "=" * 40 + "\n")

    def run(self, state: AgentState) -> AgentState:
        # We start directly without heavy headers
        
        # Perform Startup Report
        self._run_sanity_check(state)
        
        for step in self.workflow.get("pipeline", []):
            step_id = step["id"]
            Logger.log_call(f"Workflow Step: {step_id}")
            
            agent = self._get_agent(step)
            state = agent.run(state)
            
            if getattr(state, "stop_requested", False):
                Logger.log("Workflow stop requested by agent.")
                break
        
        # 🎯 FINAL EVALUATION FLAG
        self._run_evaluation(state)
                
        return state

    def _run_evaluation(self, state):
        """Compares generated SQL results with ground truth (SQL or CSV) if available."""
        import os
        import pandas as pd
        import json
        import re
        from pathlib import Path
        
        instance_id = state.instance_id
        gold_sql_path = os.path.join("gold", "sql", f"{instance_id}.sql")
        gold_csv_dir = os.path.join("gold", "exec_result")
        eval_standard_path = os.path.join("gold", "spider2lite_eval.jsonl")

        # 1. Resolve Gold Dataframes (Multiple options possible)
        gold_pds = []
        
        # Try Gold SQL first (executes on target DB)
        if os.path.exists(gold_sql_path):
            try:
                with open(gold_sql_path, 'r', encoding='utf-8') as f:
                    gold_sql = f.read()
                
                if state.dialect == "sqlite":
                    from core.sqlite_service import SQLiteService
                    svc = SQLiteService(state.db_path)
                    gold_res = svc.execute_query(gold_sql, sampling=False)
                    if not gold_res.error_message:
                        gold_pds.append(pd.DataFrame(gold_res.rows, columns=gold_res.columns))
                    else:
                        Logger.log(f"Gold SQL Execution failed: {gold_res.error_message}", "DEBUG")
            except Exception as e:
                Logger.log(f"Evaluation Error (SQL): {e}", "DEBUG")

        # Supplement with Gold CSVs if SQL missing or to be thorough
        if os.path.exists(gold_csv_dir):
            csv_pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
            try:
                for f in os.listdir(gold_csv_dir):
                    if csv_pattern.match(f):
                        p = os.path.join(gold_csv_dir, f)
                        gold_pds.append(pd.read_csv(p))
            except Exception as e:
                Logger.log(f"Evaluation Error (CSV Load): {e}", "DEBUG")

        # Always show header for consistency
        Logger.log_stage_header("🎯 GROUND TRUTH EVALUATION")

        if not gold_pds:
            Logger.log(f"ℹ️ Skipping evaluation: No gold SQL or CSV found for '{instance_id}'", "WARN")
            return

        try:
            gen_res = state.execution_result
            if not gen_res or gen_res.error_message:
                Logger.log_comparison(False)
                return

            gen_pd = pd.DataFrame(gen_res.rows, columns=gen_res.columns)
            
            # Load metadata for column constraints (Spider 2.0 specificity)
            condition_cols = None
            ignore_order = True
            if os.path.exists(eval_standard_path):
                with open(eval_standard_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        meta = json.loads(line)
                        if meta.get("instance_id") == instance_id:
                            condition_cols = meta.get("condition_cols")
                            ignore_order = meta.get("ignore_order", True)
                            break

            # Reuse official comparison logic
            import sys
            import os
            root_dir = os.getcwd()
            if root_dir not in sys.path:
                sys.path.append(root_dir)
            
            try:
                from gold.evaluate import compare_multi_pandas_table
                score = compare_multi_pandas_table(gen_pd, gold_pds, condition_cols, ignore_order)
            except ImportError:
                # Try relative if in a subdirectory
                sys.path.append(os.path.join(root_dir, "gold"))
                from evaluate import compare_multi_pandas_table
                score = compare_multi_pandas_table(gen_pd, gold_pds, condition_cols, ignore_order)
            
            is_correct = (score == 1)
            Logger.log_comparison(is_correct)
            
            if not is_correct:
                Logger.log(f"Generated row count: {len(gen_pd)}")
                Logger.log(f"Gold variant count: {len(gold_pds)}")
            
        except Exception as e:
            Logger.log(f"Evaluation Logic Error: {e}", "ERROR")
