import yaml
import os
import json
from core.agent_base import AgentState, BaseAgent
from agents.generic_agent import GenericAgent
from core.logger import Logger
from core.utils import read_db_metadata
from core.sql_normalizer import SQLNormalizer
from core.data_iq import analyze_result
from core.query_decomposer import QueryDecomposer
from core.retriever import Retriever
from core.schema_indexer import SchemaIndexer
from core.schema_graph import SchemaGraph, JoinRanker
from core.semantic_mapper import StructureAwareMapper
from core.query_planner import QueryPlanner
from core.sql_generator import SQLGenerator
from core.validator import Validator, compute_confidence
from core.guardrails import Guardrails
from core.memory import Memory

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
        PRODUCTION-GRADE PIPELINE (Step 16 target architecture)
        WITH ITERATIVE LEARNING (QueryPlanner & QueryCritic)
        """
        from core.tool_registry import ToolRegistry
        from core.utils import validate_json_response, write_sql_to_file, write_csv_to_file, format_schema_to_str

        Logger.log_state("INIT", "STARTED")
        self._run_sanity_check(state)

        # 0. Components Initialization
        memory = Memory()
        service = ToolRegistry._get_service(state)
        indexer = SchemaIndexer(service)
        decomposer = QueryDecomposer()
        validator = Validator()
        guardrails = Guardrails()
        
        # 1. Schema Indexing & Enrichment
        Logger.log_step("SchemaIndexer", "START")
        fetch_res = ToolRegistry.fetch_schema(state, params={"full": True, "sample_rows": True})
        
        # Always run indexing to discover variant keys from samples (live or local)
        state.schema_info = indexer.index_schema(state.schema_info, skip_stats=fetch_res.get("is_local", False))
        
        if fetch_res.get("is_local", False):
            Logger.log("Enriched local metadata with discovered variant keys.")
        
        full_schema_str = format_schema_to_str(state.schema_info, mode="compressed")
        state.SCHEMA = full_schema_str # Always provide full schema to agents for reasoning
        
        # 1.5. Infer Reference Date
        self._infer_reference_date(state)
        Logger.log(f"Inferred Reference Date: {state.reference_date}")

        # Initialize Agents
        intent_agent = GenericAgent("IntentAnalyzer", "intent_analyzer", state_field="structured_intent", llm_service=self.llm)
        planner_agent = GenericAgent("QueryPlanner", "query_planner", state_field="strategies", llm_service=self.llm)
        critic_agent = GenericAgent("QueryCritic", "query_critic", llm_service=self.llm)
        generator_agent = GenericAgent("SQLGenerator", "grounded_sql_generator", output_key="sql", state_field="_temp_sql", llm_service=self.llm)
        sql_critic_agent = GenericAgent("SQLCritic", "sql_critic", llm_service=self.llm)

        # 2. Intent Analysis
        state = intent_agent.run(state)
        if getattr(state, "pipeline_failure_reason", None): return state
        
        # 3. Query Decomposition
        Logger.log_step("QueryDecomposer", "START")
        tasks = decomposer.decompose(state.structured_intent)
        
        # 4. Retrieval
        Logger.log_step("Retriever", "START")
        retriever = Retriever(state.schema_info, memory)
        candidates = retriever.retrieve(state.user_query, top_k=100)
        
        # 5. Iterative Execution Loop
        MAX_EXECUTION_ATTEMPTS = 3
        sql_approved = False
        
        # Ensure reference date is set
        if not getattr(state, "reference_date", None):
            state.reference_date = "2017-01-01" # Default or infer from DB context
        
        for exec_attempt in range(MAX_EXECUTION_ATTEMPTS):
            Logger.log_stage_header("Mapping & Planning", iteration=exec_attempt+1)
            
            # Consolidate feedback for agents
            if state.feedback_history:
                state.combined_feedback = "\n".join([str(fb) for fb in state.feedback_history])
            
            # 5a. Planning Refinement Loop (Internal)
            MAX_PLAN_REFINEMENTS = 2
            current_plan = None
            
            for plan_attempt in range(MAX_PLAN_REFINEMENTS):
                Logger.log(f"Planning Attempt {plan_attempt+1}...")
                state = planner_agent.run(state)
                if getattr(state, "pipeline_failure_reason", None): return state
                
                # Robust extraction of plan for PromptLoader
                if isinstance(state.strategies, dict):
                    plan_data = state.strategies.get("strategies", state.strategies) if isinstance(state.strategies.get("strategies"), dict) else state.strategies
                    state.step_by_step_plan = plan_data.get("primary", [])
                
                current_plan = state.join_plan
                
                # Audit the plan
                Logger.log_step("QueryCritic", "START")
                critic_res = critic_agent.run(state)
                if getattr(state, "pipeline_failure_reason", None): return state
                audit = critic_res.last_agent_output # Critic returns raw JSON
                
                if isinstance(audit, dict) and audit.get("is_valid"):
                    Logger.log("Plan validated successfully by QueryCritic.")
                    break
                else:
                    feedback = audit.get("feedback", "Plan invalid.") if isinstance(audit, dict) else "Plan invalid."
                    Logger.log(f"QueryCritic Rejected Plan: {feedback}", level="WARN")
                    state.feedback_history.append(f"PLAN_FAILURE: {feedback}")
                    state.previous_action_plan = str(current_plan)

            # 5b. SQL Generation
            Logger.log_step("SQLGenerator", "START")
            
            # Use higher sample count for SQL Generator to help grounding
            full_schema_str = format_schema_to_str(state.schema_info, mode="compressed", max_samples=3)
            
            # Populate variables for PromptLoader fallback or legacy prompts
            if isinstance(state.strategies, dict):
                mapping = state.strategies.get("concept_mapping", [])
                strat_tables = []
                # Normalize schema tables for matching
                norm_schema = {t.split('.')[-1].replace('"', '').upper(): t for t in state.schema_info.keys()}
                
                for m in mapping:
                    mapped_to = m.get("mapped_to", "")
                    if mapped_to:
                        # mapped_to could be TABLE.COL or DATABASE.SCHEMA.TABLE.COL
                        parts = mapped_to.split(".")
                        # Try to match the last-but-one part (Table name) or any part
                        found = False
                        for p in parts:
                            p_clean = p.replace('"', '').upper()
                            if p_clean in norm_schema:
                                fqn = norm_schema[p_clean]
                                if fqn not in strat_tables: strat_tables.append(fqn)
                                found = True
                                break
                        if not found and parts:
                            # Fallback to first part if no match found
                            t = parts[0].replace('"', '').upper()
                            if t in norm_schema:
                                fqn = norm_schema[t]
                                if fqn not in strat_tables: strat_tables.append(fqn)
                
                if not strat_tables:
                    # Fallback to all tables in schema if mapping is empty/unresolved
                    strat_tables = list(state.schema_info.keys())

                state.grounded_schema = format_schema_to_str({t: state.schema_info.get(t, {}) for t in strat_tables}, mode="compressed", max_samples=5)
                
                primary_strat = state.strategies.get("strategies", {}).get("primary", [])
                if not primary_strat and isinstance(state.strategies.get("primary"), list):
                    primary_strat = state.strategies.get("primary")
                state.join_plan = "\n".join([str(s) for s in primary_strat])

            state = generator_agent.run(state)
            if getattr(state, "pipeline_failure_reason", None): return state
            sql = state._temp_sql
            
            # 5c. Guardrails
            try:
                sql = guardrails.apply(sql)
                state.chosen_query = sql
            except ValueError as e:
                Logger.log(f"Guardrail violation: {str(e)}", level="ERROR")
                state.feedback_history.append(f"GUARDRAIL_VIOLATION: {str(e)}")
                continue
            
            # 5d. Execution
            Logger.log_step("ExecutionEngine", "START")
            # Use ToolRegistry to ensure results are saved to CSV and SQL is saved to file
            tool_res = ToolRegistry.execute_sql(state, params={"sql": sql})
            result = state.execution_result
            
            state.audit_context = {
                "sql": sql,
                "execution": {
                    "status": "error" if result.error_message else "success",
                    "error_message": result.error_message,
                    "row_count": result.row_count
                }
            }
            
            # 5e. Validation
            valid = validator.check(result)
            
            if valid:
                Logger.log("Pipeline Success!")
                sql_approved = True
                memory.update(state.user_query, []) # Simple memory update
                break
            
            # 5f. SQL Criticism (Learning from Execution)
            Logger.log_step("SQLCritic", "START")
            critic_res = sql_critic_agent.run(state)
            if getattr(state, "pipeline_failure_reason", None): return state
            sql_audit = critic_res.last_agent_output
            
            feedback = sql_audit.get("feedback", "Unknown execution error.") if isinstance(sql_audit, dict) else "Execution failed."
            Logger.log(f"SQLCritic Feedback: {feedback}", level="WARN")
            state.feedback_history.append(f"EXECUTION_FAILURE: {feedback}")
            state.previous_sql = sql
            
            Logger.log(f"Attempt {exec_attempt+1} failed. Learning from feedback...", level="WARN")

        if not sql_approved:
            state.pipeline_failure_reason = "Failed to produce a valid query after max execution attempts."
            
        return state


    def _infer_reference_date(self, state: AgentState):
        """
        Infers the reference date based on the latest timestamp in the dataset.
        """
        from core.tool_registry import ToolRegistry
        from core.logger import Logger
        
        # 1. Identify potential timestamp columns
        date_candidates = []
        time_candidates = []
        
        for table, info in (state.all_schema_info.items() if hasattr(state, 'all_schema_info') else state.full_schema_info.items()):
            for col in info.get("columns", []):
                name = col.get("column_name", "").lower()
                c_type = col.get("type", "").upper()
                
                # Prioritize DATE or TIMESTAMP types
                if any(k in c_type for k in ["DATE", "STAMP"]):
                    date_candidates.append((table, col.get("column_name")))
                elif any(k in name for k in ["date", "stamp"]):
                    date_candidates.append((table, col.get("column_name")))
                elif "time" in name or "time" in c_type:
                    time_candidates.append((table, col.get("column_name")))
        
        candidates = date_candidates + time_candidates
        
        if not candidates:
            state.reference_date = "2017-01-01" # Default fallback
            return

        # 2. Try to fetch MAX value from candidates
        service = ToolRegistry._get_service(state)
        latest_date = None
        
        # Try top candidates
        for table, col in candidates[:10]:
            try:
                # Sanitize table/col names
                q_table = f'"{table}"' if "." not in table else table
                q_col = f'"{col}"'
                query = f"SELECT MAX({q_col}) FROM {q_table}"
                res = service.execute_query(query)
                if not res.error_message and res.rows and res.rows[0][0]:
                    val = str(res.rows[0][0])
                    # VALIDATION: Must contain a date separator and look like a date
                    if "-" in val or "/" in val:
                        if len(val) >= 8:
                            if not latest_date or val > latest_date:
                                latest_date = val
            except:
                continue
        
        if latest_date:
            # Clean up if it's a full timestamp
            if " " in latest_date: latest_date = latest_date.split(" ")[0]
            if "T" in latest_date: latest_date = latest_date.split("T")[0]
            # Further validation: ensure it's not just a time
            if "-" not in latest_date and "/" not in latest_date:
                latest_date = "2017-01-01"
            state.reference_date = latest_date
        else:
            state.reference_date = "2017-01-01"

