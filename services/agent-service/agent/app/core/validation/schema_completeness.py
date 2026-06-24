"""
Schema/metadata/relationship completeness checker.

Validates every schema JSON file in a database directory to ensure:
  - Required top-level keys are present
  - column_names and column_types lists exist and have the same length
  - FK references (if present) point to tables that also have schema files
  - No column is typed as None or empty string

Returns a CompletenessReport describing coverage and any gaps found.
Used at startup (health check) and by /api/analytics/schema-completeness.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_REQUIRED_KEYS: tuple[str, ...] = ("table_name", "column_names", "column_types")


@dataclass
class TableCompletenessResult:
    table: str
    file_path: str
    missing_keys: List[str] = field(default_factory=list)
    column_count_mismatch: bool = False
    empty_column_names: List[str] = field(default_factory=list)
    broken_fk_references: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return (
            not self.missing_keys
            and not self.column_count_mismatch
            and not self.empty_column_names
            and not self.broken_fk_references
        )


@dataclass
class CompletenessReport:
    db_name: str
    schema_dir: str
    total_tables: int
    valid_tables: int
    invalid_tables: int
    coverage_score: float
    table_results: List[TableCompletenessResult] = field(default_factory=list)
    missing_schema_files: List[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.coverage_score >= 1.0 and not self.missing_schema_files

    def as_dict(self) -> Dict:
        return {
            "db_name": self.db_name,
            "schema_dir": self.schema_dir,
            "total_tables": self.total_tables,
            "valid_tables": self.valid_tables,
            "invalid_tables": self.invalid_tables,
            "coverage_score": round(self.coverage_score, 4),
            "is_complete": self.is_complete,
            "missing_schema_files": self.missing_schema_files,
            "invalid_table_details": [
                {
                    "table": r.table,
                    "missing_keys": r.missing_keys,
                    "column_count_mismatch": r.column_count_mismatch,
                    "empty_column_names": r.empty_column_names,
                    "broken_fk_references": r.broken_fk_references,
                }
                for r in self.table_results
                if not r.is_valid
            ],
        }


def check_schema_completeness(schema_dir: str | Path) -> CompletenessReport:
    """
    Validate all schema JSON files in *schema_dir*.

    Parameters
    ----------
    schema_dir:
        Path to a database-specific schema directory, e.g.
        ``resources/databases/sqlite/IPL/``.

    Returns
    -------
    CompletenessReport
        Never raises; failures are captured inside the report.
    """
    schema_dir = Path(schema_dir)
    db_name = schema_dir.name

    json_files = sorted(schema_dir.glob("*.json"))
    known_tables: set[str] = set()
    results: List[TableCompletenessResult] = []

    # First pass: collect all table names from filenames
    for jf in json_files:
        known_tables.add(jf.stem.lower())

    # Second pass: validate each file
    for jf in json_files:
        table_name = jf.stem
        result = TableCompletenessResult(table=table_name, file_path=str(jf))

        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            result.missing_keys = list(_REQUIRED_KEYS)
            result.empty_column_names = [f"PARSE_ERROR: {exc}"]
            results.append(result)
            continue

        # Check required keys
        for key in _REQUIRED_KEYS:
            if key not in data:
                result.missing_keys.append(key)

        if not result.missing_keys:
            col_names: list = data.get("column_names") or []
            col_types: list = data.get("column_types") or []

            # Length mismatch
            if len(col_names) != len(col_types):
                result.column_count_mismatch = True

            # Empty / None column names
            result.empty_column_names = [
                str(c) for c in col_names if not c or not str(c).strip()
            ]

            # FK reference check: look for "foreign_keys" or "fk" key
            for fk_key in ("foreign_keys", "fk", "relationships"):
                fk_refs: list = data.get(fk_key) or []
                for ref in fk_refs:
                    # common shape: {"to_table": "...", ...} or ["col", "ref_table.col"]
                    ref_table: Optional[str] = None
                    if isinstance(ref, dict):
                        ref_table = ref.get("to_table") or ref.get("ref_table") or ref.get("referenced_table")
                    elif isinstance(ref, (list, tuple)) and len(ref) >= 2:
                        # e.g. ["player.player_id", "player"]
                        maybe = str(ref[-1]).split(".")[0]
                        ref_table = maybe
                    if ref_table and ref_table.lower() not in known_tables:
                        result.broken_fk_references.append(ref_table)

        results.append(result)

    valid = sum(1 for r in results if r.is_valid)
    total = len(results)
    coverage = valid / total if total > 0 else 0.0

    return CompletenessReport(
        db_name=db_name,
        schema_dir=str(schema_dir),
        total_tables=total,
        valid_tables=valid,
        invalid_tables=total - valid,
        coverage_score=coverage,
        table_results=results,
        missing_schema_files=[],  # future: compare against live DB table list
    )
