# src/core/types.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class ColumnMeta:
    table: str
    name: str
    dtype: str
    sample_values: List[Any] = field(default_factory=list)
    is_array: bool = False
    is_variant: bool = False
    json_paths: List[Tuple[str, Any]] = field(default_factory=list)
    stats: Dict[str, float] = field(default_factory=dict)  # distinct_count, null_ratio

@dataclass
class TableMeta:
    name: str
    columns: Dict[str, ColumnMeta]

@dataclass
class Candidate:
    table: str
    column: str
    score: float

@dataclass
class Mapping:
    concept: str
    table: str
    column: str
    json_path: Optional[str] = None
    operator: str = "="
    value: Optional[Any] = None
    score: float = 0.0

@dataclass
class Plan:
    base_table: str
    joins: List[Tuple[str, str]]  # (from_table, to_table)
    filters: List[Mapping]
    projections: List[Tuple[str, str]]
    aggregations: List[str]

@dataclass
class QueryResult:
    rows: List[Dict[str, Any]]
    row_count: int

@dataclass
class Confidence:
    value: float
    reason: str = ""