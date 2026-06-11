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
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.app.core.config import MEMORY_DIR
from backend.app.utils.logger import logger

DYNAMIC_LESSONS_FILE = MEMORY_DIR / "dynamic_lessons.json"

MAX_RULES = 120  # raised: was 60, filled up causing silent drops
COVER_THRESHOLD = 0.42  # slightly stricter dedup (was 0.38) — avoids over-blocking
TRIED_THRESHOLD = 0.70  # slightly stricter tried-before guard (was 0.65)
DEPRECATE_MIN_APPS = 3  # evict poor rules faster (was 5) to free slots
DEPRECATE_SUCCESS_RATE = 0.15


class DynamicRuleStore:
    _lock = threading.RLock()

    def __init__(self, path: Path = DYNAMIC_LESSONS_FILE):
        self.path = path
        self._rules: List[Dict[str, Any]] = []
        with self._lock:
            self._load()

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            for r in self._rules:
                if r.get("status") in ("ACTIVE", "CANDIDATE") and (
                    self._jaccard(generic_rule, r.get("generic_rule", ""))
                    >= COVER_THRESHOLD
                ):
                    return True
            return False

    def was_tried_before(self, generic_rule: str) -> bool:
        """True if a highly-similar rule has been tried before (any status)."""
        with self._lock:
            for r in self._rules:
                if (
                    self._jaccard(generic_rule, r.get("generic_rule", ""))
                    >= TRIED_THRESHOLD
                ):
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
        with self._lock:
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
            logger.info(
                f"DynamicRuleStore: added CANDIDATE '{rule_title}' [{lesson_id}]"
            )
            return lesson_id

    def activate_candidates(self, lesson_ids: Optional[List[str]] = None) -> int:
        """Promote CANDIDATE → ACTIVE. Returns count promoted."""
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            count = 0
            for r in self._rules:
                if r.get("status") == "ACTIVE":
                    apps = r.get("applications", 0)
                    suc = r.get("successes", 0)
                    if (
                        apps >= DEPRECATE_MIN_APPS
                        and (suc / apps) < DEPRECATE_SUCCESS_RATE
                    ):
                        r["status"] = "INACTIVE"
                        count += 1
            if count:
                self._save()
            return count

    def update_outcome(self, lesson_id: str, success: bool) -> None:
        with self._lock:
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

    def retrieve_relevant(
        self, query_words: set, top_k: int = 8, db_name: str = ""
    ) -> List[Dict[str, Any]]:
        """Return up to top_k ACTIVE rules most relevant to query_words.

        Scoring uses three fields so that rules with sparse intent_pattern still match:
          1. intent_pattern   (direct overlap — weighted ×3)
          2. rule_title       (overlap — weighted ×2)
          3. first sentence of generic_rule (overlap — weighted ×1)
        """
        with self._lock:
            active = [r for r in self._rules if r.get("status") == "ACTIVE"]
            scored = []
            for r in active:
                pattern_words = self._tokenize(r.get("intent_pattern", ""))
                title_words = self._tokenize(r.get("rule_title", ""))
                # Only first sentence of generic_rule to avoid noise
                gr_first = r.get("generic_rule", "").split(".")[0]
                gr_words = self._tokenize(gr_first)

                score = (
                    3 * len(pattern_words & query_words)
                    + 2 * len(title_words & query_words)
                    + 1 * len(gr_words & query_words)
                )
                if db_name:
                    clean_db = db_name.upper().replace("DAB_", "")
                    clean_rule_db = r.get("db_name", "").upper().replace("DAB_", "")
                    if clean_db == clean_rule_db and clean_db:
                        score += 15
                if score > 0:
                    scored.append((score, r))
            scored.sort(key=lambda x: -x[0])
            return [r for _, r in scored[:top_k]]

    def get_candidates(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r for r in self._rules if r.get("status") == "CANDIDATE"]

    def counts(self) -> Dict[str, int]:
        with self._lock:
            result: Dict[str, int] = {
                "ACTIVE": 0,
                "CANDIDATE": 0,
                "REJECTED": 0,
                "INACTIVE": 0,
            }
            for r in self._rules:
                s = r.get("status", "UNKNOWN")
                result[s] = result.get(s, 0) + 1
            return result
