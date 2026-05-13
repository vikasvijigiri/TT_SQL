from typing import List, Optional, Literal, Union, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# -------------------------
# Basic Enums / Literals
# -------------------------

IntentType = Literal[
    "filter_retrieval", "aggregation", "analytical",
    "comparison", "ranking", "join_query", "unknown"
]

Complexity = Literal["low", "medium", "high"]

Operator = Literal["=", "!=", ">", "<", ">=", "<=", "IN", "LIKE", "BETWEEN", "IS NULL", "IS NOT NULL"]

MatchMode = Literal["exact", "fuzzy", "semantic"]

ValueType = Literal["categorical", "text", "numeric", "date"]

OrderDirection = Literal["asc", "desc"]

RankingType = Literal["top", "bottom"]

NullStrategy = Literal["include", "exclude", "only"]

OutputFormat = Literal["table", "chart", "summary"]

# -------------------------
# Support Models
# -------------------------

class CandidateColumn(BaseModel):
    table: str
    column: str
    dtype: str
    sample_values: List[str] = []
    description: str = ""
    is_array: bool = False
    json_paths: List[str] = []
    stats: Dict[str, float] = {}
    score: float = 0.0
    evidence: List[str] = []

    @property
    def fqn(self) -> str:
        return f"{self.table}.{self.column}"

class JoinCondition(BaseModel):
    left_table: Optional[str] = None
    right_table: Optional[str] = None
    on: List[str] = Field(default_factory=list)
    type: Literal["inner", "left", "right"] = "inner"
    confidence: float = Field(ge=0.0, le=1.0)

class MappingCandidate(BaseModel):
    column: str
    confidence: float = Field(ge=0.0, le=1.0)

class Condition(BaseModel):
    type: Literal["condition"] = "condition"
    raw_field: str # Changed from 'field' to 'raw_field'
    operator: Operator
    value: Optional[Union[str, int, float, List[str]]] = None

    value_type: Optional[ValueType] = None
    match_mode: Optional[MatchMode] = "exact"
    case_sensitive: bool = False

    candidates: List[MappingCandidate] = Field(default_factory=list) # Added candidates list

    @property
    def field(self) -> str: # Keep 'field' property for backward compatibility
        return self.raw_field

    @model_validator(mode="after")
    def validate_operator_value(self):
        if self.operator == "IN":
            if self.value is not None and not isinstance(self.value, list):
                raise ValueError("IN operator requires a list value")
        return self

Filter = Condition

class ConditionGroup(BaseModel):
    type: Literal["group"] = "group"
    operator: Literal["AND", "OR"]
    conditions: List[Union["ConditionGroup", Condition]] = Field(default_factory=list)

ConditionGroup.model_rebuild()

class SemanticTerm(BaseModel):
    text: str
    type: Literal["entity", "attribute", "value", "condition"]

class Aggregation(BaseModel):
    function: str
    column: Optional[str] = None
    alias: Optional[str] = None

class HavingCondition(BaseModel):
    field: str
    operator: Operator
    value: Union[str, int, float]

class OrderBy(BaseModel):
    columns: List[str] = Field(default_factory=list)
    direction: Optional[OrderDirection] = None

class Ranking(BaseModel):
    type: Optional[RankingType] = None
    k: Optional[int] = None
    based_on: Optional[str] = None

class Distinct(BaseModel):
    enabled: bool = False
    columns: List[str] = Field(default_factory=list)

class TimeContext(BaseModel):
    column: Optional[str] = None
    range: Optional[str] = None
    granularity: Optional[Literal["day", "week", "month", "year"]] = None

class Calculation(BaseModel):
    expression: Optional[str] = None
    alias: Optional[str] = None
    type: Literal["arithmetic", "ratio", "case", "window"]

class OutputRequirements(BaseModel):
    format: OutputFormat = "table"
    clean_data: bool = False
    deduplicate: bool = False
    include_nulls: bool = True

class NullHandling(BaseModel):
    strategy: NullStrategy = "include"
    columns: List[str] = Field(default_factory=list)

class SemanticRequirements(BaseModel):
    must_include: List[str] = Field(default_factory=list)
    must_exclude: List[str] = Field(default_factory=list)
    business_logic: List[str] = Field(default_factory=list)

class SchemaMappingItem(BaseModel):
    input: Optional[str] = None
    column: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

class SchemaMapping(BaseModel):
    mapped_fields: List[SchemaMappingItem] = Field(default_factory=list)
    unresolved_fields: List[str] = Field(default_factory=list)

class ExecutionHints(BaseModel):
    prefer_index: List[str] = Field(default_factory=list)
    avoid_full_scan: bool = False

class Ambiguity(BaseModel):
    present: bool = False
    fields: List[str] = Field(default_factory=list)
    clarification_needed: bool = False

class Source(BaseModel):
    primary_table: Optional[str] = None
    candidate_tables: List[str] = Field(default_factory=list)
    requires_join: bool = False
    joins: List[JoinCondition] = Field(default_factory=list)
    join_hints: List[str] = Field(default_factory=list)

class Select(BaseModel):
    columns: List[str] = Field(default_factory=list)
    derived_columns: List[str] = Field(default_factory=list)
    include_all: bool = False

# -------------------------
# MAIN INTENT MODEL
# -------------------------

