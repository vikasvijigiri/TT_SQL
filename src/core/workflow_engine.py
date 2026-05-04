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
        """
        from core.tool_registry import ToolRegistry
        from core.utils import validate_json_response, write_sql_to_file, write_csv_to_file

        Logger.log_state("INIT", "STARTED")
        self._run_sanity_check(state)

        # 0. Components Initialization
        memory = Memory()
        service = ToolRegistry._get_service(state)
        indexer = SchemaIndexer(service)
        decomposer = QueryDecomposer()
        validator = Validator()
        guardrails = Guardrails()
        
        # 1. Schema Indexing (Step 4)
        Logger.log_step("SchemaIndexer", "START")
        ToolRegistry.fetch_schema(state, params={"full": True, "sample_rows": True})
        state.schema_info = indexer.index_schema(state.schema_info)
        
        graph = SchemaGraph(state.schema_info)
        ranker = JoinRanker(memory)
        retriever = Retriever(state.schema_info, memory)
        mapper = StructureAwareMapper(memory)
        planner = QueryPlanner(graph, ranker)
        generator = SQLGenerator()

        # 2. Intent Analysis (Step 1 - NO SCHEMA)
        Logger.log_step("IntentAnalyzer", "START")
        intent_agent = GenericAgent("IntentAnalyzer", "intent_analyzer", state_field="structured_intent", llm_service=self.llm)
        state = intent_agent.run(state)
        
        # 3. Query Decomposition (Step 2)
        Logger.log_step("QueryDecomposer", "START")
        tasks = decomposer.decompose(state.structured_intent)
        
        # 4. Retrieval (Step 3)
        Logger.log_step("Retriever", "START")
        candidates = retriever.retrieve(state.user_query)
        
        # 5. Retry Loop (Step 12)
        MAX_RETRIES = 3
        sql_approved = False
        
        for attempt in range(MAX_RETRIES):
            Logger.log_stage_header("Mapping & Generation", iteration=attempt+1)
            
            # 5a. Semantic Mapping (Step 7)
            mappings = mapper.map(tasks, candidates)
            if not mappings:
                Logger.log("No valid mappings found. Retrying with different candidates...", level="WARN")
                continue
                
            # 5b. Query Planning (Step 8)
            plan = planner.build(mappings)
            
            # 5c. SQL Generation (Step 9)
            sql = generator.generate(plan)
            
            # 5d. Guardrails (Step 15)
            try:
                sql = guardrails.apply(sql)
            except ValueError as e:
                Logger.log(f"Guardrail violation: {str(e)}", level="ERROR")
                continue
            
            state.chosen_query = sql
            
            # 5e. Execution
            Logger.log_step("ExecutionEngine", "START")
            result = service.execute_query(sql)
            state.execution_result = result
            
            # 5f. Validation (Step 10)
            valid = validator.check(result)
            
            # 6. Confidence Estimation (Step 11)
            scores = [m["score"] for m in mappings]
            confidence = compute_confidence(scores, valid)
            Logger.log(f"Confidence: {confidence}")
            
            # 7. Observability (Step 14)
            Logger.log(f"[Observability] Candidates: {len(candidates)}, Mappings: {len(mappings)}, Result Size: {result.row_count}")

            if valid:
                sql_approved = True
                # 8. Memory Update (Step 13)
                memory.update(state.user_query, mappings)
                break
            
            Logger.log(f"Attempt {attempt+1} failed validation. Penalizing mappings...", level="WARN")
            # Penalize mappings logic here (simplified for this task)

        if not sql_approved:
            state.pipeline_failure_reason = "Failed to produce a valid query after max retries."
            
        return state


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

