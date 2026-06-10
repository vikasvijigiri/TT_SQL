"""
feasibility_agent.py
--------------------
Diagnoses whether the schema can directly answer a question.

For every FILTER, GROUP-BY, and AGGREGATE concept extracted from the question,
it maps the concept to a schema column — or flags it as a GAP.

A gap means the question asks for something (e.g. "World category", "sentiment",
"genre") that has no direct column but may be inferrable from text content.

Output drives StrategyRouter to pick the right execution path before any SQL
is written, mirroring how a human analyst would first ask
"can this schema actually answer the question?" before writing code.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from backend.app.utils.llm import LLMClient
from backend.app.utils.logger import logger

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM = """## Role
Schema feasibility analyst. Determine whether each concept in the question maps to a real column or is a GAP.

## Task
Extract every FILTER, GROUP-BY, and AGGREGATE concept. For each:
- **DIRECT** → column values ARE the concept. `gap: false`
- **PROXY / GAP** → concept must be inferred from text (LIKE, regex, NLP). `gap: true`

## Direct vs Proxy — the hard rule
| Direct ✓ | Gap ✗ |
|---|---|
| `status IN ('active')` — column stores the label | `title LIKE '%World%'` — text search for a category |
| `date >= '2024'` — column stores the date | Extracting sentiment/intent from free text |
| `language = 'Python'` — dedicated column | `description LIKE '%Python%'` — no column |

**Hint files override ambiguity** — if a hint maps a concept to a column, that column IS the direct mapping.

## Output — JSON only, no markdown
```
{
  "concepts": [
    {
      "term": "<phrase from question>",
      "role": "filter|group_by|aggregate",
      "mapped_column": "<table.column> or null",
      "mapping_type": "direct|proxy|none",
      "gap": true|false,
      "gap_reason": "<gap=true only: why LIKE/proxy doesn't count>"
    }
  ],
  "has_gaps": true|false,
  "gap_summary": "<has_gaps=true only: one sentence on what's missing>"
}
```"""

_USER_TMPL = """**Question:** {question}

**Schema:**
{schema_text}

{hints_section}Map every concept. A LIKE search for a categorical label is always a GAP."""


class FeasibilityAgent:
    """
    Lightweight pre-flight check run once per query, before SQL generation.
    Adds ~1 LLM call on the fast path; triggers deeper exploration only when gaps exist.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def analyze(self, question: str, schema_text: str, hints: str = "") -> dict:
        """
        Map question concepts to schema columns.

        Args:
          hints: optional hint/description file content (e.g. db_description_withhint.txt)
                 — if provided, fed to the LLM so it knows about implicit encodings

        Returns a dict with keys:
          concepts      list of {term, role, mapped_column, gap, gap_reason}
          has_gaps      bool
          gap_summary   str (empty string when no gaps)
        """
        hints_section = f"Hint/description files:\n{hints.strip()}\n\n" if hints.strip() else ""
        prompt = _USER_TMPL.format(
            question=question,
            schema_text=schema_text,
            hints_section=hints_section,
        )
        try:
            raw = self.llm.generate(
                system_prompt=_SYSTEM,
                user_prompt=prompt,
            )
            raw = self._strip_think(raw)
            result = self._parse(raw)
            if result:
                logger.info(
                    f"[FeasibilityAgent] has_gaps={result['has_gaps']}  "
                    f"concepts={len(result['concepts'])}"
                )
                if result["has_gaps"]:
                    logger.info(f"[FeasibilityAgent] Gap: {result['gap_summary']}")
                return result
        except Exception as e:
            logger.debug(f"[FeasibilityAgent] failed (non-fatal): {e}")

        # Safe default — assume no gaps, continue with standard pipeline
        return {"concepts": [], "has_gaps": False, "gap_summary": ""}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_think(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    @staticmethod
    def _parse(raw: str) -> Optional[dict]:
        """Extract outermost JSON object from LLM output."""
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            obj = json.loads(raw[start:end])
            # Normalise
            if "concepts" not in obj:
                obj["concepts"] = []
            if "has_gaps" not in obj:
                obj["has_gaps"] = any(c.get("gap") for c in obj["concepts"])
            if "gap_summary" not in obj:
                obj["gap_summary"] = ""
            return obj
        except Exception:
            return None