class Intent(BaseModel):
    query: str
    intent_type: IntentType
    complexity: Complexity
    
    terms: List[SemanticTerm] = Field(default_factory=list) # Added terms

    source: Source = Field(default_factory=Source)
    select: Select = Field(default_factory=Select)

    entities: List[str] = Field(default_factory=list) 
    filters: Optional[ConditionGroup] = None

    aggregations: List[Aggregation] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    having: List[HavingCondition] = Field(default_factory=list)

    order_by: Optional[OrderBy] = None
    ranking: Optional[Ranking] = None
    limit: Optional[int] = None

    distinct: Distinct = Field(default_factory=Distinct)
    time_context: TimeContext = Field(default_factory=TimeContext)

    calculations: List[Calculation] = Field(default_factory=list)

    output_requirements: OutputRequirements = Field(default_factory=OutputRequirements)
    null_handling: NullHandling = Field(default_factory=NullHandling)

    semantic_requirements: SemanticRequirements = Field(default_factory=SemanticRequirements)
    schema_mapping: SchemaMapping = Field(default_factory=SchemaMapping)

    sub_queries: List[dict] = Field(default_factory=list)

    execution_hints: ExecutionHints = Field(default_factory=ExecutionHints)

    ambiguity: Ambiguity = Field(default_factory=Ambiguity)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):
        if v is not None and v <= 0:
            raise ValueError("limit must be > 0")
        return v

    def flatten_filters(self) -> List[Condition]:
        conditions = []
        if not self.filters:
            return []
        
        def _walk(group: Union[ConditionGroup, Condition]):
            if isinstance(group, Condition):
                conditions.append(group)
            elif isinstance(group, ConditionGroup):
                for cond in group.conditions:
                    _walk(cond)
            elif isinstance(group, dict):
                if group.get("type") == "condition":
                    conditions.append(Condition(**group))
                else:
                    for cond in group.get("conditions", []):
                        _walk(cond)
        
        _walk(self.filters)
        return conditions

# -------------------------
# Other Pipeline Models
# -------------------------

class ColumnMapping(BaseModel):
    source_type: str 
    source_name: str 
    column: CandidateColumn
    confidence: float
    value_override: Optional[Any] = None

class SQLPlan(BaseModel):
    base_table: str
    joins: List[Dict[str, Any]] = []
    filters: List[str] = []
    projections: List[str] = []
    group_by: List[str] = []
    order_by: Optional[str] = None
    limit: Optional[int] = None

class ExecutionResult(BaseModel):
    query: str
    sql: str = ""
    rows: List[Dict[str, Any]] = []
    row_count: int = 0
    error: Optional[str] = None
    status: str = "success"
    confidence: float = 0.0
    latency_ms: float = 0.0
    
    intent: Optional[Intent] = None
    mappings: List[ColumnMapping] = []
    plan: Optional[SQLPlan] = None
    steps: List[str] = []
    
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"input": 0, "output": 0})
    llm_call_count: int = 0
    agent_metrics: Dict[str, Any] = Field(default_factory=dict)
# -------------------------
# Agent Output Models (for Validation)
# -------------------------

class PlanStep(BaseModel):
    step_id: str = Field(alias="id")
    operation: str = Field(alias="op")
    description: Optional[str] = Field(None, alias="desc")
    inputs: Union[List[str], str] = Field(default_factory=list)
    output: str = Field(alias="out")
    grounding: Optional[Dict[str, Any]] = Field(None, alias="gnd")
    depends_on: List[str] = Field(default_factory=list, alias="dep")
    dialect_note: Optional[str] = Field(None, alias="note")

    class Config:
        populate_by_name = True

class Risk(BaseModel):
    risk_type: str
    mitigation: str

class FullPlan(BaseModel):
    action_plan: List[str] = Field(alias="action_plan")
    confidence: float = 0.5
    repair_summary: Optional[str] = None
    reasoning: Optional[str] = None
    
    @model_validator(mode="before")
    @classmethod
    def handle_legacy_or_user_format(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If the model produced 'steps' instead of 'action_plan', we map it
            if "steps" in data and "action_plan" not in data:
                data["action_plan"] = [f"{s.get('op', 'STEP')}: {s.get('desc', '')}" for s in data["steps"]]
        return data

    class Config:
        populate_by_name = True

class CriticResult(BaseModel):
    is_valid: bool
    logical_fit: str
    feedback: str
    missing_logical_steps: List[str] = []
    grounding_errors: List[str] = []
    suggested_fix: Optional[str] = None

class SQLCandidate(BaseModel):
    id: int
    reasoning: str
    sql: str

class SQLBuilderOutput(BaseModel):
    sql: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: Optional[float] = 0.0
    candidates: Optional[List[SQLCandidate]] = None
    
    @model_validator(mode="after")
    def validate_sql_present(self):
        if not self.sql and (not self.candidates or len(self.candidates) == 0):
            raise ValueError("SQL must be present either in 'sql' or 'candidates'")
        if not self.sql and self.candidates:
            self.sql = self.candidates[0].sql
        return self

# -------------------------
# Pruning Stage Models
# -------------------------

class TablePruningResult(BaseModel):
    relevant_tables: List[str]
    reasoning: str

class ColumnPruningResult(BaseModel):
    table_columns: Dict[str, List[str]] # table_name -> [col1, col2]
    reasoning: str

class ValuePruningResult(BaseModel):
    values: List[Dict[str, Any]] = [] # [{"table": "T", "column": "C", "value": "V"}]
    variant_keys: List[Dict[str, Any]] = [] # [{"table": "T", "column": "C", "key": "K"}]
    reasoning: str
