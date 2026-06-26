"""
Post-generation, pre-execution dialect validator and auto-fixer.

Runs after the LLM produces SQL but BEFORE db_executor.execute().
Auto-fixes safe deterministic violations, flags unfixable ones.

Auto-fixed (deterministic, zero false-positive risk):
  char(N)                       → chr(N)
  \\d \\s \\w \\D \\S \\W inside SQL strings → character-class equivalents
  CAST(REGEXP_EXTRACT(          → TRY_CAST(REGEXP_EXTRACT(

Flagged (cannot auto-fix without regeneration):
  PCRE lookaheads/lookbehinds   (?= (?! (?< (?P
  JOIN predicate on function     ON REGEXP_EXTRACT(...) = col
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class PreflightResult:
    sql: str
    auto_fixed: bool
    fixes_applied: List[str] = field(default_factory=list)
    unfixable: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.unfixable


# Backslash sequences to replace inside SQL string literals.
# Ordered longest-first to avoid partial matches.
_BACKSLASH_SUBS = [
    (r"\D", "[^0-9]"),
    (r"\S", r"[^ \t]"),
    (r"\W", "[^a-zA-Z0-9_]"),
    (r"\d", "[0-9]"),
    (r"\s", r"[ \t]"),
    (r"\w", "[a-zA-Z0-9_]"),
]

# Matches a single-quoted SQL string literal, handling '' escapes.
_STRING_RE = re.compile(r"'(?:[^'\\]|''|\\.)*'", re.DOTALL)


def _fix_strings(sql: str) -> tuple[str, list[str]]:
    """Replace backslash meta-sequences inside SQL string literals."""
    fixes: list[str] = []
    changed = False

    def _patch(m: re.Match) -> str:
        nonlocal changed
        s = m.group()
        for bs, cls in _BACKSLASH_SUBS:
            if bs in s:
                s = s.replace(bs, cls)
                if s != m.group():
                    changed = True
        return s

    result = _STRING_RE.sub(_patch, sql)
    if changed:
        fixes.append("Replaced backslash regex escapes (\\d->[0-9], \\s->[ \\t], \\w->[a-zA-Z0-9_], etc.) inside string literals")
    return result, fixes


def check_and_fix(sql: str, dialect: str = "duckdb") -> PreflightResult:
    """
    Run the preflight checker on a generated SQL string.
    Returns a PreflightResult with the (possibly corrected) SQL,
    a list of fixes applied, and any unfixable violations.
    """
    if not sql or dialect.lower() not in ("duckdb",):
        return PreflightResult(sql=sql, auto_fixed=False)

    original = sql
    all_fixes: list[str] = []
    unfixable: list[str] = []

    # ── Auto-fix 1: char(N) → chr(N) ───────────────────────────────────────
    # Guard: must not match "varchar(" — require word boundary before "char"
    # and ensure it's not preceded by a letter (catches varchar, nchar, etc.)
    patched = re.sub(
        r'(?<![a-zA-Z])char\s*\(',
        'chr(',
        sql,
        flags=re.IGNORECASE,
    )
    if patched != sql:
        sql = patched
        all_fixes.append("char(N) -> chr(N)")

    # ── Auto-fix 2: backslash meta-sequences in string literals ─────────────
    sql, string_fixes = _fix_strings(sql)
    all_fixes.extend(string_fixes)

    # ── Auto-fix 3: CAST(REGEXP_EXTRACT → TRY_CAST(REGEXP_EXTRACT ───────────
    patched = re.sub(
        r'\bCAST\s*\(\s*REGEXP_EXTRACT\b',
        'TRY_CAST(REGEXP_EXTRACT',
        sql,
        flags=re.IGNORECASE,
    )
    if patched != sql:
        sql = patched
        all_fixes.append("CAST(REGEXP_EXTRACT(...)) -> TRY_CAST(REGEXP_EXTRACT(...))")

    # ── Flag: PCRE lookaheads / lookbehinds / named groups ──────────────────
    if re.search(r'\(\?[=!<P]', sql):
        unfixable.append(
            "PCRE construct detected ((?=, (?!, (?<, (?P<). "
            "DuckDB RE2 does not support lookaheads, lookbehinds, or named groups. "
            "Rewrite using capturing groups and post-extraction filtering."
        )

    # ── Flag: JOIN predicate on a function expression ───────────────────────
    if (re.search(r'\bON\s+REGEXP_EXTRACT\s*\(', sql, re.IGNORECASE) or
            re.search(r'=\s*REGEXP_EXTRACT\s*\(', sql, re.IGNORECASE)):
        unfixable.append(
            "JOIN predicate directly on REGEXP_EXTRACT(). "
            "Extract the value into a CTE column first, then join on that column."
        )

    auto_fixed = sql != original
    return PreflightResult(
        sql=sql,
        auto_fixed=auto_fixed,
        fixes_applied=all_fixes,
        unfixable=unfixable,
    )
