from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional, Dict, Any, Union

# ---------------------------------------------------------
# Semantic Context Models (Offline Engine)
# ---------------------------------------------------------


class SemanticColumn(BaseModel):
    name: str = Field(description="The actual physical column name in the database.")
    type: str = Field(description="Data type of the column.")
    description: Optional[str] = Field(
        None, description="Semantic description of the column."
    )
    sample_values: List[str] = Field(
        default_factory=list, description="Categorical sample values available."
    )
    nested_keys: List[str] = Field(
        default_factory=list,
        description="Internal keys found in JSON/VARIANT structures.",
    )


class SemanticTable(BaseModel):
    name: str = Field(description="The fully qualified table name.")
    description: Optional[str] = Field(
        None, description="Semantic description of the table."
    )
    columns: List[SemanticColumn] = Field(
        default_factory=list, description="List of columns in this table."
    )
    foreign_keys: List[str] = Field(
        default_factory=list, description="Known foreign key relationships."
    )
    sample_rows: List[Dict[str, Any]] = Field(
        default_factory=list, description="A few actual rows from the table."
    )


class SemanticContext(BaseModel):
    tables: List[SemanticTable] = Field(
        default_factory=list, description="The governed semantic layer definitions."
    )


# ---------------------------------------------------------
# Agent Output Models
# ---------------------------------------------------------


class ValueMapping(BaseModel):
    user_term: str = Field(
        description="The term the user used in their natural language question (e.g., 'lung cancer')."
    )
    db_value: Optional[Any] = Field(
        None,
        description="The exact corresponding value from the semantic context sample values (e.g., 'luad'). May be empty if no exact match was found. Can be a string or list of strings.",
    )
    column: Optional[str] = Field(
        None, 
        description="The column this value belongs to. Can be null if the mapping is unresolved."
    )
    match_type: Optional[str] = Field(
        None,
        description="Type of match: exact, fuzzy, or dynamic_lookup."
    )


class SchemaDiscoveryOutput(BaseModel):
    discovered_domains: List[str] = Field(description="High-level business domains found relevant to the query.")
    relevant_tables: List[str] = Field(description="The subset of fully qualified tables that belong to these domains.")
    known_relationships: List[str] = Field(description="Foreign key paths connecting the relevant tables.")
    reasoning: str = Field(description="Why these domains and tables were selected.")

class SchemaLinkerOutput(BaseModel):
    reasoning: Optional[str] = Field(
        None,
        description="Step-by-step reasoning for why these tables and columns are required.",
    )
    selected_tables: List[str] = Field(
        description="List of required fully qualified table names."
    )
    selected_columns: List[str] = Field(
        description="List of required column names across all selected tables."
    )
    value_mappings: List[ValueMapping] = Field(
        default_factory=list,
        description="Explicit mappings from user terms to database values.",
    )
    coverage_score: float = Field(
        default=1.0,
        description="Confidence score from 0.0 to 1.0 indicating if all required business/text/metric columns were found.",
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of facts/entities/metrics requested but missing from the schema.",
    )


class SQLGeneratorOutput(BaseModel):
    hierarchy_audit: Optional[str] = Field(
        None,
        description="Detailed audit of hierarchical string lengths and prefix selection for the requested grain.",
    )
    sql_vs_retrieval_decision: str = Field(
        default="SQL_ONLY",
        description="Decision on execution strategy: 'SQL_ONLY', 'RETRIEVAL_ONLY', or 'HYBRID'."
    )
    thought_process: Union[str, List[str]] = Field(
        default="",
        validation_alias=AliasChoices(
            "thought_process", "reasoning", "analysis", "thought"
        ),
        description="ReAct-style reasoning trace: Thought -> Action -> Observation cycles before producing SQL.",
    )
    probe_sql: Optional[str] = Field(
        None,
        description=(
            "ReAct probe: a targeted SQL to execute BEFORE finalising the main SQL. "
            "Use to verify a value exists, check a data format, or confirm join cardinality. "
            "If probe is set, leave `sql` as an empty string - the framework will run the probe, "
            "feed you the result, and call you again with the observation."
        ),
    )
    sql: str = Field(description="The final executable SQL query. Empty string if probe_sql is set.")


class SelfCorrectorOutput(BaseModel):
    error_analysis: Optional[Union[str, List[str]]] = Field(
        None,
        validation_alias=AliasChoices("error_analysis", "analysis"),
        description="Analysis of why the previous SQL threw a database execution error.",
    )
    thought_process: Union[str, List[str]] = Field(
        default="",
        validation_alias=AliasChoices(
            "thought_process", "reasoning", "analysis", "thought"
        ),
        description="Step-by-step logic to resolve the error.",
    )
    probe_sql: Optional[str] = Field(
        None,
        description="Optional SQL query to execute against the database to gather diagnostic evidence (e.g. check table rows, verify columns, query sample values).",
    )
    sql: str = Field(description="The corrected, final executable SQL query.")


class CriticOutput(BaseModel):
    is_valid: bool = Field(
        description="True if the proposed SQL query is logically and syntactically correct based on the query instructions, False otherwise."
    )
    criticism: Optional[str] = Field(
        None,
        description="Detailed criticism of the proposed SQL, highlighting exact errors, ambiguities, type cast issues, or semantic deviations.",
    )
    proposed_fix: Optional[str] = Field(
        None,
        description="A clear, abstract recipe or pseudo-SQL explaining exactly how to fix the identified issue.",
    )


# ---------------------------------------------------------
# V4 Validation Contracts
# ---------------------------------------------------------

class QuestionValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if the question analysis is logically sound")
    rejection_reason: Optional[str] = Field(None)

class PlanValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if the semantic plan covers required facts and strategy")
    rejection_reason: Optional[str] = Field(None)

class SchemaValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if the schema provides all required business/text columns")
    rejection_reason: Optional[str] = Field(None)
    coverage_score: float = Field(description="Score from 0.0 to 1.0")

class JoinValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if all joins are safe (no cartesian products) and paths exist")
    rejection_reason: Optional[str] = Field(None)

class SQLValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if SQL passes syntax and semantic business checks")
    rejection_reason: Optional[str] = Field(None)

class ExecutionValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if the execution plan is safe (no massive full table scans)")
    rejection_reason: Optional[str] = Field(None)
    estimated_cost: float = Field(description="Estimated execution cost")

class ResultValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if results don't contain impossible values or explosion artifacts")
    rejection_reason: Optional[str] = Field(None)

class EvidenceValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if synthesized evidence is logically sound and consistent")
    rejection_reason: Optional[str] = Field(None)

class AnswerabilityValidatorOutput(BaseModel):
    is_valid: bool = Field(description="True if we have enough evidence to answer without hallucinating")
    rejection_reason: Optional[str] = Field(None)

