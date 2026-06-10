"""
schema_explorer.py
------------------
When the FeasibilityAgent detects a gap (a question concept with no schema column),
SchemaExplorer runs lightweight, zero-LLM introspection to understand the data:

  1. SELECT DISTINCT on every column of every relevant table (up to 50 values each)
  2. SELECT sample rows (10–20) from relevant tables
  3. Read any hint / description files provided by the caller
  4. Summarise raw findings as plain text for StrategyRouter

All of this is deterministic SQL + file I/O — no LLM call, no hardcoding.
The analyst pattern: "before deciding how to query, look at the data."
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.app.utils.logger import logger


class SchemaExplorer:
    """
    Runs introspection queries against the live database and reads auxiliary
    description files. Returns a human-readable findings string.
    """

    MAX_DISTINCT_VALUES = 50
    MAX_SAMPLE_ROWS = 20
    MAX_TEXT_SAMPLE_CHARS = 120   # truncate long text fields in display

    def explore(
        self,
        gap_concepts: list[str],
        schema_text: str,
        executor,                         # DatabaseExecutor instance
        hint_files: Optional[list[str]] = None,
        description_text: Optional[str] = None,
    ) -> str:
        """
        Returns a multi-section exploration report as plain text.
        Never raises — failures are caught and noted in the report.
        """
        sections: list[str] = []

        # 1. Read hint / description files
        hint_text = self._read_hints(hint_files, description_text)
        if hint_text:
            sections.append(f"=== HINT FILES ===\n{hint_text}")

        # 2. Parse table names from schema_text
        tables = self._extract_table_names(schema_text)
        if not tables:
            sections.append("(Could not extract table names from schema)")
            return "\n\n".join(sections)

        # 3. SELECT DISTINCT on all columns (understand value space)
        distinct_section = self._probe_distinct_values(tables, executor)
        if distinct_section:
            sections.append(f"=== COLUMN VALUE SAMPLES ===\n{distinct_section}")

        # 4. Sample rows (understand text field content)
        sample_section = self._probe_sample_rows(tables, executor)
        if sample_section:
            sections.append(f"=== SAMPLE ROWS ===\n{sample_section}")

        # 5. Summarise gap concepts against what was found
        gap_note = (
            f"=== GAP ANALYSIS ===\n"
            f"The question requires: {', '.join(gap_concepts)}\n"
            f"None of the above map directly to a schema column.\n"
            f"Based on the data above, reason about how to derive this information."
        )
        sections.append(gap_note)

        report = "\n\n".join(sections)
        logger.info(f"[SchemaExplorer] Report ready ({len(report)} chars, {len(sections)} sections)")
        return report

    # ------------------------------------------------------------------
    # Hint / description file reader
    # ------------------------------------------------------------------

    def _read_hints(
        self,
        hint_files: Optional[list[str]],
        description_text: Optional[str],
    ) -> str:
        parts: list[str] = []

        if description_text:
            parts.append(description_text.strip()[:2000])

        if hint_files:
            for fpath in hint_files:
                p = Path(fpath)
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace").strip()
                        parts.append(f"[{p.name}]\n{content[:2000]}")
                    except Exception as e:
                        parts.append(f"[{p.name}] (read error: {e})")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Live DB probing
    # ------------------------------------------------------------------

    def _probe_distinct_values(self, tables: list[str], executor) -> str:
        lines: list[str] = []
        dialect = getattr(executor, "dialect", "sqlite")
        quote = '"' if dialect in ("sqlite", "postgres", "duckdb") else "`"

        for table in tables:
            # Get column names first
            try:
                col_sql = self._columns_query(table, dialect, quote)
                ok, _, col_data = executor.execute_direct(col_sql)
                if not ok or not col_data:
                    continue
                # PRAGMA table_info returns rows with (cid, name, type, ...) — name is index 1
                columns = [list(r.values())[1] if len(r) > 1 else list(r.values())[0] for r in col_data]
            except Exception as e:
                logger.debug(f"[SchemaExplorer] col probe failed for {table}: {e}")
                continue

            for col in columns[:12]:   # cap at 12 columns per table
                try:
                    q = (
                        f'SELECT DISTINCT {quote}{col}{quote} '
                        f'FROM {quote}{table}{quote} '
                        f'WHERE {quote}{col}{quote} IS NOT NULL '
                        f'LIMIT {self.MAX_DISTINCT_VALUES}'
                    )
                    ok2, _, raw_rows = executor.execute_direct(q)
                    if not ok2 or not raw_rows:
                        continue
                    vals = [str(list(r.values())[0])[:60] for r in raw_rows]
                    lines.append(f"  {table}.{col}: [{', '.join(vals[:20])}]")
                except Exception:
                    continue

        return "\n".join(lines) if lines else "(no distinct value data)"

    def _probe_sample_rows(self, tables: list[str], executor) -> str:
        lines: list[str] = []
        dialect = getattr(executor, "dialect", "sqlite")
        quote = '"' if dialect in ("sqlite", "postgres", "duckdb") else "`"

        for table in tables[:4]:   # limit to first 4 tables
            try:
                q = f'SELECT * FROM {quote}{table}{quote} LIMIT {self.MAX_SAMPLE_ROWS}'
                ok2, _, raw_rows = executor.execute_direct(q)
                if not ok2 or not raw_rows:
                    continue
                lines.append(f"  Table: {table}")
                lines.append(f"  Columns: {list(raw_rows[0].keys())}")
                for row in raw_rows[:5]:
                    truncated = {k: str(v)[:self.MAX_TEXT_SAMPLE_CHARS] for k, v in row.items()}
                    lines.append(f"    {truncated}")
            except Exception as e:
                logger.debug(f"[SchemaExplorer] sample failed for {table}: {e}")
                continue

        return "\n".join(lines) if lines else "(no sample row data)"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_table_names(schema_text: str) -> list[str]:
        """Parse table names from formatted schema text."""
        import re
        # Match "Table: tablename" or "tablename (" patterns
        patterns = [
            r"Table:\s*[`\"]?(\w+)[`\"]?",
            r"^[`\"]?(\w+)[`\"]?\s*\(",
            r"CREATE TABLE\s+[`\"]?(\w+)[`\"]?",
        ]
        found = []
        for pat in patterns:
            matches = re.findall(pat, schema_text, re.I | re.M)
            found.extend(matches)
        # deduplicate preserving order
        seen = set()
        result = []
        for t in found:
            if t.lower() not in seen and t.lower() not in ("create", "table", "if"):
                seen.add(t.lower())
                result.append(t)
        return result

    @staticmethod
    def _columns_query(table: str, dialect: str, quote: str) -> str:
        if dialect in ("sqlite", "duckdb"):
            return f"PRAGMA table_info({quote}{table}{quote})"
        elif dialect == "postgres":
            return (
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name = '{table}' ORDER BY ordinal_position"
            )
        else:
            return f"SHOW COLUMNS FROM {quote}{table}{quote}"
