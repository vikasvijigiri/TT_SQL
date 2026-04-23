from typing import Any

from pydantic import BaseModel, Field


class CandidateQuery(BaseModel):
    sql: str
    approach: str = "standard"  # e.g., "CTE", "SUBQUERY", "TEMP_TABLE"
    explanation: str | None = None
    score: float = 0.0


class ExecutionResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    row_count: int = 0
    error_message: str | None = None

    def rows_to_df(self):
        """Helper to convert results to a pandas DataFrame safely."""
        import pandas as pd

        if not self.rows:
            return pd.DataFrame(columns=self.columns)
        return pd.DataFrame(self.rows, columns=self.columns)


class GeneratorResponse(BaseModel):
    corrections: list[str] = Field(default_factory=list)
    sql: str
    sql_lines: list[str] = Field(default_factory=list)
    approach: str
    explanation: str | None = None


class CriticResponse(BaseModel):
    is_valid: bool
    feedback: str
    suggestion: str | None = None


class SubTaskResult(BaseModel):
    sub_question: str
    sub_sql: str | None = None
    intermediate_rows: list[list[Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    critic_feedback: str | None = None
    iteration_count: int = 0
    is_valid: bool = False

    def rows_to_df(self):
        """Helper to convert results to a pandas DataFrame safely."""
        import pandas as pd

        if not self.intermediate_rows:
            return pd.DataFrame(columns=self.columns)
        return pd.DataFrame(self.intermediate_rows, columns=self.columns)


class AgentState(BaseModel):
    """
    Shared state object passed between agents.
    """

    # Input
    user_query: str
    db_path: str
    db_name: str | None = (
        None  # raw DB name; used as Qdrant collection override in RAG mode
    )
    instance_id: str = "default"  # Required for file-based tracking Header
    external_knowledge: str | None = None  # For BigQuery dataset resolution
    model_name: str = "default_model"  # Track which model is running this task
    dialect: str = "sqlite"  # Database dialect (sqlite, bigquery, snowflake, postgres)
    sub_questions: list[str] = Field(
        default_factory=list
    )  # Decomposed questions for multi-part queries

    # Analysis
    schema_info: dict[str, Any] = Field(default_factory=dict)
    rag_columns: list[dict[str, Any]] = Field(
        default_factory=list
    )  # raw RAG retrieved columns
    query_intent: str | None = None
    complexity_score: str | None = None  # e.g., "LOW", "MEDIUM", "HIGH"
    relevant_tables: list[str] = Field(default_factory=list)
    context_reasoning: str = ""  # Reasoning for table selection

    # Intent Classification Details
    intent_entities: list[str] = Field(default_factory=list)
    intent_metrics: list[str] = Field(default_factory=list)
    intent_math_operations: list[str] = Field(default_factory=list)
    intent_quantities: list[str] = Field(default_factory=list)
    intent_approach: str = ""
    intent_dimensions: list[str] = Field(default_factory=list)
    intent_filters: list[str] = Field(default_factory=list)
    intent_time_constraints: list[str] = Field(default_factory=list)
    intent_joins: list[str] = Field(default_factory=list)
    intent_sorting: list[str] = Field(default_factory=list)
    intent_limits: str | None = None
    intent_output_format: str | None = None
    intent_output_precision: str | None = None

    # Planning
    step_by_step_plan: list[str] = Field(default_factory=list)

    # Generation
    candidate_queries: list[CandidateQuery] = Field(default_factory=list)
    chosen_query: str | None = None

    # Execution
    execution_result: ExecutionResult | None = None

    # Metadata & History
    logs: list[str] = Field(default_factory=list)
    current_step: str = "INIT"
    history: list[dict[str, Any]] = Field(default_factory=list)

    # Critic and Refinement
    is_result_valid: bool = False
    critic_feedback: str = ""
    last_raw_response: str = ""  # To debug parsing issues
    error_message: str | None = None

    # Execution
    subtask_history: list[SubTaskResult] = Field(default_factory=list)
    current_subtask_index: int = 0
    sampling_enabled: bool = False
    rag_source: str = "qdrant"  # Options: "none", "qdrant", "bedrock"
    use_rag: bool = False  # If True, use RAG for table retrieval and bypass LLM
    rag_limit: int = 2  # Number of tables to retrieve from RAG
    execution_result: ExecutionResult | None = None
    execution_error_history: list[str] = Field(
        default_factory=list
    )  # Track all execution errors

    # Interaction
    viz_recommendation: dict[str, Any] | None = None
    stop_requested: bool = False

    # Usage Tracking
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"input": 0, "output": 0}
    )

    def add_log(self, message: str):
        self.logs.append(message)
