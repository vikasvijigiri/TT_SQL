"""
pipeline_smart_scorer.py
------------------------
Computes a per-run "Smartness Score" (0-100) from the evolution snapshot
that the orchestrator records for every query execution.

Score formula
-------------
  start = 100

  PENALTIES (subtracted):
    Each failed attempt (success=False)       : -8 per attempt
    First attempt failed                      : -5 (extra on top of -8)
    Stagnation (same SQL hash repeated)       : -15 (once per stagnation event)
    Error plateau (3+ same error category)    : -20 (once per plateau event)
    Timeout keyword in error                  : -25
    Hallucination category hit                : -10 (per attempt, on top of -8)
    Zero rows on a successful execution       : -5 (per zero-row attempt)
    FAILED final verdict                      : -30
    PARTIAL final verdict                     : -10

  BONUSES (added):
    SOLVED on first attempt                   : +10
    SOLVED after self-correction (attempt > 1): +5
    Zero hallucinations across all attempts   : +5
    All attempts produced new SQL (no stagnation): +5

  Final score = clamp(raw, 0, 100)

History
-------
Every computed score is appended to MEMORY_DIR/smartness_history.json.
The cumulative weighted average (recent runs weighted higher) is the global
pipeline KPI - it must trend upward over time.
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Optional
from pathlib import Path


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------
_PENALTY_FAILED_ATTEMPT    = 8
_PENALTY_FIRST_FAIL        = 5
_PENALTY_STAGNATION        = 15
_PENALTY_ERROR_PLATEAU     = 20
_PENALTY_TIMEOUT           = 25
_PENALTY_HALLUCINATION_HIT = 10
_PENALTY_ZERO_ROWS         = 5
_PENALTY_FINAL_FAILED      = 30
_PENALTY_FINAL_PARTIAL     = 10

_BONUS_SOLVED_FIRST        = 10
_BONUS_SOLVED_CORRECTED    = 5
_BONUS_NO_HALLUCINATIONS   = 5
_BONUS_NO_STAGNATION       = 5


class PipelineSmartScorer:
    """Computes a smartness score for a single pipeline run from its evolution list."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def score(
        evolution: list[dict],
        final_verdict: str,
        termination_reason: str,
    ) -> float:
        """
        Compute smartness score (0.0-100.0) from evolution snapshot.

        Parameters
        ----------
        evolution          : list of per-attempt dicts (from orchestrator)
        final_verdict      : 'SOLVED' | 'PARTIAL' | 'FAILED'
        termination_reason : e.g. 'VALIDATION_PASSED', 'STAGNATION:...', etc.
        """
        if not evolution:
            # No attempts recorded = total failure
            return 0.0

        raw = 100.0
        n = len(evolution)
        sql_hashes = [e.get("sql_hash", "") for e in evolution]
        error_cats = [e.get("error_category", "") for e in evolution]

        # -- Per-attempt penalties --------------------------------------
        for i, e in enumerate(evolution):
            success = e.get("success", False)
            is_valid = e.get("is_valid", False)
            row_count = e.get("row_count", 0)
            err_cat = e.get("error_category", "")
            feedback = (e.get("validation_feedback") or "").lower()

            if not is_valid:
                # Failed attempt
                raw -= _PENALTY_FAILED_ATTEMPT
                if i == 0:
                    raw -= _PENALTY_FIRST_FAIL

                # Hallucination hit
                if err_cat == "hallucination":
                    raw -= _PENALTY_HALLUCINATION_HIT

                # Timeout
                if "timeout" in feedback or "timeout" in err_cat.lower():
                    raw -= _PENALTY_TIMEOUT

            elif success and row_count == 0:
                # Executed OK but returned nothing
                raw -= _PENALTY_ZERO_ROWS

        # -- Stagnation penalty (consecutive same SQL hash) -------------
        stagnation_count = 0
        for i in range(1, n):
            if sql_hashes[i] and sql_hashes[i] == sql_hashes[i - 1]:
                stagnation_count += 1
        if stagnation_count > 0:
            raw -= _PENALTY_STAGNATION * min(stagnation_count, 2)

        # -- Error plateau penalty (3+ same category in a row) ---------
        if n >= 3:
            for i in range(n - 2):
                window = error_cats[i : i + 3]
                if (
                    len(set(window)) == 1
                    and window[0] not in ("none", "")
                    and not any(evolution[i + j].get("is_valid") for j in range(3))
                ):
                    raw -= _PENALTY_ERROR_PLATEAU
                    break  # count once per run

        # -- Termination-reason-based penalty --------------------------
        tr_lower = termination_reason.lower()
        if "stagnation" in tr_lower:
            raw -= _PENALTY_STAGNATION
        if "plateau" in tr_lower:
            raw -= _PENALTY_ERROR_PLATEAU

        # -- Final verdict penalty --------------------------------------
        if final_verdict == "FAILED":
            raw -= _PENALTY_FINAL_FAILED
        elif final_verdict == "PARTIAL":
            raw -= _PENALTY_FINAL_PARTIAL

        # -- Bonuses ---------------------------------------------------
        first = evolution[0]
        if final_verdict == "SOLVED":
            if first.get("is_valid"):
                raw += _BONUS_SOLVED_FIRST
            else:
                raw += _BONUS_SOLVED_CORRECTED

        has_hallucination = any(e.get("error_category") == "hallucination" for e in evolution)
        if not has_hallucination:
            raw += _BONUS_NO_HALLUCINATIONS

        if stagnation_count == 0:
            raw += _BONUS_NO_STAGNATION

        return round(float(max(0.0, min(100.0, raw))), 2)

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------

    @staticmethod
    def record_to_history(
        instance_id: str,
        smartness_score: float,
        final_verdict: str,
        total_attempts: int,
        evolution_score: float,
        memory_dir: Path,
    ) -> float:
        """
        Append entry to smartness_history.json and return the new cumulative
        weighted average (the global pipeline KPI).

        Recent entries get linearly higher weight so the KPI reflects
        improvement over time.
        """
        history_path = memory_dir / "smartness_history.json"

        # Load existing history
        history: list[dict] = []
        if history_path.exists():
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        # Compute weighted cumulative average (linear weight: newest = highest)
        all_scores = [h.get("smartness_score", 0.0) for h in history] + [smartness_score]
        n = len(all_scores)
        weights = list(range(1, n + 1))  # 1, 2, 3, ..., n
        weighted_avg = sum(s * w for s, w in zip(all_scores, weights)) / sum(weights)
        cumulative_avg = round(weighted_avg, 2)

        # Trend vs last entry
        prev_avg = history[-1].get("cumulative_avg", cumulative_avg) if history else cumulative_avg
        trend = "UP" if cumulative_avg >= prev_avg else "DOWN"

        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "instance_id": instance_id,
            "smartness_score": smartness_score,
            "final_verdict": final_verdict,
            "total_attempts": total_attempts,
            "evolution_score": round(evolution_score, 4),
            "cumulative_avg": cumulative_avg,
            "trend": trend,
        }

        history.append(entry)

        # Save atomically
        tmp = history_path.with_suffix(".tmp")
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp, history_path)
        except Exception:
            pass

        return cumulative_avg

    @staticmethod
    def grade_label(score: float) -> str:
        """Return human-readable grade label for a smartness score."""
        if score >= 90:
            return "EXCEPTIONAL"
        if score >= 70:
            return "GOOD"
        if score >= 50:
            return "ADEQUATE"
        if score >= 30:
            return "POOR"
        return "FAILED"
