from typing import Any

from pydantic import BaseModel, Field


class ExecutionResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    row_count: int = 0
    error_message: str | None = None
    status: str | None = None  # SUCCESS or FAILED
    reason: str | None = None  # e.g. COLUMN_NOT_FOUND, TABLE_NOT_FOUND

    def rows_to_df(self):
        """Helper to convert results to a pandas DataFrame safely."""
        import pandas as pd

        if not self.rows:
            return pd.DataFrame(columns=self.columns)
        return pd.DataFrame(self.rows, columns=self.columns)


class CriticResponse(BaseModel):
    is_valid: bool
    feedback: str
    suggestion: str | None = None


class AgentState(BaseModel):
    """
    Shared state object passed between agents.
    """

    # Input
    user_query: str
    db_path: str
    db_name: str | None = None  # raw DB name
    instance_id: str = "default"  # Required for file-based tracking Header
    external_knowledge: str | None = None  # For BigQuery dataset resolution
    model_name: str = "default_model"  # Track which model is running this task
    dialect: str = "sqlite"  # Database dialect (sqlite, bigquery, snowflake, postgres)

    # Analysis
    schema_info: dict[str, Any] = Field(default_factory=dict)
    full_schema_info: dict[str, Any] = Field(default_factory=dict) # Master copy
    query_intent: str | None = None
    structured_intent: dict[str, Any] = Field(default_factory=dict)
    grounded_intent: dict[str, Any] = Field(default_factory=dict)
    complexity_score: str | None = None  # e.g., "LOW", "MEDIUM", "HIGH"
    relevant_tables: list[str] = Field(default_factory=list)
    structured_pruning: dict[str, Any] = Field(default_factory=dict)
    all_table_names: list[str] = Field(default_factory=list) # Task 2: Stage 1
    all_tables: str | None = None # Formatted string for TablePruner
    selected_tables: list[str] = Field(default_factory=list) # Task 2: Stage 2
    selected_columns: dict[str, list[str]] = Field(default_factory=dict) # Task 2: Stage 4
    all_columns_fetched: bool = False # Flag for Stage 3
    schema_retrieval_stage: int = 0
    context_reasoning: str = ""  # Reasoning for table selection

    intent_approach: str = ""

    # Planning
    step_by_step_plan: list[str] = Field(default_factory=list)
    strategies: dict[str, Any] | None = None
    discovered_values: list[str] = Field(default_factory=list)

    # Generation
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
    combined_feedback: str = "" # Consolidated diagnostic string
    required_actions: list[str] = Field(default_factory=list) # Mandatory fixes to verify
    required_tables: list[str] = Field(default_factory=list) # Strategy-mandated tables
    semantic_failures: list[str] = Field(default_factory=list) # Audit track for logic errors
    previous_patterns: list[str] = Field(default_factory=list) # Blocked patterns
    learning_type: str = "unknown" # syntax_error, semantic_error, logic_error, etc.
    output_audit_report: dict[str, Any] | None = None
    audit_context: str = "" # Used for ensemble evaluation
    crit_response: dict[str, Any] = Field(default_factory=dict) # Newly mapped JSON output from SQLCritic
    plan_critique: dict[str, Any] = Field(default_factory=dict) # Newly mapped JSON output from QueryCritic
    plan_critique_history: list[dict[str, Any]] = Field(default_factory=list) # Task X: History for adaptive planning
    sql_candidates: list[dict[str, Any]] = Field(default_factory=list)
    last_raw_response: str = ""  # To debug parsing issues
    error_message: str | None = None
    
    # State Checkpointing & Soft-Tuning
    previous_run_sql: str | None = None  # Bootstrapped from disk
    refinement_improvement_count: int = 0

    # Execution
    sampling_enabled: bool = False
    execution_error_history: list[str] = Field(
        default_factory=list
    )  # Track all execution errors
    iteration_count: int = 0  # Global iteration counter for refinement loop
    feedback_history: list[str] = Field(
        default_factory=list
    )  # Track all critic feedback

    schema_status: str = "PENDING"  # PENDING, SUCCESS, FAILED
    fix_flags: dict[str, Any] = Field(default_factory=dict) # Dynamic hints for Builder (Task 7)
    stop_requested: bool = False

    # --- Hardening Fields (Tasks 2, 3, 8, 12) ---
    previous_errors: list[str] = Field(default_factory=list)  # Task 3: repeated error hard-stop detection
    concept_source_mismatch: bool = False                      # Task 2: concept maps to wrong table
    schema_insufficient: bool = False                          # Task 8: required concept not in schema
    pipeline_failure_reason: str | None = None                 # Task 12: structured hard-stop reason
    reference_date: str = "2017-01-01"                         # Global dataset reference date (Task 15)

    # --- Adaptive Recovery Fields (Tasks 1, 2, 4, 5, 7) ---
    failed_concepts: list[str] = Field(default_factory=list)          # Task 1: concepts that could not be mapped
    blocked_tables: list[str] = Field(default_factory=list)           # Task 4: tables banned after column failures
    concept_failure_counts: dict[str, int] = Field(default_factory=dict)  # Task 5: per-concept escalation counter
    strategy_source_type: str = "relational"                           # Task 7: current source type (relational|variant)
    variant_required: list[dict[str, Any]] = Field(default_factory=list) # Task X: Required variant keys
    variant_schema_hints: str = ""                                     # Formatted hints for prompt injection
    resolver_output: dict[str, Any] = Field(default_factory=dict)      # Cache for MissingElementsResolver
    resolved_elements: list[Any] = Field(default_factory=list)         # Output of MissingElementsResolver

    # Usage Tracking
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"input": 0, "output": 0}
    )
    last_call_metrics: dict[str, Any] = Field(
        default_factory=lambda: {"input": 0, "output": 0, "max": 0, "stop": "n/a"}
    )
    llm_call_count: int = 0
    seen_sqls: list[str] = Field(default_factory=list) # To prevent redundant generations
    dialect_constraints: list[str] = Field(default_factory=list) # Learned dialect rules

    # --- SQL Generation Fields ---
    grounded_schema: str = ""
    join_plan: str = ""
    _temp_sql: str = "" # Captured output from SQLGenerator agent
    SCHEMA: str = "" # Full schema for FastTrack mode
    
    # --- Iterative Learning Fields ---
    feedback_history: list[str] = []
    previous_action_plan: str = ""
    previous_sql: str = ""
    audit_context: dict = {}
    last_agent_output: dict | None = None

    def add_log(self, message: str):
        self.logs.append(message)

