"""
Security validator for user input and LLM-generated SQL.

Two independent layers:

1. Prompt injection detection on user text — scans for instruction-override
   patterns, role-injection attempts, system-tag smuggling, and extraction
   probes before the query enters the reasoning pipeline.

2. Destructive SQL detection on LLM output — blocks any DDL/DML statement
   (DROP, DELETE, INSERT, UPDATE, TRUNCATE, CREATE, ALTER, GRANT, REVOKE,
   EXEC) before execution, enforcing a read-only contract on the pipeline.

Both checks are stateless regular-expression scans — no I/O, safe on hot paths.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SecurityViolation:
    """Structured record of a detected security threat."""

    threat_type: str   # "prompt_injection" | "destructive_sql"
    pattern: str       # Human-readable pattern label
    details: str       # Match position / excerpt


class SecurityValidator:
    """
    Stateless security validator.  All methods are class methods so callers
    never need to instantiate — ``SecurityValidator.check_user_input(text)``.
    """

    # ── Prompt injection patterns ─────────────────────────────────────────────
    # Tuples of (compiled_re, label).  Order matters: more specific patterns first.
    _INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"(?i)\bignore\s+(previous|above|all|prior)\b"), "instruction-override"),
        (re.compile(r"(?i)\bforget\s+(previous|everything|instructions|context)\b"), "context-erasure"),
        (re.compile(r"(?i)you\s+are\s+(now\s+)?(a|an|the)\s+\w+"), "role-injection"),
        (re.compile(r"(?i)\bact\s+as\b"), "role-injection"),
        (re.compile(r"(?i)\bpretend\s+(you\s+are|to\s+be)\b"), "role-injection"),
        (re.compile(r"(?i)\bdo\s+not\s+follow\b"), "instruction-override"),
        (re.compile(r"(?i)\byour\s+(real\s+)?instructions\s+are\b"), "instruction-override"),
        (re.compile(r"(?i)</?system>"), "system-tag-injection"),
        (re.compile(r"(?i)\[\s*system\s*\]"), "system-tag-injection"),
        (re.compile(r"(?i)###\s*(system|user|assistant)\s*:"), "prompt-delimiter-injection"),
        (re.compile(r"(?i)\breveal\s+(your\s+)?(system\s+)?(prompt|instructions)\b"), "extraction-attempt"),
        (re.compile(r"(?i)\bprint\s+(your\s+)?(system\s+)?(prompt|instructions)\b"), "extraction-attempt"),
        (re.compile(r"(?i)\bwhat\s+(are|were)\s+your\s+(original\s+)?instructions\b"), "extraction-attempt"),
        (re.compile(r"(?i)\bjailbreak\b"), "jailbreak"),
        (re.compile(r"(?i)\bDAN\b"), "jailbreak"),  # "Do Anything Now" jailbreak alias
    ]

    # ── Destructive SQL patterns ──────────────────────────────────────────────
    _DESTRUCTIVE_SQL_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"(?i)\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b"), "DROP statement"),
        (re.compile(r"(?i)\bDELETE\s+FROM\b"), "DELETE statement"),
        (re.compile(r"(?i)\bTRUNCATE\s+(TABLE\b|\w)"), "TRUNCATE statement"),
        (re.compile(r"(?i)\bINSERT\s+INTO\b"), "INSERT statement"),
        (re.compile(r"(?i)\bUPDATE\s+\w+\s+SET\b"), "UPDATE statement"),
        (re.compile(r"(?i)\bCREATE\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b"), "CREATE statement"),
        (re.compile(r"(?i)\bALTER\s+(TABLE|DATABASE|SCHEMA)\b"), "ALTER statement"),
        (re.compile(r"(?i)\bGRANT\s+\w"), "GRANT statement"),
        (re.compile(r"(?i)\bREVOKE\s+\w"), "REVOKE statement"),
        (re.compile(r"(?i)\bEXEC(UTE)?\s*\("), "EXEC statement"),
        (re.compile(r"(?i)\bxp_cmdshell\b"), "shell-execution"),
        (re.compile(r"(?i)\bSHUTDOWN\b"), "SHUTDOWN statement"),
    ]

    @classmethod
    def check_user_input(cls, text: str) -> Optional[SecurityViolation]:
        """
        Scan user-supplied text for prompt injection patterns.

        Returns a SecurityViolation on the first match, None when the input is clean.
        Callers should treat a non-None return as a 400 Bad Request.
        """
        for pattern, label in cls._INJECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                return SecurityViolation(
                    threat_type="prompt_injection",
                    pattern=label,
                    details=f"Matched '{m.group()}' at position {m.start()}",
                )
        return None

    @classmethod
    def check_generated_sql(cls, sql: str) -> Optional[SecurityViolation]:
        """
        Validate LLM-generated SQL against the destructive-statement blocklist.

        Returns a SecurityViolation if a dangerous pattern is detected, None otherwise.
        Callers should treat a non-None return as an execution block (log and reject).
        """
        for pattern, label in cls._DESTRUCTIVE_SQL_PATTERNS:
            m = pattern.search(sql)
            if m:
                return SecurityViolation(
                    threat_type="destructive_sql",
                    pattern=label,
                    details=f"Blocked '{m.group()}' — pipeline is read-only",
                )
        return None
