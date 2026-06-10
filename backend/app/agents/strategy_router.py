"""
strategy_router.py
------------------
Given the FeasibilityAgent gap report and the SchemaExplorer findings,
an LLM reasons about HOW to answer the question and returns a strategy.

Strategies
----------
direct_sql
    The schema fully supports the question.  Continue with the standard
    SQL generation pipeline, optionally injecting exploration context.

enriched_sql
    The schema partially supports the question, but exploration revealed
    enough (e.g. a naming convention, a value distribution) to let the
    SQL generator write a better query with the extra context injected.

text_classify_aggregate
    A key filter/group dimension is encoded in free text (title,
    description) with no column.  The pipeline must:
      1. Fetch candidate rows (SQL)
      2. LLM-classify each row's text into the target category
      3. Aggregate the classified results in Python
    StrategyRouter returns the SQL to fetch rows + the classification
    spec so TextClassifyExecutor can run it.

cannot_answer
    The data genuinely cannot answer the question (column missing,
    dataset scope mismatch, etc.).  Return a graceful explanation.
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
Execution strategy planner. Choose HOW to answer a question given a schema and live data exploration.

## Strategies

| Strategy | When to use |
|---|---|
| `direct_sql` | Schema fully supports the question; no extra guidance needed |
| `enriched_sql` | Schema mostly works but exploration revealed patterns, conventions, or data quirks the SQL generator must know — OR a value must be extracted from free text via regex/CASE |
| `text_classify_aggregate` | A key dimension is DISCRETE NAMED CATEGORIES in free text AND you can write complete fetch_sql AND list exact categories right now |
| `cannot_answer` | Data genuinely cannot answer the question |

## NARROW JOIN PROTOCOL — mandatory when exploration shows "*** NARROW JOIN"
If SchemaExplorer reports `*** NARROW JOIN` between table A and table B on column C:
- The join `A.C = B.C` is the **only correct data anchor** — it defines the real queryable universe
- Scanning A alone or B alone returns WRONG results
- Your `enriched_context` MUST include:
  ```
  ANCHOR: FROM [A] JOIN [B] ON [A].[C] = [B].[C]
  Use [B].[path_col] for file-path filters — NOT [A]'s sample columns
  Do NOT scan [A] or [B] alone under any circumstances
  ```

## text_classify_aggregate rules
- ALL four conditions must hold: (a) no dedicated category column, (b) discrete named categories, (c) complete fetch_sql now, (d) exact category list now
- NEVER for numeric extraction — use `enriched_sql` instead
- Missing fetch_sql or categories → downgrade to `enriched_sql`

## Output — JSON only
```json
{
  "strategy": "direct_sql|enriched_sql|text_classify_aggregate|cannot_answer",
  "reasoning": "<2-3 sentences: WHY this strategy based on exploration>",
  "enriched_context": "<direct_sql/enriched_sql: SQL generation guidance; include NARROW JOIN anchor if detected>",
  "classify_spec": {
    "fetch_sql": "<REQUIRED: complete runnable SQL>",
    "id_column": "<unique row identifier>",
    "group_column": "<group-by column>",
    "text_columns": ["<col>"],
    "categories": ["<exact label>"],
    "target_category": "<target>",
    "classification_instruction": "<one sentence>"
  },
  "cannot_answer_reason": "<cannot_answer only>"
}
```"""

_USER_TMPL = """**Question:** {question}

**Schema:**
{schema_text}

**Feasibility gaps:**
{gap_report}

**Exploration findings:**
{exploration}

Choose the best strategy. If exploration shows NARROW JOIN, your enriched_context must include the join anchor."""


class StrategyRouter:
    """One LLM call that turns gap + exploration into an actionable execution plan."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def route(
        self,
        question: str,
        schema_text: str,
        feasibility: dict,
        exploration: str,
    ) -> dict:
        """
        Returns a strategy dict.  Never raises — falls back to direct_sql
        if the LLM call or parse fails.
        """
        gap_report = json.dumps(
            {
                "has_gaps": feasibility.get("has_gaps", False),
                "gap_summary": feasibility.get("gap_summary", ""),
                "gaps": [
                    {"term": c["term"], "reason": c.get("gap_reason", "")}
                    for c in feasibility.get("concepts", [])
                    if c.get("gap")
                ],
            },
            indent=2,
        )

        prompt = _USER_TMPL.format(
            question=question,
            schema_text=schema_text,
            gap_report=gap_report,
            exploration=exploration or "(no exploration performed)",
        )

        try:
            raw = self.llm.generate(
                system_prompt=_SYSTEM,
                user_prompt=prompt,
            )
            raw = self._strip_think(raw)
            result = self._parse(raw)
            if result:
                logger.info(f"[StrategyRouter] strategy={result['strategy']}")
                logger.info(f"[StrategyRouter] reasoning: {result['reasoning'][:120]}")
                return result
        except Exception as e:
            logger.debug(f"[StrategyRouter] failed (non-fatal): {e}")

        return self._default()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_think(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    @staticmethod
    def _parse(raw: str) -> Optional[dict]:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            obj = json.loads(raw[start:end])
            obj.setdefault("strategy", "direct_sql")
            obj.setdefault("reasoning", "")
            obj.setdefault("enriched_context", "")
            obj.setdefault("classify_spec", {})
            obj.setdefault("cannot_answer_reason", "")
            if obj["strategy"] not in (
                "direct_sql", "enriched_sql",
                "text_classify_aggregate", "cannot_answer"
            ):
                obj["strategy"] = "direct_sql"
            # Validate text_classify_aggregate — if spec is incomplete, downgrade to enriched_sql
            if obj["strategy"] == "text_classify_aggregate":
                spec = obj.get("classify_spec", {})
                missing_fetch = not spec.get("fetch_sql", "").strip()
                missing_cats = not spec.get("categories")
                if missing_fetch or missing_cats:
                    obj["strategy"] = "enriched_sql"
                    # Build an actionable context: reason (if any) + positive guidance to use
                    # string/regex extraction rather than giving up.
                    base = obj.get("enriched_context") or obj.get("reasoning", "")
                    guidance = (
                        "\nGUIDANCE: The required value may be embedded in a free-text column. "
                        "Use the EXPLORATION FINDINGS below to identify the exact column and pattern. "
                        "Use regexp_extract(), REGEXP_SUBSTR(), LIKE, or CASE expressions to extract it. "
                        "You MUST write a SQL query — do NOT refuse or return empty SQL."
                    )
                    obj["enriched_context"] = (base + guidance).strip()
                    logger.debug(
                        "[StrategyRouter] text_classify_aggregate classify_spec incomplete "
                        f"(missing: {'fetch_sql ' if missing_fetch else ''}{'categories' if missing_cats else ''}) "
                        "— downgraded to enriched_sql"
                    )
            return obj
        except Exception:
            return None

    @staticmethod
    def _default() -> dict:
        return {
            "strategy": "direct_sql",
            "reasoning": "Strategy routing failed; falling back to direct SQL generation.",
            "enriched_context": "",
            "classify_spec": {},
            "cannot_answer_reason": "",
        }
