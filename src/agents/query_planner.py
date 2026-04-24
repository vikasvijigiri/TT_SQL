import os

from core.agent_base import AgentState, BaseAgent
from core.bq_service import BigQueryService
from core.file_coordinator import FileCoordinator
from core.llm_service import LLMService
from core.logger import Logger
from core.prompt_loader import PromptLoader
from core.sf_service import SnowflakeService
from core.sqlite_service import SQLiteService
from core.utils import format_rag_columns, format_schema_to_str
from rag.vector_store import VectorStoreAgent


class ContextEnrichmentAgent(BaseAgent):
    """Agent responsible for gathering database schema context.

    This agent enriches the current state with schema information by either
    performing column-level RAG retrieval or directly fetching the full schema
    from the target database (SQLite, BigQuery, or Snowflake).
    """

    def __init__(self, config: dict = None):
        """Initializes the ContextEnrichmentAgent.

        Args:
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="ContextEnrichment", config=config)
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        """Executes the context enrichment workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The updated state containing schema_info and metadata.
        """
        Logger.log_call(f"{self.name}.run", {"instance_id": state.instance_id})
        is_bigquery = state.dialect == "bigquery"
        is_snowflake = state.dialect == "snowflake"

        # 1. Try RAG if enabled
        if getattr(state, "use_rag", False):
            try:
                vector_store = VectorStoreAgent(collection_override=state.db_name)
                col_limit = getattr(state, "rag_limit", 2)
                retrieved_columns = vector_store.retrieve_relevant_columns(
                    state.user_query, limit=col_limit
                )

                if retrieved_columns:
                    rag_schema = {}
                    for col in retrieved_columns:
                        tname = col["table_name"]
                        if tname not in rag_schema:
                            rag_schema[tname] = {"columns": [], "foreign_keys": []}
                        rag_schema[tname]["columns"].append(
                            {
                                "column_name": col["column_name"],
                                "type": col["type"],
                                "description": col["description"],
                                "pk": col.get("pk", False),
                            }
                        )
                    state.schema_info = rag_schema
                    state.rag_columns = retrieved_columns
                    self.log(
                        state,
                        f"Column RAG: retrieved {len(retrieved_columns)} columns.",
                    )
                else:
                    self.log(
                        state,
                        "Column RAG: No relevant columns found. Falling back to full schema.",
                    )
            except Exception as e:
                self.log(
                    state,
                    f"RAG failed: {e}. Falling back to full schema.",
                    level="WARN",
                )
        else:
            self.log(state, "RAG is disabled. Fetching full schema.")

        # 2. SQLite Full Schema Logic (if applicable)
        if (
            not is_bigquery
            and not is_snowflake
            and (not state.schema_info or not getattr(state, "use_rag", False))
        ):
            if os.path.exists(state.db_path):
                try:
                    self.log(
                        state,
                        f"Fetching full schema from SQLite: {os.path.basename(state.db_path)}",
                    )
                    sqlite_svc = SQLiteService(state.db_path)
                    full_schema = sqlite_svc.get_full_schema()
                    if full_schema:
                        state.schema_info = full_schema
                        self.log(
                            state,
                            f"SQLite full schema fetched: {len(full_schema)} tables.",
                        )
                except Exception as e:
                    self.log(
                        state, f"Local schema extraction failed: {e}", level="ERROR"
                    )

        # 2. BigQuery Fallback
        if is_bigquery and (state.db_name or state.external_knowledge):
            try:
                bq_service = BigQueryService()
                datasets_to_try = []
                if state.db_name:
                    datasets_to_try.append(state.db_name)

                if state.external_knowledge and "." in state.external_knowledge:
                    potential_ds = state.external_knowledge.split(".")[0]
                    if potential_ds not in datasets_to_try:
                        datasets_to_try.append(potential_ds)

                final_datasets_to_try = []
                for ds in datasets_to_try:
                    final_datasets_to_try.append(ds)
                    if "." not in ds:
                        final_datasets_to_try.append(f"bigquery-public-data.{ds}")

                bq_schema = {}
                for ds in final_datasets_to_try:
                    self.log(state, f"BigQuery API fetch starting for: {ds}")
                    bq_schema = bq_service.get_dataset_schema(ds)
                    if bq_schema:
                        state.schema_info = bq_schema
                        self.log(
                            state,
                            f"BigQuery API: Fetched full schema for dataset '{ds}' ({len(bq_schema)} tables).",
                        )
                        break
            except Exception as e:
                self.log(state, f"BigQuery API fetch failed: {e}", level="WARN")

        # 3. Snowflake Fallback
        if is_snowflake and (state.db_name or state.external_knowledge):
            try:
                sf_service = SnowflakeService()
                db_val = state.db_name or os.getenv("SNOWFLAKE_DATABASE")
                
                database = db_val
                schema = None

                if db_val and "." in db_val:
                    parts = db_val.split(".")
                    database = parts[0]
                    schema = parts[1]
                elif db_val:
                    # Per user feedback: generally DB and Schema are same
                    database = db_val
                    schema = db_val # Default to same name
                
                # Log clearly the resolved DB.SCHEMA
                self.log(
                    state, f"Snowflake API fetch starting for: {database}.{schema or 'AUTO'}"
                )
                sf_schema = sf_service.get_schema(database, schema) if database else {}
                if sf_schema:
                    state.schema_info = sf_schema
                    self.log(
                        state,
                        f"Snowflake API: Fetched full schema ({len(sf_schema)} tables).",
                    )
            except Exception as e:
                self.log(state, f"Snowflake API fetch failed: {e}", level="WARN")

        if not state.schema_info:
            self.log(state, "WARNING: No schema info could be retrieved.", level="WARN")
        else:
            self.file_coordinator.write_schema(
                state.instance_id, state.schema_info, state.model_name
            )

        # Defaults
        if not state.query_intent: state.query_intent = "DATA_RETRIEVAL"
        if not state.complexity_score: state.complexity_score = "MEDIUM"
        state.full_schema_info = state.schema_info # Save master copy
        return state


class StepByStepPlannerAgent(BaseAgent):
    """Agent responsible for breaking down the user query into a logical roadmap.

    This agent uses an LLM to analyze the user query and available schema
    to generate a step-by-step approach plan, which guides the SQL generation process.
    """

    def __init__(self, llm_service: LLMService, config: dict = None):
        """Initializes the StepByStepPlannerAgent.

        Args:
            llm_service (LLMService): Service for interacting with LLM APIs.
            config (dict, optional): Configuration dictionary for the agent.
        """
        super().__init__(name="QueryPlanner", config=config)
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        """Executes the planning workflow.

        Args:
            state (AgentState): The current shared state of the pipeline.

        Returns:
            AgentState: The updated state containing the step_by_step_plan.
        """
        roadmap_label = "Execution Roadmap"
        self.log(state, f"PLAN_CATEGORY: {roadmap_label}")

        intent_context = (
            f"Intent: {state.query_intent}, Complexity: {state.complexity_score}"
        )

        # Pivot context: use full schema if we are re-planning after failures
        use_full = bool(state.execution_error_history)
        active_schema = state.full_schema_info if (use_full and state.full_schema_info) else state.schema_info

        if state.rag_columns:
            schema_str = format_rag_columns(state.rag_columns)
        elif active_schema:
            schema_str = format_schema_to_str(active_schema)
        else:
            schema_str = "No schema info available."

        self.log(state, f"PROMPT_VAR: intent_path={intent_context}")
        schema_summary = schema_str[:100] + "..." if len(schema_str) > 100 else schema_str
        self.log(state, f"PROMPT_VAR: schema={schema_summary}")

        # Synthesize CUMULATIVE FAILURE HISTORY for "Plan Pivoting"
        failure_history = "Initial Plan - No previous failures."
        if state.execution_error_history:
            history_lines = []
            for i, err in enumerate(state.execution_error_history):
                fback = state.feedback_history[i] if i < len(state.feedback_history) else "No feedback."
                history_lines.append(f"SQL ATTEMPT {i+1} FAILED.\nERROR: {err}\nCRITIC: {fback}")
            
            failure_history = (
                "### [RETROSPECTIVE: WHY PREVIOUS ATTEMPTS FAILED]\n"
                "Your previous plan led to these errors. Analyze them carefully:\n"
                + "\n\n".join(history_lines) + "\n\n"
                "### [PIVOT INSTRUCTION]\n"
                "If the errors were SYNTAX-related (e.g., column not found), reconsider your schema interpretation.\n"
                "If the errors were LOGIC-related (e.g., 0 rows), reconsider your JOIN keys or filters.\n"
                "Do NOT repeat the same logical strategy if it failed twice. Propose a more robust alternative."
            )

        messages = self.prompt_loader.load_prompt(
            "query_planner",
            user_query=state.user_query,
            schema=schema_str,
            intent_path=intent_context,
            agent_role=self.role,
            agent_task=self.task,
            failure_history=failure_history,
        )

        response = self.llm.get_json_completion(
            messages, state=state, agent_name=self.name
        )
        if response and "step_by_step_approach" in response:
            state.step_by_step_plan = response["step_by_step_approach"]
            self.file_coordinator.write_plan(
                state.instance_id, state.step_by_step_plan, state.model_name
            )
        else:
            state.step_by_step_plan = ["Analyze Schema", "Generate SQL"]

        self.log(
            state,
            f"Generated execution plan with {len(state.step_by_step_plan)} sub-tasks.",
        )
        return state
