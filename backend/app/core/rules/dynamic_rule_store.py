"""
dynamic_rule_store.py
---------------------
Persistent rule store that manages the lifecycle of learned SQL rules.
Rules flow: CANDIDATE → ACTIVE | REJECTED → (eventually) INACTIVE

Deduplication uses two-level Jaccard similarity:
  - COVER_THRESHOLD (0.38): blocks adding a rule too similar to any ACTIVE/CANDIDATE rule.
  - TRIED_THRESHOLD (0.65): blocks re-adding a rule very similar to any previously-tried rule
    (any status, including REJECTED) — enforces convergence.
"""
import json
import os
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.app.core.config import MEMORY_DIR
from backend.app.utils.logger import logger

DYNAMIC_LESSONS_FILE = MEMORY_DIR / "dynamic_lessons.json"

MAX_RULES = 60
COVER_THRESHOLD = 0.38
TRIED_THRESHOLD = 0.65
DEPRECATE_MIN_APPS = 5
DEPRECATE_SUCCESS_RATE = 0.15


class DynamicRuleStore:
    def __init__(self, path: Path = DYNAMIC_LESSONS_FILE):
        self.path = path
        self._rules: List[Dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._rules = data if isinstance(data, list) else []
            except Exception as e:
                logger.warning(f"DynamicRuleStore: failed to load {self.path}: {e}")
                self._rules = []
        else:
            self._rules = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._rules, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception as e:
            logger.error(f"DynamicRuleStore: save failed: {e}")

    def reload(self) -> None:
        """Re-read from disk (useful after another process wrote the file)."""
        self._load()

    # ------------------------------------------------------------------
    # Similarity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set:
        return set(text.lower().split())

    def _jaccard(self, a: str, b: str) -> float:
        ta, tb = self._tokenize(a), self._tokenize(b)
        if not ta and not tb:
            return 1.0
        inter = len(ta & tb)
        union = len(ta | tb)
        return inter / union if union else 0.0

    # ------------------------------------------------------------------
    # Dedup guards
    # ------------------------------------------------------------------

    def is_covered(self, generic_rule: str) -> bool:
        """True if an ACTIVE or CANDIDATE rule is already similar enough."""
        for r in self._rules:
            if r.get("status") in ("ACTIVE", "CANDIDATE"):
                if self._jaccard(generic_rule, r.get("generic_rule", "")) >= COVER_THRESHOLD:
                    return True
        return False

    def was_tried_before(self, generic_rule: str) -> bool:
        """True if a highly-similar rule has been tried before (any status)."""
        for r in self._rules:
            if self._jaccard(generic_rule, r.get("generic_rule", "")) >= TRIED_THRESHOLD:
                return True
        return False

    # ------------------------------------------------------------------
    # Rule lifecycle
    # ------------------------------------------------------------------

    def add_rule(
        self,
        rule_title: str,
        generic_rule: str,
        intent_pattern: str,
        category: str,
        source_failure: str,
        db_name: str = "",
    ) -> Optional[str]:
        """
        Add a CANDIDATE rule if not already covered or tried.
        Returns the new lesson_id, or None if skipped.
        """
        if self.is_covered(generic_rule) or self.was_tried_before(generic_rule):
            return None
        active_candidate_count = sum(
            1 for r in self._rules if r.get("status") in ("ACTIVE", "CANDIDATE")
        )
        if active_candidate_count >= MAX_RULES:
            logger.warning("DynamicRuleStore: MAX_RULES reached, skipping new rule")
            return None

        lesson_id = f"dyn_{int(time.time() * 1000) % 10_000_000_000}_{hashlib.sha256(generic_rule.encode()).hexdigest()[:6]}"
        rule = {
            "lesson_id": lesson_id,
            "intent_pattern": intent_pattern,
            "rule_title": rule_title,
            "generic_rule": generic_rule,
            "category": category,
            "source_failures": [source_failure],
            "db_name": db_name,
            "status": "CANDIDATE",
            "applications": 0,
            "successes": 0,
        }
        self._rules.append(rule)
        self._save()
        logger.info(f"DynamicRuleStore: added CANDIDATE '{rule_title}' [{lesson_id}]")
        return lesson_id

    def activate_candidates(self, lesson_ids: Optional[List[str]] = None) -> int:
        """Promote CANDIDATE → ACTIVE. Returns count promoted."""
        count = 0
        for r in self._rules:
            if r.get("status") == "CANDIDATE":
                if lesson_ids is None or r["lesson_id"] in lesson_ids:
                    r["status"] = "ACTIVE"
                    count += 1
        if count:
            self._save()
        return count

    def reject_candidates(self, lesson_ids: Optional[List[str]] = None) -> int:
        """Rollback: CANDIDATE → REJECTED. Returns count rejected."""
        count = 0
        for r in self._rules:
            if r.get("status") == "CANDIDATE":
                if lesson_ids is None or r["lesson_id"] in lesson_ids:
                    r["status"] = "REJECTED"
                    count += 1
        if count:
            self._save()
        return count

    def deactivate_poor_performers(self) -> int:
        """ACTIVE → INACTIVE for rules with sustained low success rates."""
        count = 0
        for r in self._rules:
            if r.get("status") == "ACTIVE":
                apps = r.get("applications", 0)
                suc = r.get("successes", 0)
                if apps >= DEPRECATE_MIN_APPS and (suc / apps) < DEPRECATE_SUCCESS_RATE:
                    r["status"] = "INACTIVE"
                    count += 1
        if count:
            self._save()
        return count

    def update_outcome(self, lesson_id: str, success: bool) -> None:
        for r in self._rules:
            if r["lesson_id"] == lesson_id:
                r["applications"] = r.get("applications", 0) + 1
                if success:
                    r["successes"] = r.get("successes", 0) + 1
                self._save()
                return

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve_relevant(self, query_words: set, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return up to top_k ACTIVE rules most relevant to query_words."""
        active = [r for r in self._rules if r.get("status") == "ACTIVE"]
        scored = []
        for r in active:
            pattern_words = self._tokenize(r.get("intent_pattern", ""))
            overlap = len(pattern_words & query_words)
            if overlap > 0:
                scored.append((overlap, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]

    def get_candidates(self) -> List[Dict[str, Any]]:
        return [r for r in self._rules if r.get("status") == "CANDIDATE"]

    def counts(self) -> Dict[str, int]:
        result: Dict[str, int] = {"ACTIVE": 0, "CANDIDATE": 0, "REJECTED": 0, "INACTIVE": 0}
        for r in self._rules:
            s = r.get("status", "UNKNOWN")
            result[s] = result.get(s, 0) + 1
        return result
