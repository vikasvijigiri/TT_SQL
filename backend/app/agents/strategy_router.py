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

_SYSTEM = """You are a senior data engineer who decides HOW to answer a natural language question
given a database schema and live data exploration results.

Choose one of four strategies:

1. direct_sql
   Schema fully supports the question. No additional context needed beyond the schema.

2. enriched_sql
   Schema mostly supports it but exploration revealed useful context (value patterns,
   naming conventions, data quirks) worth injecting into SQL generation.

3. text_classify_aggregate
   A key concept (filter or group-by dimension) has no column but is encoded in a
   text field (title, description, notes, etc.).
   Use this when the only way to answer is:
     a) Fetch rows with text fields
     b) Classify each row's text into the required categories
     c) Aggregate the classified results
   Provide a fetch_sql and a classify_spec.

4. cannot_answer
   The data genuinely does not contain the information needed.

Respond ONLY with a JSON object (no markdown, no prose):
{
  "strategy": "direct_sql | enriched_sql | text_classify_aggregate | cannot_answer",
  "reasoning": "<2-3 sentences explaining WHY this strategy, based on the exploration>",
  "enriched_context": "<for direct_sql/enriched_sql: additional text to inject into SQL generation prompt; empty string otherwise>",
  "classify_spec": {
    "fetch_sql": "<for text_classify_aggregate: SQL to fetch (id_col, group_col, text_col1, text_col2, ...) from the DB>",
    "id_column": "<column name that uniquely identifies each row>",
    "group_column": "<column to group by after classification>",
    "text_columns": ["<col1>", "<col2>"],
    "categories": ["<cat1>", "<cat2>", "..."],
    "target_category": "<the category we want to filter to>",
    "classification_instruction": "<one sentence telling the classifier what to look for>"
  },
  "cannot_answer_reason": "<for cannot_answer: explanation for the user; empty string otherwise>"
}"""

_USER_TMPL = """Question: {question}

Schema:
{schema_text}

FeasibilityAgent gap report:
{gap_report}

SchemaExplorer findings:
{exploration}

Choose the best strategy to answer this question."""


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
