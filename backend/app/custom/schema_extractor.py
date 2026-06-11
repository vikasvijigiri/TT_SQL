"""
schema_extractor.py
-------------------
Extracts table schemas from a live database and writes per-table JSON files
in the IDC Format A expected by SemanticContextEngine:

  {
    "columns": [
      {"column_name": "id", "type": "INTEGER", "description": "", "sample_values": [1, 2, 3]},
      ...
    ],
    "sample": [{"id": 1, "name": "Alice"}, ...]
  }

One JSON file per table, filename = table_name.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.repositories.db_executor import DatabaseExecutor
from backend.app.utils.logger import logger


class SchemaExtractor:
    def __init__(self, executor: DatabaseExecutor):
        self.executor = executor
        self._dialect = (executor.dialect or "").lower()

    # ── Public entry point ────────────────────────────────────────────────────

    def extract_to_dir(self, output_dir: Path) -> int:
        """Extract schema to output_dir. Returns number of tables written."""
        output_dir.mkdir(parents=True, exist_ok=True)
        tables = self._list_tables()
        if not tables:
            logger.warning(f"[SchemaExtractor] No tables found for {self._dialect}.")
            return 0

        written = 0
        for table in tables:
            try:
                columns = self._describe_table(table)
                sample_rows = self._sample_rows(table)

                col_samples: Dict[str, List[Any]] = {}
                for row in sample_rows:
                    for k, v in row.items():
                        col_samples.setdefault(k, []).append(v)

                table_json: Dict[str, Any] = {
                    "columns": [
                        {
                            "column_name": col["name"],
                            "type": col["type"],
                            "description": "",
                            "sample_values": col_samples.get(col["name"], [])[:3],
                        }
                        for col in columns
                    ],
                    "sample": sample_rows[:5],
                }

                out_file = output_dir / f"{table}.json"
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(table_json, f, indent=2, default=str)
                written += 1
                logger.info(f"[SchemaExtractor] Wrote {out_file.name}")
            except Exception as e:
                logger.warning(f"[SchemaExtractor] Failed on table '{table}': {e}")

        logger.info(f"[SchemaExtractor] Extracted {written}/{len(tables)} tables -> {output_dir}")
        return written

    # ── Table listing ─────────────────────────────────────────────────────────

    def _list_tables(self) -> List[str]:
        d = self._dialect
        if d == "sqlite":
            sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        elif d in ("postgres", "postgresql"):
            sql = (
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
        elif d == "duckdb":
            sql = "SHOW TABLES"
        elif d == "snowflake":
            sql = "SHOW TABLES"
        elif d == "mysql":
            sql = "SHOW TABLES"
        else:
            sql = "SHOW TABLES"

        ok, _, rows = self.executor.execute_direct(sql)
        if not ok or not rows:
            return []
        return [str(list(r.values())[0]) for r in rows if r]

    # ── Column descriptions ───────────────────────────────────────────────────

    def _describe_table(self, table: str) -> List[Dict[str, str]]:
        d = self._dialect
        safe = table.replace('"', "")

        if d == "sqlite":
            sql = f'PRAGMA table_info("{safe}")'
            ok, _, rows = self.executor.execute_direct(sql)
            if ok and rows:
                return [{"name": r.get("name", ""), "type": r.get("type", "TEXT") or "TEXT"} for r in rows]

        elif d in ("postgres", "postgresql"):
            sql = (
                f"SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_name = '{safe}' AND table_schema = 'public' "
                f"ORDER BY ordinal_position"
            )
            ok, _, rows = self.executor.execute_direct(sql)
            if ok and rows:
                return [
                    {"name": r.get("column_name", ""), "type": r.get("data_type", "TEXT") or "TEXT"}
                    for r in rows
                ]

        elif d == "duckdb":
            sql = f'PRAGMA table_info("{safe}")'
            ok, _, rows = self.executor.execute_direct(sql)
            if ok and rows:
                return [{"name": r.get("name", ""), "type": r.get("type", "TEXT") or "TEXT"} for r in rows]

        elif d == "snowflake":
            sql = f'DESCRIBE TABLE "{safe}"'
            ok, _, rows = self.executor.execute_direct(sql)
            if ok and rows:
                return [
                    {
                        "name": r.get("name", "") or r.get("NAME", ""),
                        "type": r.get("type", "") or r.get("TYPE", "") or "TEXT",
                    }
                    for r in rows
                ]

        elif d == "mysql":
            sql = f"DESCRIBE `{safe}`"
            ok, _, rows = self.executor.execute_direct(sql)
            if ok and rows:
                return [
                    {
                        "name": r.get("Field", "") or r.get("field", ""),
                        "type": r.get("Type", "") or r.get("type", "") or "TEXT",
                    }
                    for r in rows
                ]

        # Fallback: SELECT * LIMIT 0 to get column names only
        return self._infer_columns_from_select(safe)

    def _infer_columns_from_select(self, table: str) -> List[Dict[str, str]]:
        sql = f'SELECT * FROM "{table}" LIMIT 1'
        ok, _, rows = self.executor.execute_direct(sql)
        if ok and rows:
            return [{"name": k, "type": "TEXT"} for k in rows[0].keys()]
        return []

    # ── Sample rows ───────────────────────────────────────────────────────────

    def _sample_rows(self, table: str) -> List[Dict[str, Any]]:
        safe = table.replace('"', "")
        sql = f'SELECT * FROM "{safe}" LIMIT 5'
        ok, _, rows = self.executor.execute_direct(sql)
        return rows if ok else []
