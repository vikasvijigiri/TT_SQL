from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any, Union

# ---------------------------------------------------------
# Semantic Context Models (Offline Engine)
# ---------------------------------------------------------

class SemanticColumn(BaseModel):
    name: str = Field(description="The actual physical column name in the database.")
    type: str = Field(description="Data type of the column.")
    description: Optional[str] = Field(None, description="Semantic description of the column.")
    sample_values: List[str] = Field(default_factory=list, description="Categorical sample values available.")
    nested_keys: List[str] = Field(default_factory=list, description="Internal keys found in JSON/VARIANT structures.")

class SemanticTable(BaseModel):
    name: str = Field(description="The fully qualified table name.")
    description: Optional[str] = Field(None, description="Semantic description of the table.")
    columns: List[SemanticColumn] = Field(default_factory=list, description="List of columns in this table.")
    foreign_keys: List[str] = Field(default_factory=list, description="Known foreign key relationships.")
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list, description="A few actual rows from the table.")

class SemanticContext(BaseModel):
    tables: List[SemanticTable] = Field(default_factory=list, description="The governed semantic layer definitions.")

# ---------------------------------------------------------
# Agent Output Models
# ---------------------------------------------------------

class ValueMapping(BaseModel):
    user_term: str = Field(description="The term the user used in their natural language question (e.g., 'lung cancer').")
    db_value: Optional[Any] = Field(None, description="The exact corresponding value from the semantic context sample values (e.g., 'luad'). May be empty if no exact match was found. Can be a string or list of strings.")
    column: str = Field(description="The column this value belongs to.")

class SchemaLinkerOutput(BaseModel):
    reasoning: Optional[str] = Field(None, description="Step-by-step reasoning for why these tables and columns are required.")
    selected_tables: List[str] = Field(description="List of required fully qualified table names.")
    selected_columns: List[str] = Field(description="List of required column names across all selected tables.")
    value_mappings: List[ValueMapping] = Field(default_factory=list, description="Explicit mappings from user terms to database values.")

class SQLGeneratorOutput(BaseModel):
    hierarchy_audit: Optional[str] = Field(None, description="Detailed audit of hierarchical string lengths and prefix selection for the requested grain.")
    thought_process: Union[str, List[str]] = Field(description="Detailed step-by-step logic on how the SQL is constructed using the mapped schema.")
    sql: str = Field(description="The final executable SQL query.")

class SelfCorrectorOutput(BaseModel):
    error_analysis: Union[str, List[str]] = Field(None, description="Analysis of why the previous SQL threw a database execution error.")
    thought_process: Union[str, List[str]] = Field(description="Step-by-step logic to resolve the error.")
    sql: str = Field(description="The corrected, final executable SQL query.")



