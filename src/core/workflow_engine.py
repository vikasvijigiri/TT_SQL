import yaml
import os
import json
from core.agent_base import AgentState, BaseAgent
from agents.generic_agent import GenericAgent
from core.logger import Logger
from core.utils import read_db_metadata
from core.sql_normalizer import SQLNormalizer
from core.data_iq import analyze_result

class WorkflowEngine:
    """
    Orchestrates the execution of multiple agents based on a YAML workflow configuration.
    """

    def __init__(self, workflow_path: str, llm_service):
        self.workflow_path = workflow_path
        self.llm = llm_service
        self.workflow = self._load_workflow()
        self.stages = self.workflow.get("stages", [])
        self.features = self.workflow.get("features", {})
        self.agent_cache = {}

    def _get_stage_config(self, stage_id: str) -> dict:
        """Returns the configuration for a specific stage from workflow.yaml."""
        for stage in self.stages:
            if stage["id"] == stage_id:
                return stage
        return {}

    def _load_workflow(self):
        if not os.path.exists(self.workflow_path):
            raise FileNotFoundError(f"Workflow file not found: {self.workflow_path}")
        with open(self.workflow_path, "r") as f:
            return yaml.safe_load(f)

    def _get_agent(self, step_config):
        step_id = step_config["id"]
        
        # All agents are now Generic Prompt-Driven Agents
        if "prompt" in step_config:
            return GenericAgent(
                step_id=step_id,
                prompt_name=step_config["prompt"],
                output_key=step_config.get("output_key"),
                state_field=step_config.get("state_field"),
                llm_service=self.llm,
                max_tokens=step_config.get("max_tokens")
            )
        
        raise ValueError(f"Step {step_id} must have a 'prompt' configured.")

    def _run_sanity_check(self, state):
        Logger.log_section("Settings and sanitary checks")
        
        try:
            # 1. LLM Readiness (Using existing service)
            if not self.llm.enabled:
                raise Exception(f"LLM Credentials Missing for model: {state.model_name}")
            Logger.log(f"1. Model: {state.model_name} (status: active)")


            # 2. Database Connectivity
            dialect = getattr(state, "dialect", "sqlite")
            db_name = state.db_name
            
            if dialect == "sqlite":
                if not os.path.exists(state.db_path):
                    raise Exception(f"SQLite IO Error: File not found at {state.db_path}")
                Logger.log(f"2. Local Target: {os.path.basename(state.db_path)} (status: verified)")
            elif dialect == "snowflake":
                from core.sf_service import SnowflakeService
                svc = SnowflakeService()
                if not svc.get_connection():
                    raise Exception(f"Snowflake Connection Error: Validation failed for {db_name}")
                Logger.log(f"2. Cloud Target: SNOWFLAKE://{db_name} (status: authenticated)")
            elif dialect == "bigquery":
                from core.bq_service import BigQueryService
                svc = BigQueryService()
                svc.get_client() 
                Logger.log(f"2. Cloud Target: BIGQUERY://{db_name} (status: authenticated)")

        except Exception as e:
            Logger.log_error(f"Sanity Check Failed: {str(e)}")
            # Write error and stop
            raise SystemExit(f"FATAL: Sanity check failed - {str(e)}")

    def run(self, state: AgentState) -> AgentState:
        """
        Enforced STRICT state-machine pipeline (Task 7).
        INIT → SCHEMA_READY → PLAN_READY → SQL_READY → EXECUTED → VALIDATED
        """
        from core.tool_registry import ToolRegistry
        from core.utils import validate_json_response, write_sql_to_file, write_csv_to_file
        
        state.current_step = "INIT"
        Logger.log_state("INIT", "STARTED")
        self._run_sanity_check(state)

        # ─── 1. SchemaExtractor (Unified Discovery) ─────────────────────────
        Logger.log_step("SchemaExtractor", "START")
        try:
            ToolRegistry.fetch_schema(state, params={"full": True, "sample_rows": True})
            if not state.all_table_names:
                raise Exception("No tables discovered in database.")
            Logger.log_step("SchemaExtractor", "SUCCESS")
        except Exception as e:
            state.pipeline_failure_reason = f"SchemaExtractor failed: {str(e)}"
            Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
            return state

        state.current_step = "SCHEMA_READY"
        Logger.log_state("STARTED", "SCHEMA_READY")

        # ─── 1.1 Reference Date Inference (Task 15) ─────────────────────────
        self._infer_reference_date(state)
        Logger.log(f"Using reference_date = {state.reference_date}")


        # ─── 1.2 Table Pruner (Relevancy Filtering) [PAUSED BY USER REQUEST] ───
        Logger.log("[TablePruner] Paused. Passing full compressed schema to all agents.")

        # ─── 1.2.5 Discover Variant Keys ──────────────────────────────────
        if getattr(state, "dialect", "sqlite") == "snowflake":
            Logger.log_step("VariantDiscovery", "START")
            from core.variant_inspector import VariantInspector
            vi = VariantInspector(state.db_name)
            found_variants = 0
            for t_name, t_info in state.schema_info.items():
                for c in t_info.get("columns", []):
                    if "VARIANT" in str(c.get("type", "")).upper() and not c.get("variant_keys"):
                        try:
                            inspection = vi.inspect_column(t_name, c["column_name"])
                            keys = inspection.get("keys", [])
                            c["variant_keys"] = keys
                            if keys: found_variants += 1
                        except BaseException as e:
                            Logger.log(f"[VariantDiscovery] Error on {t_name}.{c['column_name']}: {e}", level="WARN")
            Logger.log(f"[VariantDiscovery] Discovered keys for {found_variants} VARIANT columns.")

        # ─── 1.5 IntentAnalyzer (Semantic Baseline) ─────────────────────────
        Logger.log_step("IntentAnalyzer", "START")
        intent_agent = GenericAgent("IntentAnalyzer", "intent_analyzer", state_field="structured_intent", llm_service=self.llm)
        state = intent_agent.run(state)
        
        # Intent Structural Validation
        intent_val = validate_json_response(
            state.structured_intent,
            required_keys=["entities", "metrics", "pre_filters", "post_filters", "filter_grain", "aggregation_steps", "aggregation_target", "answer_grain", "grouping_required", "join_required", "edge_cases", "ambiguities"]
        )
        if intent_val["status"] != "SUCCESS":
            state.pipeline_failure_reason = f"IntentAnalyzer contract violation: {intent_val['reason']}"
            Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
            return state
            
        Logger.log(f"[IntentAnalyzer] Intent mapped: {state.structured_intent.get('answer_grain')}")

        # ─── 1.75 GroundingValidator (New) ───────────────────────────────
        Logger.log_step("GroundingValidator", "START")
        grounding_agent = GenericAgent("GroundingValidator", "grounding_validator", state_field="grounded_intent", llm_service=self.llm)
        state = grounding_agent.run(state)
        
        if not state.grounded_intent:
            state.grounded_intent = state.structured_intent

        # ─── 2. QueryPlanner & QueryCritic Loop (Strategy Refinement) ──────
        max_plan_iterations = 3
        if not hasattr(state, "plan_critique_history"):
            state.plan_critique_history = []
        plan_iter = 0
        plan_approved = False
        
        while plan_iter < max_plan_iterations and not plan_approved:
            plan_iter += 1
            Logger.log_stage_header("Strategy Planning & Validation", iteration=plan_iter)
            
            # 2a. QueryPlanner
            Logger.log_step("QueryPlanner", "START")
            planner = GenericAgent("QueryPlanner", "query_planner", state_field="strategies", llm_service=self.llm)
            state = planner.run(state)
            
            if state.pipeline_failure_reason:
                Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                return state

            # Planner Structural Validation
            plan_validation = validate_json_response(
                state.strategies, 
                required_keys=["strategies", "concept_mapping", "confidence", "missing_elements", "expansion_required", "requested_tables"],
                allowed_values={"confidence": ["high", "medium", "low"]}
            )
            if plan_validation["status"] != "SUCCESS":
                Logger.log(f"[Validator] QueryPlanner → FAIL ({plan_validation['reason']})", level="ERROR")
                state.pipeline_failure_reason = f"Planner contract violation: {plan_validation['reason']}"
                Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                return state
            
            Logger.log("[Validator] QueryPlanner → PASS")

            # 2b. QueryCritic (The Gatekeeper)
            if self.features.get("query_critic", True):
                Logger.log_step("QueryCritic", "START")
                critic = GenericAgent("QueryCritic", "query_critic", state_field="plan_critique", llm_service=self.llm)
                state = critic.run(state)
                
                # 1. Structural Validation (JSON contract)
                crit_val = validate_json_response(
                    state.plan_critique,
                    required_keys=["is_valid", "logical_fit", "feedback", "missing_logical_steps", "grounding_errors", "suggested_fix"],
                    allowed_values={"logical_fit": ["pass", "pass_with_risk", "fail"]}
                )
                if crit_val["status"] != "SUCCESS":
                    state.pipeline_failure_reason = f"QueryCritic contract violation: {crit_val['reason']}"
                    Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                    return state
                    
                # 2. Semantic Validation (Critic's judgment)
                if state.plan_critique.get("is_valid", False):
                    Logger.log("[QueryCritic] Plan Validated Successfully")
                    plan_approved = True
                else:
                    fb = state.plan_critique.get('feedback', '')
                    s_fix = state.plan_critique.get('suggested_fix', '')
                    if s_fix:
                        fb += f"\nSuggested Fix: {s_fix}"
                        state.plan_critique['feedback'] = fb
                    
                    Logger.log(f"⚠️ QueryCritic REJECTED plan (Iteration {plan_iter}/{max_plan_iterations}): {fb}", level="WARN")

                    # ─── AUTO-EXTEND PLAN ITERATIONS IF PROGRESSING ───
                    if plan_iter == max_plan_iterations and max_plan_iterations < 7:
                        last_feedback = ""
                        if len(state.plan_critique_history) > 0:
                            last_feedback = str(state.plan_critique_history[-1].get("feedback", "")).strip()
                        
                        current_feedback = str(state.plan_critique.get("feedback", "")).strip()
                        has_suggested_fix = bool(state.plan_critique.get("suggested_fix"))
                        feedback_changed = current_feedback != last_feedback
                        
                        if has_suggested_fix or feedback_changed:
                            Logger.log(f"🔄 Plan Progress detected (feedback changed: {feedback_changed}, fix suggested: {has_suggested_fix}). Auto-extending iterations from {max_plan_iterations} to {max_plan_iterations + 2}.")
                            max_plan_iterations += 2

                    state.plan_critique_history.append(state.plan_critique)

                    # ─── NEW: MissingElementsResolver Agent ───
                    strategies_data = getattr(state, "strategies", {})
                    if isinstance(strategies_data, dict) and strategies_data.get("missing_elements"):
                        Logger.log_step("MissingElementsResolver", "START")
                        resolver = GenericAgent("MissingElementsResolver", "missing_elements_resolver", output_key=None, state_field="resolver_output", llm_service=self.llm)
                        state = resolver.run(state)
                        
                        if hasattr(state, "resolver_output") and isinstance(state.resolver_output, dict):
                            state.resolved_elements = state.resolver_output.get("resolved_elements", [])
                            updated_missing = state.resolver_output.get("updated_missing_elements", [])
                            state.strategies["missing_elements"] = updated_missing
                            Logger.log(f"[MissingElementsResolver] Resolved {len(state.resolved_elements)} elements.")
                        else:
                            state.resolved_elements = []

                    if plan_iter >= max_plan_iterations:
                        state.pipeline_failure_reason = f"QueryCritic refused plan after {max_plan_iterations} attempts: {state.plan_critique.get('feedback')}"
                        Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                        return state
            else:
                plan_approved = True

        state.current_step = "PLAN_READY"
        Logger.log_state("SCHEMA_READY", "PLAN_READY")

        # ─── Builder <-> Critic Adaptive Loop ────────────────────────────
        max_sql_iterations = 3
        sql_iter = 0
        sql_approved = False
        
        while sql_iter < max_sql_iterations and not sql_approved:
            sql_iter += 1
            Logger.log(f"\n🔄 SQL ITERATION {sql_iter}/{max_sql_iterations}", to_file=False)

            # ─── 3. SQLBuilder ───────────────────────────────────────────────
            Logger.log_step("SQLBuilder", "START")
            builder = GenericAgent("SQLBuilder", "sql_builder", output_key="candidates", state_field="sql_candidates", llm_service=self.llm)
            state = builder.run(state)
            
            if state.pipeline_failure_reason or not state.sql_candidates:
                state.pipeline_failure_reason = state.pipeline_failure_reason or "SQLBuilder failed"
                Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                return state

            # ─── 3.25 SemanticFixLayer (NEW) ─────────────────────────────────
            Logger.log_step("SemanticFixLayer", "START")
            from core.semantic_fixer import apply_semantic_fixes, get_log_stats
            
            plan = state.strategies if hasattr(state, "strategies") else {}
            schema_meta = state.schema_info if hasattr(state, "schema_info") else {}
            raw_sql = state.sql_candidates[0].get("sql", "")
            
            fixed_sql = apply_semantic_fixes(plan, raw_sql, state.dialect, schema_meta)
            
            logs = get_log_stats()
            Logger.log(f"[SemanticFixLayer]\n"
                       f"- dedup_applied: {str(logs.get('dedup_applied', False)).lower()}\n"
                       f"- date_normalized: {str(logs.get('date_normalized', False)).lower()}\n"
                       f"- variant_corrected: {str(logs.get('variant_corrected', False)).lower()}\n"
                       f"- output_formatted: {str(logs.get('output_formatted', False)).lower()}")
                       
            state.sql_candidates[0]["sql"] = fixed_sql

            # ─── 3.5 SQL Normalization (NEW: Dialect-Aware AST transformation) ──
            Logger.log_step("SQLNormalizer", "START")
            raw_sql = state.sql_candidates[0].get("sql", "")
            normalizer = SQLNormalizer(state.dialect, reference_date=state.reference_date)
            normalized_sql = normalizer.normalize(raw_sql)
            
            state.chosen_query = normalized_sql
            
            # PERSIST: SQL (Task 12)
            write_sql_to_file(state.instance_id, state.db_name, state.chosen_query, state.model_name, dialect=state.dialect)
            
            state.current_step = "SQL_READY"
            if sql_iter == 1:
                Logger.log_state("PLAN_READY", "SQL_READY")

            # ─── 4. ExecutionEngine ──────────────────────────────────────────
            Logger.log_step("ExecutionEngine", "START")
            service = ToolRegistry._get_service(state)
            res = service.execute_query(state.chosen_query, sampling=False)
            
            state.execution_result = res
            
            # ─── 4.5 DataIQ (NEW: Result Validation) ──────────────────────────
            data_iq_analysis = analyze_result(res)
            state.output_audit_report = data_iq_analysis
            
            if res.error_message:
                Logger.log_step("ExecutionEngine", "FAILED", res.error_message[:50])
            else:
                Logger.log_step("ExecutionEngine", "SUCCESS")
                # PERSIST: Results (Task 12)
                write_csv_to_file(state.instance_id, state.db_name, res.rows, res.columns, state.model_name)
            
            state.current_step = "EXECUTED"
            if sql_iter == 1:
                Logger.log_state("SQL_READY", "EXECUTED")

            # ─── 5. SQLCritic (Mandatory Query Validation) ────────────────────
            if self.features.get("sql_critic", True):
                Logger.log_step("SQLCritic", "START")
                
                # TASK 8: Propagate SEMANTIC RISK
                semantic_risks = []
                if state.strategies:
                    semantic_risks = state.strategies.get("semantic_risks", []) or state.strategies.get("risks", [])
                
                eval_item = {
                    "id": 1, 
                    "sql": state.chosen_query, 
                    "execution": {"error": res.error_message, "row_count": res.row_count},
                    "data_iq": state.output_audit_report,
                    "semantic_risks": semantic_risks
                }
                state.audit_context = json.dumps([eval_item])
                
                critic = GenericAgent("SQLCritic", "sql_critic", state_field="crit_response", llm_service=self.llm)
                state = critic.run(state)
                
                # 1. Structural Validation (JSON contract)
                crit_val = validate_json_response(
                    state.crit_response,
                    required_keys=["is_valid", "logical_fit", "feedback", "missing_logical_steps", "grounding_errors", "suggested_fix"],
                    allowed_values={"logical_fit": ["pass", "pass_with_risk", "fail"]}
                )
                if crit_val["status"] != "SUCCESS":
                    state.pipeline_failure_reason = f"SQLCritic contract violation: {crit_val['reason']}"
                    Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                    return state
                    
                # 2. Semantic Validation (Critic's judgment)
                if not state.crit_response.get("is_valid", False):
                    fb = state.crit_response.get('feedback', '')
                    s_fix = state.crit_response.get('suggested_fix', '')
                    if s_fix:
                        fb += f"\nSuggested Fix: {s_fix}"
                    Logger.log(f"⚠️ SQLCritic REJECTED query (Iteration {sql_iter}/{max_sql_iterations}): {fb}", level="WARN")
                    
                    if not hasattr(state, "execution_error_history"):
                        state.execution_error_history = []
                        
                    # ─── AUTO-EXTEND ITERATIONS IF PROGRESSING ───
                    if sql_iter == max_sql_iterations and max_sql_iterations < 7:
                        last_error = ""
                        if len(state.execution_error_history) > 0:
                            prev_entry = state.execution_error_history[-1]
                            if "| Error: " in prev_entry and " | Feedback:" in prev_entry:
                                last_error = prev_entry.split("| Error: ")[1].split(" | Feedback: ")[0].strip()
                                
                        current_error = str(res.error_message).strip() if res.error_message else ""
                        has_suggested_fix = bool(state.crit_response.get("suggested_fix"))
                        error_changed = current_error != last_error

                        if has_suggested_fix or (current_error and error_changed):
                            Logger.log(f"🔄 Progress detected (new error: {error_changed}, fix suggested: {has_suggested_fix}). Auto-extending iterations from {max_sql_iterations} to {max_sql_iterations + 2}.")
                            max_sql_iterations += 2
                    
                    hist_entry = f"[Iteration {sql_iter}] Query: {state.chosen_query} | Error: {res.error_message} | Feedback: {fb}"
                    state.execution_error_history.append(hist_entry)
                    state.combined_feedback = fb
                    
                    if sql_iter >= max_sql_iterations:
                        state.pipeline_failure_reason = f"SQLCritic rejected output after {max_sql_iterations} attempts: {fb}"
                        Logger.log_pipeline_status(False, reason=state.pipeline_failure_reason)
                        return state
                else:
                    Logger.log("[SQLCritic] Output Validated Successfully")
                    sql_approved = True
            else:
                sql_approved = True

        return state

    def _infer_reference_date(self, state: AgentState):
        """
        Infers the reference date based on the latest timestamp in the dataset.
        """
        from core.tool_registry import ToolRegistry
        from core.logger import Logger
        
        # 1. Identify potential timestamp columns
        time_keywords = ["stamp", "date", "time", "created_at", "registered_at", "updated_at", "year"]
        candidates = []
        for table, info in state.all_schema_info.items() if hasattr(state, 'all_schema_info') else state.full_schema_info.items():
            for col in info.get("columns", []):
                name = col.get("column_name", "").lower()
                c_type = col.get("type", "").upper()
                if any(k in name for k in time_keywords) or any(k in c_type for k in ["DATE", "TIME", "STAMP"]):
                    candidates.append((table, col.get("column_name")))
        
        if not candidates:
            state.reference_date = "2017-01-01" # Default fallback
            return

        # 2. Try to fetch MAX value from candidates
        service = ToolRegistry._get_service(state)
        latest_date = None
        
        # Try top 5 candidates
        for table, col in candidates[:5]:
            try:
                # Sanitize table/col names
                q_table = f'"{table}"' if "." not in table else table
                q_col = f'"{col}"'
                query = f"SELECT MAX({q_col}) FROM {q_table}"
                res = service.execute_query(query)
                if not res.error_message and res.rows and res.rows[0][0]:
                    val = str(res.rows[0][0])
                    # Basic date validation
                    if len(val) >= 4:
                        if not latest_date or val > latest_date:
                            latest_date = val
            except:
                continue
        
        if latest_date:
            # Clean up if it's a full timestamp
            if " " in latest_date: latest_date = latest_date.split(" ")[0]
            if "T" in latest_date: latest_date = latest_date.split("T")[0]
            state.reference_date = latest_date
        else:
            state.reference_date = "2017-01-01"

