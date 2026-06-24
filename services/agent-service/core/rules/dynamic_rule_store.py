"""
dynamic_rule_store.py
---------------------
Persistent rule store that manages the lifecycle of learned SQL rules.
Rules flow: CANDIDATE => ACTIVE | REJECTED => (eventually) INACTIVE

Deduplication uses two-level Jaccard similarity:
  - COVER_THRESHOLD (0.38): blocks adding a rule too similar to any ACTIVE/CANDIDATE rule.
  - TRIED_THRESHOLD (0.65): blocks re-adding a rule very similar to any previously-tried rule
    (any status, including REJECTED) -- enforces convergence.
"""

import json
import os
import time
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

from agent.app.core.config import get_active_knowledge_dir
from agent.services.logger import logger

def get_dynamic_lessons_file(): return get_active_knowledge_dir() / "dynamic_lessons.json"

# Rules are consolidated (LLM-merged) once this threshold is reached.
# After consolidation the count drops significantly, making room for new learning.
MAX_RULES          = 80   # hard upper bound - never exceeded
CONSOLIDATE_AT     = 64   # trigger LLM merge when active+candidate hits this (80% of 80)
COVER_THRESHOLD    = 0.42  # slightly stricter dedup (was 0.38) - avoids over-blocking
TRIED_THRESHOLD    = 0.70  # slightly stricter tried-before guard (was 0.65)
DEPRECATE_MIN_APPS = 3  # evict poor rules faster (was 5) to free slots
DEPRECATE_SUCCESS_RATE = 0.15


class DynamicRuleStore:
    _lock = threading.RLock()

    def __init__(self, path: Optional[Path] = None):
        self.path = path or get_dynamic_lessons_file()
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
        llm_client=None,
    ) -> Optional[str]:
        """
        Add a CANDIDATE rule if not already covered or tried.
        When active+candidate count reaches CONSOLIDATE_AT, triggers an LLM
        consolidation pass to merge/compress semantically similar rules before
        adding more. Returns the new lesson_id, or None if skipped.
        """
        with self._lock:
            if self.is_covered(generic_rule) or self.was_tried_before(generic_rule):
                return None

            active_candidate_count = sum(
                1 for r in self._rules if r.get("status") in ("ACTIVE", "CANDIDATE")
            )

            # -- Consolidation trigger -------------------------------------
            if active_candidate_count >= CONSOLIDATE_AT:
                if llm_client is not None:
                    logger.info(
                        f"[DynamicRuleStore] Threshold {CONSOLIDATE_AT} reached "
                        f"({active_candidate_count} rules). Running LLM consolidation."
                    )
                    self._consolidate(llm_client)
                    # Re-count after consolidation
                    active_candidate_count = sum(
                        1 for r in self._rules if r.get("status") in ("ACTIVE", "CANDIDATE")
                    )
                else:
                    logger.info(
                        "[DynamicRuleStore] Threshold reached but no LLM client available. "
                        "Will consolidate on next add_rule call that provides a client."
                    )

            # Hard cap - safety net only (should rarely trigger after consolidation)
            if active_candidate_count >= MAX_RULES:
                logger.warning(
                    "[DynamicRuleStore] MAX_RULES hard cap reached after consolidation. "
                    "Skipping new rule."
                )
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

    # ------------------------------------------------------------------
    # LLM-based rule consolidation
    # ------------------------------------------------------------------

    _CONSOLIDATION_SYSTEM = """You are a SQL rule deduplication and compression expert.
Your job is to consolidate a list of learned SQL rules into a smaller, higher-quality set.

For each rule you receive, decide:
- KEEP  - unique insight, no overlap with others
- MERGE - semantically equivalent or redundant with another rule (provide merged text)
- DROP  - too vague, incorrect, or superseded by a KEEP rule

Output a JSON array of consolidated rules. Each element:
{
  "rule_title": "<concise title>",
  "generic_rule": "<single most-general statement, <=80 words>",
  "intent_pattern": "<3-6 space-separated keywords that identify when this rule applies>",
  "category": "<original category>"
}

CRITICAL constraints:
- Output ONLY valid JSON. No markdown, no commentary.
- Preserve the most specific and actionable rules.
- Merge rules that express the same fix in different words.
- Drop rules that are obvious SQL basics or already covered by a more specific rule.
- Target: reduce rule count by at least 30% while retaining all unique insights."""

    def _consolidate(self, llm_client) -> None:
        """Call the LLM to merge/compress/deduplicate ACTIVE rules in place."""
        import json as _json

        active_rules = [r for r in self._rules if r.get("status") == "ACTIVE"]
        if len(active_rules) < 10:
            return  # not enough rules to bother

        # Build compact representation to minimize tokens
        compact = [
            {
                "id": r["lesson_id"],
                "title": r.get("rule_title", ""),
                "rule": r.get("generic_rule", ""),
                "pattern": r.get("intent_pattern", ""),
                "category": r.get("category", ""),
            }
            for r in active_rules
        ]

        user_prompt = (
            f"Consolidate these {len(compact)} SQL rules into the minimal set.\n\n"
            + _json.dumps(compact, ensure_ascii=False)
        )

        try:
            raw = llm_client.generate(
                system_prompt=self._CONSOLIDATION_SYSTEM,
                user_prompt=user_prompt,
            )
            # Strip any think tags
            import re as _re
            raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.S).strip()
            # Extract JSON array
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                logger.warning("[DynamicRuleStore] Consolidation: no JSON array in LLM output.")
                return

            consolidated = _json.loads(raw[start:end])
            if not isinstance(consolidated, list) or not consolidated:
                logger.warning("[DynamicRuleStore] Consolidation: empty or invalid result.")
                return

            before = len(active_rules)
            # Mark all old ACTIVE rules as INACTIVE (they're superseded)
            old_ids = {r["lesson_id"] for r in active_rules}
            for r in self._rules:
                if r["lesson_id"] in old_ids:
                    r["status"] = "INACTIVE"

            # Insert the consolidated rules as new ACTIVE rules
            for new_r in consolidated:
                if not new_r.get("generic_rule"):
                    continue
                lid = f"con_{int(time.time() * 1000) % 10_000_000_000}_{hashlib.sha256(new_r['generic_rule'].encode()).hexdigest()[:6]}"
                self._rules.append({
                    "lesson_id":      lid,
                    "rule_title":     new_r.get("rule_title", "consolidated"),
                    "generic_rule":   new_r["generic_rule"],
                    "intent_pattern": new_r.get("intent_pattern", ""),
                    "category":       new_r.get("category", "consolidated"),
                    "source_failures":["consolidation"],
                    "db_name":        "",
                    "status":         "ACTIVE",
                    "applications":   0,
                    "successes":      0,
                })

            self._save()
            after = sum(1 for r in self._rules if r.get("status") == "ACTIVE")
            logger.info(
                f"[DynamicRuleStore] Consolidation complete: {before} -> {after} ACTIVE rules "
                f"({before - after} removed, {len(consolidated)} consolidated rules added)."
            )

        except Exception as e:
            logger.warning(f"[DynamicRuleStore] Consolidation failed (non-fatal): {e}")

    def activate_candidates(self, lesson_ids: Optional[List[str]] = None) -> int:
        """Promote CANDIDATE => ACTIVE. Returns count promoted."""
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
        """Rollback: CANDIDATE => REJECTED. Returns count rejected."""
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
        """ACTIVE => INACTIVE for rules with sustained low success rates."""
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
          1. intent_pattern   (direct overlap -- weighted "3)
          2. rule_title       (overlap -- weighted "2)
          3. first sentence of generic_rule (overlap -- weighted "1)
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
