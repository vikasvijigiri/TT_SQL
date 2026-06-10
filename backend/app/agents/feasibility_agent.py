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

_SYSTEM = """You are a database feasibility analyst with deep SQL expertise.

Given a natural language question, a database schema, and any available hint/description files,
your job is to:
1. Extract every FILTER concept, GROUP-BY dimension, and AGGREGATE target from the question
2. Map each concept to a schema column ONLY if the column DIRECTLY stores that value
3. Flag as a GAP any concept where no column stores it directly

CRITICAL DISTINCTION — direct vs proxy:
- DIRECT: a column whose values ARE the concept (e.g. column "status" with values "active/inactive"
  maps directly to a filter on "active users")
- PROXY / GAP: using a text field with LIKE as an approximation is NOT a direct mapping.
  If the concept is a categorical label (category, genre, type, topic, sentiment, language)
  that has no dedicated column, it is a GAP even if some text fields contain the word.
  Example: "World category" is a GAP if there is no column named "category" — filtering
  title LIKE '%World%' is a flawed proxy, not a real mapping.

A GAP means the question asks for something that cannot be answered by a
straightforward WHERE / GROUP BY on existing columns without semantic reasoning.
Common gap patterns:
- A categorical label (category, genre, type, topic) encoded only in free text
- A derived attribute requiring text understanding (sentiment, intent, language)
- A business concept not stored in any column
- A temporal reference that cannot be derived from available date columns

If hint/description files are provided, use them — they often reveal hidden encodings.

Respond ONLY with a JSON object — no prose, no markdown fences:
{
  "concepts": [
    {
      "term": "<concept phrase from the question>",
      "role": "filter|group_by|aggregate",
      "mapped_column": "<table.column> or null",
      "mapping_type": "direct|proxy|none",
      "gap": true or false,
      "gap_reason": "<if gap=true: one sentence explaining what is missing and why proxy doesn't count>"
    }
  ],
  "has_gaps": true or false,
  "gap_summary": "<if has_gaps: one concise sentence describing the core missing information>"
}"""

_USER_TMPL = """Question: {question}

Schema:
{schema_text}

{hints_section}Analyze feasibility. Remember: a PROXY text search (LIKE) for a categorical concept is still a GAP."""


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
