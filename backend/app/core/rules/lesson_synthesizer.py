"""
lesson_synthesizer.py
---------------------
Extracts generic, database-agnostic SQL rules from successful SQL correction events.
Saves these rules dynamically to dynamic_lessons.json.
"""
import re
import json
import time
import hashlib
from typing import Dict, Any, Optional
from backend.app.core.rules.dynamic_rule_store import DynamicRuleStore
from backend.app.utils.logger import logger
from backend.app.utils.llm import LLMClient

_SYSTEM_PROMPT = """\
Analyze a corrected SQL event and synthesize a generic, reusable rule.
CONSTRAINTS:
1. STRICTLY database/schema agnostic: NO table, column, DB names, or data values.
2. Derived from how the fix resolved the failure.
3. Return a JSON object matching:
{"rule_title": "Title (<=10 words)", "error_cause": "1-2 sentences generic cause", "generic_rule": "2-4 sentences rule", "intent_pattern": "keywords", "category": "aggregation|join|filtering|casting|ordering|subquery|string_match|date_handling|numeric_precision|schema_inference"}
No other text.\
"""

class LessonSynthesizer:
    def __init__(self, llm_client=None):
        self.llm = llm_client or LLMClient()
        self.store = DynamicRuleStore()

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        # Try markdown block
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # Find outermost { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidate = text[start : end + 1]
            candidate = re.sub(r"//[^\n]*", "", candidate)
            candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
            try:
                return json.loads(candidate)
            except Exception:
                pass
        return None

    def synthesize_and_save(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        corrected_sql: str,
        dialect: str,
        dataset: str = "",
        instance_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesizes a rule from a correction event and saves it to dynamic_lessons.json as ACTIVE.
        """
        if not failed_sql or not corrected_sql or failed_sql.strip() == corrected_sql.strip():
            return None

        user_prompt = (
            "=== SQL CORRECTION EVENT ===\n\n"
            f"Dialect: {dialect}\n"
            f"Dataset / DB: {dataset}\n"
            f"NL Question: {question[:400]}\n\n"
            f"FAILED SQL:\n{failed_sql[:1500]}\n\n"
            f"ERROR / FAILURE REASON:\n{error_message[:1000]}\n\n"
            f"SUCCESSFUL CORRECTED SQL:\n{corrected_sql[:1500]}\n\n"
            "Identify why the failed SQL was incorrect, how the corrected SQL fixed it, and synthesize a generic rule for this dialect."
        )

        try:
            raw = self.llm.generate(_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning(f"LessonSynthesizer: LLM generation failed: {e}")
            return None

        # Clean reasoning tags if any
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)

        # Parse JSON
        rule_data = self._extract_json_object(raw)
        if not rule_data:
            logger.warning("LessonSynthesizer: failed to parse JSON response from LLM")
            return None

        # Validate fields
        required = {"rule_title", "error_cause", "generic_rule", "intent_pattern", "category"}
        if not required.issubset(rule_data.keys()):
            logger.warning(f"LessonSynthesizer: missing required fields in JSON: {rule_data.keys()}")
            return None

        generic_rule = rule_data["generic_rule"]
        self.store.reload()  # Make sure we have the latest rules from disk
        if self.store.is_covered(generic_rule) or self.store.was_tried_before(generic_rule):
            logger.info("LessonSynthesizer: Synthesized rule is already covered or was tried before. Skipping.")
            return None

        lesson_id = f"dyn_{int(time.time() * 1000) % 10_000_000_000}_{hashlib.sha256(generic_rule.encode()).hexdigest()[:6]}"
        
        new_rule = {
            "lesson_id": lesson_id,
            "intent_pattern": rule_data["intent_pattern"],
            "rule_title": rule_data["rule_title"],
            "error_cause": rule_data["error_cause"],
            "generic_rule": generic_rule,
            "category": rule_data["category"],
            "dialect": dialect.lower(),
            "source_failures": [f"{dataset}_{instance_id}" if dataset else instance_id],
            "db_name": dataset.upper(),
            "status": "ACTIVE",  # Since it's successfully corrected, mark it active immediately
            "applications": 1,
            "successes": 1,
        }

        self.store._rules.append(new_rule)
        self.store._save()
        logger.info(f"LessonSynthesizer: Synthesized and saved ACTIVE rule '{rule_data['rule_title']}' [{lesson_id}] for {dialect}")
        return new_rule
