"""
rule_extractor_agent.py
-----------------------
Extracts generic, database-agnostic SQL rules from query failures.

Strict constraints:
  - NO hardcoded table/column/value names
  - Rules derived entirely from observed failure patterns
  - NO hallucination — only what can be inferred from the failure
"""
import re
import json
from typing import List, Dict, Any

from backend.app.utils.logger import logger

_SYSTEM_PROMPT = """\
Extract 1-2 SHORT, GENERIC, ACTIONABLE SQL rules from query failures.
CONSTRAINTS:
1. STRICTLY generic: NO specific table/column/dataset names or data values of anysort etc.
2. Derived ONLY from the failure. No speculation.
3. Return a JSON array matching:
[{"rule_title": "Title (<=10 words)", "generic_rule": "2-4 sentences rule", "intent_pattern": "keywords", "category": "aggregation|join|filtering|casting|ordering|subquery|string_match|date_handling|numeric_precision|schema_inference"}]
No other text. Return [] if no rule is learnable.\
"""


def extract_rules_from_failure(
    llm,
    question: str,
    sql_generated: str,
    error_or_mismatch: str,
    ground_truth_hint: str = "",
    dataset: str = "",
    log_tail: str = "",
) -> List[Dict[str, Any]]:
    """
    Call the LLM to extract candidate rules from a single query failure.

    Args:
        llm: LLMClient instance (uses llm.generate())
        question: the NL question that was asked
        sql_generated: the SQL the pipeline produced
        error_or_mismatch: the evaluator's failure reason string
        ground_truth_hint: optional snippet of the ground truth (truncated for safety)
        dataset: dataset name (for context only, not to be used in rules)
        log_tail: optional log tail containing recent execution logs

    Returns:
        List of rule dicts validated against the required schema.
    """
    user_prompt = (
        "=== QUERY FAILURE REPORT ===\n\n"
        f"Question: {question[:400]}\n"
        f"Dataset type: {dataset}\n"
    )
    if log_tail:
        user_prompt += f"=== RECENT EXECUTION LOG TRACE ===\n{log_tail}\n\n"
    else:
        user_prompt += (
            f"SQL produced:\n{sql_generated[:1500]}\n\n"
            f"Failure reason: {error_or_mismatch[:600]}\n"
        )
    if ground_truth_hint:
        user_prompt += f"Ground truth hint (truncated): {ground_truth_hint[:250]}\n"
    user_prompt += (
        "\nExtract 1–2 generic SQL rules that would prevent this failure category. "
        "Return ONLY a JSON array — no prose before or after.\n"
        "```json\n[\n  {\n    \"rule_title\": \"...\",\n    \"generic_rule\": \"...\","
        "\n    \"intent_pattern\": \"...\",\n    \"category\": \"...\"\n  }\n]\n```"
    )

    try:
        raw = llm.generate(_SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning(f"RuleExtractorAgent: LLM call failed: {e}")
        return []

    # Strip think tags
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    if "<think>" in raw:
        idx = raw.find("{")
        if idx != -1:
            raw = raw[idx:]

    # Parse JSON array
    rules_raw = _extract_json_array(raw)
    if rules_raw is None:
        logger.warning(f"RuleExtractorAgent: no JSON array found in LLM output")
        return []

    validated: List[Dict[str, Any]] = []
    required_keys = {"rule_title", "generic_rule", "intent_pattern", "category"}
    valid_categories = {
        "aggregation", "join", "filtering", "casting", "ordering",
        "subquery", "string_match", "date_handling", "numeric_precision", "schema_inference",
    }
    for item in rules_raw:
        if not isinstance(item, dict):
            continue
        if not required_keys.issubset(item.keys()):
            continue
        if item.get("category") not in valid_categories:
            item["category"] = "filtering"
        rule_text = item.get("generic_rule", "")
        if len(rule_text) < 20:
            continue
        validated.append({k: str(item[k]).strip() for k in required_keys})

    return validated


def _extract_json_array(text: str) -> Any:
    """Extract the outermost JSON array from text."""
    # Try markdown block
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # Find outermost [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        # Strip inline comments
        candidate = re.sub(r"//[^\n]*", "", candidate)
        candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None
