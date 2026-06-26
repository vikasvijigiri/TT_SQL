"""
WitnessHunter: Pre-generation database probing service.

Runs 2-4 lightweight read-only probes against the actual database
BEFORE the SQL generator is called. Discovers:
  - Exact text patterns in VARCHAR columns (regex anchoring)
  - Actual enum/categorical values (case, spacing)
  - JSON key paths in VARIANT columns
  - Join key overlap samples

Returns a "witness bundle" string injected into the generator's context
so it writes SQL constrained by confirmed real data — not guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent.app.models.schemas import SemanticContext, SemanticColumn
from agent.services.logger import logger


@dataclass
class WitnessBundle:
    probes_run: int = 0
    findings: List[str] = field(default_factory=list)

    def as_context_block(self) -> str:
        if not self.findings:
            return ""
        block = "=== PRE-GENERATION DATA WITNESSES (confirmed from real DB) ===\n"
        block += "Use these EXACT patterns — do not guess or deviate from confirmed data.\n\n"
        block += "\n\n".join(self.findings)
        block += "\n=== END WITNESSES ==="
        return block


def _is_sqlite_file(path: str) -> bool:
    """True if the file has the SQLite magic header."""
    try:
        with open(path, "rb") as f:
            return f.read(16).startswith(b"SQLite format 3")
    except Exception:
        return False


def _is_duckdb_file(path: str) -> bool:
    """True if the file contains the DuckDB magic bytes 'DUCK' in the first 16 bytes."""
    try:
        with open(path, "rb") as f:
            return b"DUCK" in f.read(16)
    except Exception:
        return False


def _find_primary_db(db_directory: str) -> Optional[tuple[str, str]]:
    """
    Return (path, type) of the primary DB file in db_directory.
    Prefers real DuckDB files (.duckdb extension OR 'DUCK' magic header).
    Falls back to the largest SQLite file if no DuckDB file found.
    """
    d = Path(db_directory)
    if not d.exists():
        return None

    all_db_files = list(d.glob("*.duckdb")) + list(d.glob("*.db"))

    # Prefer files with DuckDB magic header
    for p in all_db_files:
        if _is_duckdb_file(str(p)):
            try:
                import duckdb
                conn = duckdb.connect(str(p), read_only=True)
                conn.close()
                return str(p), "duckdb"
            except Exception:
                pass

    # Fall back to opening the largest SQLite file via DuckDB
    # (DuckDB can query SQLite files natively via ATTACH)
    sqlite_files = sorted(
        [p for p in all_db_files if _is_sqlite_file(str(p))],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if sqlite_files:
        primary = sqlite_files[0]
        try:
            import duckdb
            conn = duckdb.connect(":memory:")
            conn.execute("INSTALL sqlite; LOAD sqlite;")
            conn.execute(f"ATTACH '{primary}' AS _tmp (TYPE SQLITE, READ_ONLY);")
            conn.close()
            return str(primary), "sqlite_via_duckdb"
        except Exception:
            pass
        try:
            import sqlite3
            conn = sqlite3.connect(str(primary))
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            conn.close()
            return str(primary), "sqlite"
        except Exception:
            pass

    return None


def _find_sibling_dbs(db_directory: str, primary_path: str) -> list[tuple[str, str]]:
    """Return [(path, alias)] for all sibling DB files excluding the primary."""
    d = Path(db_directory)
    siblings: list[tuple[str, str]] = []
    for p in list(d.glob("*.db")) + list(d.glob("*.duckdb")):
        if str(p) == primary_path:
            continue
        alias = p.stem.replace("-", "_").replace(".", "_")
        siblings.append((str(p), alias))
    return siblings


def _run_probe(
    primary_path: str,
    db_type: str,
    sibling_dbs: list[tuple[str, str]],
    probe_sql: str,
    timeout_s: float = 5.0,
) -> Optional[list[dict]]:
    """Execute a single probe query and return rows as dicts, or None on failure."""
    try:
        if db_type == "duckdb":
            import duckdb
            conn = duckdb.connect(primary_path, read_only=True)
            # Attach SQLite siblings
            for sib_path, sib_alias in sibling_dbs:
                try:
                    conn.execute("INSTALL sqlite; LOAD sqlite;")
                    conn.execute(
                        f"ATTACH '{sib_path}' AS {sib_alias} (TYPE SQLITE, READ_ONLY);"
                    )
                except Exception:
                    pass
            rel = conn.execute(probe_sql)
            cols = [d[0] for d in rel.description]
            rows = rel.fetchmany(20)
            conn.close()
            return [dict(zip(cols, row)) for row in rows]
        elif db_type in ("sqlite", "sqlite_via_duckdb"):
            import sqlite3
            conn = sqlite3.connect(primary_path, timeout=timeout_s)
            # Attach sibling SQLite databases so probes can reference their tables
            for sib_path, sib_alias in sibling_dbs:
                try:
                    conn.execute(f"ATTACH '{sib_path}' AS {sib_alias}")
                except Exception:
                    pass
            conn.row_factory = sqlite3.Row
            cur = conn.execute(probe_sql)
            rows = cur.fetchmany(20)
            conn.close()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.debug(f"[WitnessHunter] Probe failed: {exc}")
    return None


def _col_is_variant(col: SemanticColumn) -> bool:
    t = (col.type or "").upper()
    return "VARIANT" in t or "JSON" in t or "OBJECT" in t or "ARRAY" in t


_ENUM_KEYWORDS = ("system", "type", "status", "kind", "category", "source",
                  "relation", "provenance", "label", "role", "mode")


def _col_is_short_varchar(col: SemanticColumn) -> bool:
    t = (col.type or "").upper()
    name_lower = col.name.lower()
    # TEXT/VARCHAR enum column (original check)
    if ("TEXT" in t or "VARCHAR" in t) and any(kw in name_lower for kw in _ENUM_KEYWORDS):
        return True
    # Integer categoricals (e.g. category_id, type_id) — same keywords, numeric type
    if any(kw in t for kw in ("INT", "BIGINT", "TINYINT", "SMALLINT")) and \
       any(kw in name_lower for kw in _ENUM_KEYWORDS):
        return True
    return False


_EMBED_NUM_NAME_KEYWORDS = (
    "information", "description", "details", "summary", "about", "content",
    "note", "comment", "bio", "info",
)


def _col_likely_has_embedded_numbers(col: SemanticColumn) -> bool:
    """True if the column likely contains natural-language text with embedded numbers.

    Uses name heuristics first (e.g. Project_Information) so probes fire even
    when the semantic context has no sample values for the column.
    """
    name_lower = col.name.lower()
    if any(kw in name_lower for kw in _EMBED_NUM_NAME_KEYWORDS):
        return True
    if not col.sample_values:
        return False
    joined = " ".join(str(v) for v in col.sample_values[:5])
    # Numbers embedded in text sentences
    return bool(re.search(r'[a-zA-Z].*[0-9]+.*[a-zA-Z]', joined)) and len(joined) > 80


def _format_rows(rows: list[dict], max_rows: int = 8) -> str:
    if not rows:
        return "  (no rows returned)"
    lines = []
    for row in rows[:max_rows]:
        parts = []
        for k, v in row.items():
            v_str = str(v)
            if len(v_str) > 200:
                v_str = v_str[:200] + "..."
            parts.append(f"{k}={repr(v_str)}")
        lines.append("  " + " | ".join(parts))
    return "\n".join(lines)


def _infer_regex_from_samples(col_name: str, rows: list[dict]) -> str:
    """Try to guess the regex pattern from sample text rows."""
    all_text = " ".join(str(list(r.values())[0]) for r in rows if r)
    # Look for "N stars", "stars count of N", "N forks", etc.
    # Each tuple: (detection regex, human label, extraction hint)
    metric_patterns = [
        (r'([0-9,]+)\s+stars', "stars (N stars format)",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, '([0-9,]+) star', 1), ',', '') AS BIGINT)"),
        (r'stars\s+count\s+of\s+([0-9,]+)', "stars (stars count of N format)",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, 'stars count of ([0-9,]+)', 1), ',', '') AS BIGINT)"),
        (r'([0-9,]+)\s+forks', "forks",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, '([0-9,]+) fork', 1), ',', '') AS BIGINT)"),
        (r'forks?\s+count\s+of\s+([0-9,]+)', "forks count of N",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, 'forks count of ([0-9,]+)', 1), ',', '') AS BIGINT)"),
        (r'([0-9,]+)\s+open\s+issues', "open issues",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, '([0-9,]+) open issue', 1), ',', '') AS BIGINT)"),
        (r'\bv?([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b', "version",
         f"REGEXP_EXTRACT({col_name}, '([0-9]+\\\\.[0-9]+(?:\\\\.[0-9]+)?)', 1)"),
        (r'([0-9]+(?:\.[0-9]+)?)\s*%', "percentage",
         f"TRY_CAST(REGEXP_EXTRACT({col_name}, '([0-9]+(?:\\\\.[0-9]+)?)\\\\s*%', 1) AS DOUBLE)"),
        (r'\$([0-9,]+(?:\.[0-9]+)?)', "currency",
         f"TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, '\\$([0-9,]+)', 1), ',', '') AS DOUBLE)"),
    ]
    hints = []
    seen_labels: set[str] = set()
    for pat, label, extraction in metric_patterns:
        if re.search(pat, all_text, re.IGNORECASE):
            base = label.split(" (")[0]
            hints.append(f"  Pattern '{label}' found. Use: {extraction}")
            seen_labels.add(base)
    # If BOTH star formats found in the same column, suggest COALESCE
    if "stars (N stars format)" in [h.split("'")[1] for h in hints if "stars" in h.lower()] \
            or ("stars (N stars format)" in str(hints) and "stars (stars count of N format)" in str(hints)):
        stars_hints = [h for h in hints if "stars" in h.lower()]
        if len(stars_hints) >= 2:
            hints.append(
                f"  IMPORTANT: Two star formats detected. Use COALESCE to handle both:\n"
                f"    COALESCE(\n"
                f"      TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, '([0-9,]+) star', 1), ',', '') AS BIGINT),\n"
                f"      TRY_CAST(REPLACE(REGEXP_EXTRACT({col_name}, 'stars count of ([0-9,]+)', 1), ',', '') AS BIGINT)\n"
                f"    )"
            )
    return "\n".join(hints) if hints else ""


def _run_probe_multi(
    primary_path: str,
    db_type: str,
    sibling_dbs: list[tuple[str, str]],
    probe_sql: str,
    timeout_s: float = 5.0,
) -> Optional[list[dict]]:
    """Run a probe against the primary DB first; if it returns None, try each sibling
    DB as a standalone connection.  This handles multi-DB datasets where a relevant
    table lives in a sibling file rather than the primary."""
    result = _run_probe(primary_path, db_type, sibling_dbs, probe_sql, timeout_s)
    if result is not None:
        return result
    for sib_path, _sib_alias in sibling_dbs:
        sib_type = "duckdb" if _is_duckdb_file(sib_path) else "sqlite"
        result = _run_probe(sib_path, sib_type, [], probe_sql, timeout_s)
        if result is not None:
            return result
    return None


def hunt(
    question: str,
    schema_context: SemanticContext,
    relevant_tables: List[str],
    db_directory: str,
    max_probes: int = 3,
) -> WitnessBundle:
    """
    Run targeted DB probes to discover real data patterns.
    Returns a WitnessBundle with a formatted context block.
    """
    bundle = WitnessBundle()

    if not schema_context or not schema_context.tables or not db_directory:
        return bundle

    db_info = _find_primary_db(db_directory)
    if not db_info:
        logger.debug("[WitnessHunter] No primary DB found in directory.")
        return bundle

    primary_path, db_type = db_info
    sibling_dbs = _find_sibling_dbs(db_directory, primary_path)

    question_lower = question.lower()
    probes_run = 0

    relevant_lower = {r.lower().split(".")[-1] for r in (relevant_tables or [])}
    if not relevant_lower:
        relevant_lower = {t.name.lower() for t in schema_context.tables}

    # ── Probe type 1 (highest priority): Text columns with embedded numbers ───
    # Runs first because natural-language columns with metrics are the hardest
    # to get right without seeing real data (regex patterns are not guessable).
    for tbl in schema_context.tables:
        if probes_run >= max_probes:
            break
        if tbl.name.lower() not in relevant_lower:
            continue
        for col in tbl.columns:
            if probes_run >= max_probes:
                break
            if _col_is_variant(col) or _col_is_short_varchar(col):
                continue
            t = (col.type or "").upper()
            if "TEXT" not in t and "VARCHAR" not in t:
                continue
            if not _col_likely_has_embedded_numbers(col):
                continue
            probe = (
                f"SELECT {col.name} FROM {tbl.name} "
                f"WHERE {col.name} IS NOT NULL LIMIT 5"
            )
            rows = _run_probe_multi(primary_path, db_type, sibling_dbs, probe)
            if rows is None:
                continue
            probes_run += 1
            if rows:
                sample_text = _format_rows(rows, max_rows=5)
                regex_hints = _infer_regex_from_samples(col.name, rows)
                finding = (
                    f"[WITNESS: {tbl.name}.{col.name} text pattern]\n"
                    f"Probe: {probe}\n"
                    f"Sample data:\n{sample_text}"
                )
                if regex_hints:
                    finding += f"\nInferred extraction patterns:\n{regex_hints}"
                finding += (
                    f"\nIMPORTANT: Use character classes [0-9] not \\d in REGEXP_EXTRACT. "
                    f"Always wrap with TRY_CAST(...) not CAST(...)."
                )
                bundle.findings.append(finding)

    # ── Probe type 1.5: JOIN fanout detection ────────────────────────────────
    # Runs before enum probes so it doesn't get squeezed out of the budget.
    # Checks whether relevant tables have multiple rows per apparent FK pair.
    for tbl in schema_context.tables:
        if probes_run >= max_probes:
            break
        if tbl.name.lower() not in relevant_lower:
            continue
        col_names = [c.name for c in tbl.columns]
        fk_pairs = [
            (c1, c2)
            for c1 in col_names for c2 in col_names
            if c1 != c2
            and any(k in c1.lower() for k in ("name", "id", "key"))
            and any(k in c2.lower() for k in ("name", "version", "id", "key"))
        ]
        if not fk_pairs:
            continue
        c1, c2 = fk_pairs[0]
        probe = (
            f"SELECT {c1}, {c2}, COUNT(*) AS cnt FROM {tbl.name} "
            f"GROUP BY {c1}, {c2} HAVING cnt > 1 LIMIT 3"
        )
        rows = _run_probe_multi(primary_path, db_type, sibling_dbs, probe)
        if rows is None:
            continue
        probes_run += 1
        if rows:
            bundle.findings.append(
                f"[WITNESS: {tbl.name} JOIN fanout warning]\n"
                f"Probe: {probe}\n"
                f"Result: {rows[:3]}\n"
                f"WARNING: {tbl.name} has multiple rows per ({c1}, {c2}). "
                f"JOINs on these columns will produce duplicate output rows. "
                f"Use SELECT DISTINCT or a deduplicating subquery."
            )

    # ── Probe type 2: Enum/categorical columns ─────────────────────────────
    for tbl in schema_context.tables:
        if probes_run >= max_probes:
            break
        if tbl.name.lower() not in relevant_lower:
            continue
        for col in tbl.columns:
            if probes_run >= max_probes:
                break
            if not _col_is_short_varchar(col):
                continue
            # Check if question mentions something relevant to this column
            if col.name.lower() not in question_lower and not col.sample_values:
                continue
            probe = (
                f"SELECT {col.name}, COUNT(*) AS cnt FROM {tbl.name} "
                f"WHERE {col.name} IS NOT NULL "
                f"GROUP BY {col.name} ORDER BY cnt DESC LIMIT 15"
            )
            rows = _run_probe_multi(primary_path, db_type, sibling_dbs, probe)
            if rows is None:
                continue  # failed probe — don't count against budget
            probes_run += 1
            if rows:
                vals = [(r.get(col.name), r.get("cnt")) for r in rows]
                vals_str = ", ".join(
                    f"'{v}' ({c})" for v, c in vals[:10] if v is not None
                )
                bundle.findings.append(
                    f"[WITNESS: {tbl.name}.{col.name} enum values]\n"
                    f"Probe: {probe}\n"
                    f"Confirmed values: {vals_str}\n"
                    f"Use exact casing shown above in WHERE / HAVING / CASE conditions."
                )

    # ── Probe type 2.5: Integer enum cross-reference ─────────────────────────
    # When a table has a low-cardinality integer column (e.g. category_id) plus
    # a FK column (e.g. article_id) that links to a sibling table with text content,
    # sample one title/text per category value so the agent knows what each ID means.
    if probes_run < max_probes:
        # Build a column-name → table index map for FK discovery
        _col_to_tables: dict[str, list[str]] = {}
        for _t in schema_context.tables:
            for _c in _t.columns:
                _col_to_tables.setdefault(_c.name.lower(), []).append(_t.name)

        for tbl in schema_context.tables:
            if probes_run >= max_probes:
                break
            if tbl.name.lower() not in relevant_lower:
                continue

            # Identify integer enum columns in this table
            int_enum_col = None
            for col in tbl.columns:
                t_upper = (col.type or "").upper()
                n_lower = col.name.lower()
                if any(kw in t_upper for kw in ("INT", "BIGINT", "TINYINT", "SMALLINT")) \
                   and any(kw in n_lower for kw in _ENUM_KEYWORDS):
                    int_enum_col = col
                    break
            if not int_enum_col:
                continue

            # Find a FK column in this table that also appears in another table with text
            for fk_col in tbl.columns:
                if not fk_col.name.lower().endswith("_id"):
                    continue
                shared_tables = [tn for tn in _col_to_tables.get(fk_col.name.lower(), [])
                                  if tn != tbl.name]
                if not shared_tables:
                    continue

                # Find a text column in the sibling table
                sibling_name = shared_tables[0]
                sibling_tbl = next((t for t in schema_context.tables if t.name == sibling_name), None)
                if sibling_tbl is None:
                    continue
                text_col = None
                for c in sibling_tbl.columns:
                    ct = (c.type or "").upper()
                    if "TEXT" in ct or "VARCHAR" in ct:
                        cn = c.name.lower()
                        if any(kw in cn for kw in ("title", "name", "description", "text", "content")):
                            text_col = c
                            break
                if not text_col:
                    continue

                # Get distinct enum values (skip if too many — not a real categorical)
                distinct_probe = (
                    f"SELECT DISTINCT {int_enum_col.name} FROM {tbl.name} "
                    f"WHERE {int_enum_col.name} IS NOT NULL ORDER BY {int_enum_col.name} LIMIT 10"
                )
                d_rows = _run_probe_multi(primary_path, db_type, sibling_dbs, distinct_probe)
                if not d_rows:
                    continue
                dist_vals = [r.get(int_enum_col.name) for r in d_rows
                             if r.get(int_enum_col.name) is not None]
                if len(dist_vals) < 2 or len(dist_vals) > 8:
                    continue

                # Sample one text row per category value
                sample_lines = []
                for val in dist_vals[:6]:
                    xprobe = (
                        f"SELECT {sibling_name}.{text_col.name} "
                        f"FROM {tbl.name} "
                        f"JOIN {sibling_name} ON {tbl.name}.{fk_col.name} = {sibling_name}.{fk_col.name} "
                        f"WHERE {tbl.name}.{int_enum_col.name} = {val} LIMIT 1"
                    )
                    x_rows = _run_probe_multi(primary_path, db_type, sibling_dbs, xprobe)
                    if x_rows and x_rows[0].get(text_col.name):
                        sample_val = str(x_rows[0][text_col.name])[:70]
                        sample_lines.append(f"  {int_enum_col.name}={val} → '{sample_val}'")

                if sample_lines:
                    probes_run += 1
                    bundle.findings.append(
                        f"[WITNESS: {tbl.name}.{int_enum_col.name} category mapping]\n"
                        f"Distinct values: {dist_vals}\n"
                        f"Sample content per value (from {sibling_name}.{text_col.name}):\n"
                        + "\n".join(sample_lines)
                        + f"\nUse WHERE {tbl.name}.{int_enum_col.name} = <value> to filter by topic. "
                        f"Identify the matching value from the sample content above."
                    )
                break  # one cross-reference per table is enough

    # ── Probe type 3: VARIANT/JSON columns — discover key paths ──────────────
    for tbl in schema_context.tables:
        if probes_run >= max_probes:
            break
        if tbl.name.lower() not in relevant_lower:
            continue
        for col in tbl.columns:
            if probes_run >= max_probes:
                break
            if not _col_is_variant(col):
                continue
            probe = (
                f"SELECT DISTINCT json_object_keys({col.name}) AS keys "
                f"FROM {tbl.name} WHERE {col.name} IS NOT NULL LIMIT 15"
            )
            rows = _run_probe_multi(primary_path, db_type, sibling_dbs, probe)
            if rows is None:
                continue  # failed probe — don't count against budget
            probes_run += 1
            keys = sorted({r.get("keys") for r in rows if r.get("keys")})
            if keys:
                bundle.findings.append(
                    f"[WITNESS: {tbl.name}.{col.name} JSON keys]\n"
                    f"Probe: {probe}\n"
                    f"Confirmed keys: {keys}\n"
                    f"Use: json_extract_string({col.name}, '$.key_name') for text values"
                )

    # ── Probe type 4: Content sample for long-text columns ───────────────────
    # Fires only when no witnesses found yet. Samples rows from multiple offsets
    # so the agent sees diverse real content (not just the first/longest rows).
    if not bundle.findings:
        for tbl in schema_context.tables:
            if probes_run >= max_probes:
                break
            if tbl.name.lower() not in relevant_lower:
                continue
            for col in tbl.columns:
                if probes_run >= max_probes:
                    break
                if _col_is_variant(col) or _col_is_short_varchar(col):
                    continue
                t = (col.type or "").upper()
                if "TEXT" not in t and "VARCHAR" not in t:
                    continue
                name_lower = col.name.lower()
                if not any(kw in name_lower for kw in (
                    "description", "content", "text", "body", "summary",
                    "abstract", "info", "detail", "note",
                )):
                    continue
                # Sample from two offsets (25% and 75%) to expose diverse content
                # patterns — datasets with implicit categories (e.g. news articles)
                # may have very different content in different parts of the table.
                total_probe = (
                    f"SELECT COUNT(*) AS n FROM {tbl.name} "
                    f"WHERE {col.name} IS NOT NULL"
                )
                total_rows = _run_probe_multi(primary_path, db_type, sibling_dbs, total_probe)
                n = total_rows[0].get("n", 0) if total_rows else 0
                # Three offsets: 25%, 55%, 80% — covers the start, middle, and
                # upper region of the table for maximum content diversity.
                offset_a = max(0, n // 4)          # 25%
                offset_b = max(0, (n * 11) // 20)  # 55%
                offset_c = max(0, (n * 4) // 5)    # 80%
                combined_rows: list = []
                for off in (offset_a, offset_b, offset_c):
                    probe_off = (
                        f"SELECT {col.name} FROM {tbl.name} "
                        f"WHERE {col.name} IS NOT NULL LIMIT 2 OFFSET {off}"
                    )
                    r = _run_probe_multi(primary_path, db_type, sibling_dbs, probe_off)
                    if r:
                        combined_rows.extend(r)
                if not combined_rows:
                    continue
                probes_run += 1
                probe = f"triple-offset sample at 25%, 55%, 80% of {tbl.name}"
                sample_text = _format_rows(combined_rows, max_rows=6)
                bundle.findings.append(
                    f"[WITNESS: {tbl.name}.{col.name} content sample]\n"
                    f"Probe: {probe}\n"
                    f"Sample data (diverse rows from different table regions):\n{sample_text}\n"
                    f"IMPORTANT: Inspect these samples to understand the REAL content format. "
                    f"Check whether a category/type column exists in related tables before "
                    f"using text filters. If no category column is available, use multiple "
                    f"OR-chained LIKE conditions on the text content to cover different "
                    f"vocabulary patterns for the same topic."
                )

    bundle.probes_run = probes_run
    if probes_run > 0:
        logger.info(
            f"[WitnessHunter] Ran {probes_run} probe(s), "
            f"found {len(bundle.findings)} witness(es)."
        )
    return bundle
