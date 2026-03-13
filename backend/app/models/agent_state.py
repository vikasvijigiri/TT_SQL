from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CandidateQuery(BaseModel):
    sql: str
    approach: str = "standard"  # e.g., "CTE", "SUBQUERY", "TEMP_TABLE"
    explanation: Optional[str] = None
    score: float = 0.0

class ExecutionResult(BaseModel):
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    row_count: int = 0
    error_message: Optional[str] = None

    def rows_to_df(self):
        """Helper to convert results to a pandas DataFrame safely."""
        import pandas as pd
        if not self.rows:
            return pd.DataFrame(columns=self.columns)
        return pd.DataFrame(self.rows, columns=self.columns)

class GeneratorResponse(BaseModel):
    corrections: List[str] = Field(default_factory=list)
    sql: str
    sql_lines: List[str] = Field(default_factory=list)
    approach: str
    explanation: Optional[str] = None

class CriticResponse(BaseModel):
    is_valid: bool
    feedback: str
    suggestion: Optional[str] = None

class SubTaskResult(BaseModel):
    sub_question: str
    sub_sql: Optional[str] = None
    intermediate_rows: List[List[Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    critic_feedback: Optional[str] = None
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
    db_name: Optional[str] = None   # raw DB name; used as Qdrant collection override in RAG mode
    instance_id: str = "default"  # Required for file-based tracking Header
    model_name: str = "default_model" # Track which model is running this task
    sub_questions: List[str] = Field(default_factory=list) # Decomposed questions for multi-part queries
    
    # Analysis
    schema_info: Dict[str, Any] = Field(default_factory=dict)
    rag_columns: List[Dict[str, Any]] = Field(default_factory=list)  # raw RAG retrieved columns
    rag_multi_sets: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict) # Set A, B, C
    rag_pool: List[Dict[str, Any]] = Field(default_factory=list) # Union of all columns retrieved by RAG
    formatted_rag_pool: Optional[str] = None # Pre-formatted schema context for agents
    query_intent: Optional[str] = None
    complexity_score: Optional[str] = None  # e.g., "LOW", "MEDIUM", "HIGH"
    relevant_tables: List[str] = Field(default_factory=list)
    context_reasoning: str = "" # Reasoning for table selection
    
    
    # Intent Classification Details
    intent_entities: List[str] = Field(default_factory=list)
    intent_metrics: List[str] = Field(default_factory=list)
    intent_math_operations: List[str] = Field(default_factory=list)
    intent_quantities: List[str] = Field(default_factory=list)
    intent_approach: str = ""
    intent_dimensions: List[str] = Field(default_factory=list)
    intent_filters: List[str] = Field(default_factory=list)
    intent_time_constraints: List[str] = Field(default_factory=list)
    intent_joins: List[str] = Field(default_factory=list)
    intent_sorting: List[str] = Field(default_factory=list)
    intent_limits: Optional[str] = None
    intent_output_format: Optional[str] = None
    intent_output_precision: Optional[str] = None
    
    # Planning
    step_by_step_plan: List[str] = Field(default_factory=list)
    
    # Generation
    candidate_queries: List[CandidateQuery] = Field(default_factory=list)
    multi_set_candidates: List[Dict[str, Any]] = Field(default_factory=list) # Store SQL + Execution for Set A, B, C
    chosen_query: Optional[str] = None
    
    # Execution
    execution_result: Optional[ExecutionResult] = None
    
    # Metadata & History
    logs: List[str] = Field(default_factory=list)
    current_step: str = "INIT"
    history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Critic and Refinement
    is_result_valid: bool = False
    critic_feedback: str = ""
    last_raw_response: str = "" # To debug parsing issues
    error_message: Optional[str] = None
    business_summary: Optional[str] = None

    # Execution
    subtask_history: List[SubTaskResult] = Field(default_factory=list)
    current_subtask_index: int = 0
    sampling_enabled: bool = False
    rag_source: str = "qdrant" # Options: "none", "qdrant", "bedrock"
    use_rag: bool = False # If True, use RAG for table retrieval and bypass LLM
    rag_limit: int = 2 # Number of tables to retrieve from RAG
    execution_result: Optional[ExecutionResult] = None
    execution_error_history: List[str] = Field(default_factory=list)  # Track all execution errors
    
    # Interaction
    viz_recommendation: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None  # Chart type/axes from Orchestrator (bar, line, pie, none)
    stop_requested: bool = False

    # Usage Tracking
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})
    total_duration: float = 0.0

    def add_log(self, message: str):
        self.logs.append(message)
