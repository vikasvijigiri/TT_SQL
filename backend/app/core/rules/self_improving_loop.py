"""
self_improving_loop.py
----------------------
Autonomous self-improvement pipeline for the DAB benchmark.

Each daily run performs up to MAX_ROUNDS of targeted improvement cycles:
  1. Identify all currently-failing queries.
  2. Extract generic SQL rules from each failure via the LLM.
  3. Promote new rules to ACTIVE in dynamic_lessons.json.
  4. Re-run the failed queries (they now benefit from the new rules).
  5. Compare pass counts: if improved → keep rules; else → rollback to REJECTED.
  6. Detect saturation: stop early if no new rules can be extracted, or if
     MAX_NO_IMPROVE consecutive rounds produced no improvement.

Progress and history are written atomically to improvement_log.json so the
UI can display them without any server restart.
"""
import json
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import MEMORY_DIR, DAB_REPO
from backend.app.utils.logger import logger

# ------------------------------------------------------------------ constants
MAX_ROUNDS = 3
MIN_IMPROVEMENT = 1
MAX_NO_IMPROVE = 2
MAX_FAILURES_PER_ROUND = 20   # max failures to extract rules from per round
MAX_RERUN_PER_ROUND = 15      # max queries to re-run per round

IMPROVEMENT_LOG_FILE = MEMORY_DIR / "improvement_log.json"


class SelfImprovingLoop:
    """
    Stateless across days — each daily invocation re-reads the log from disk.
    """

    def __init__(self, dab_repo: Optional[str] = None, llm_client=None):
        self.dab_repo = str(dab_repo or DAB_REPO)
        self._llm = llm_client
        self._log = self._load_log()

    # ---------------------------------------------------------- log I/O

    def _load_log(self) -> Dict[str, Any]:
        if IMPROVEMENT_LOG_FILE.exists():
            try:
                with open(IMPROVEMENT_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"SelfImprovingLoop: failed to load log: {e}")
        return {
            "runs": [],
            "total_rounds": 0,
            "last_run": None,
            "saturated": False,
            "baseline_pass_rate": None,
        }

    def _save_log(self) -> None:
        IMPROVEMENT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = IMPROVEMENT_LOG_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._log, f, indent=2, ensure_ascii=False)
        os.replace(tmp, IMPROVEMENT_LOG_FILE)

    # ---------------------------------------------------------- helpers

    def _count_passed(self) -> Tuple[int, int]:
        """Return (passed, total) from saved eval results (no LLM calls)."""
        from backend.app.dab.dab_evaluator import load_eval_result
        from backend.app.dab.benchmark_loader import load_all_queries

        queries = load_all_queries(self.dab_repo)
        total = len(queries)
        passed = sum(
            1
            for q in queries
            if (ev := load_eval_result(q["dataset"], q["query_id"])) and ev.get("passed")
        )
        return passed, total

    def _get_failures(self) -> List[Dict[str, Any]]:
        """Return all query dicts that have a saved FAIL eval result."""
        from backend.app.dab.dab_evaluator import load_eval_result
        from backend.app.dab.benchmark_loader import load_all_queries

        queries = load_all_queries(self.dab_repo)
        return [
            {"query": q, "eval": ev}
            for q in queries
            if (ev := load_eval_result(q["dataset"], q["query_id"])) and not ev.get("passed")
        ]

    def _prioritize_failures(
        self, failures: List[Dict[str, Any]], new_rule_patterns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Sort failures by keyword overlap with newly extracted rules so that
        the most-likely-to-benefit queries are re-run first.
        """
        all_pattern_words: set = set()
        for p in new_rule_patterns:
            all_pattern_words.update(p.lower().split())

        def score(f: Dict[str, Any]) -> int:
            q = f["query"]
            q_words = set(q.get("question", "").lower().split())
            return len(q_words & all_pattern_words)

        return sorted(failures, key=score, reverse=True)

    # ---------------------------------------------------------- main entry

    def run_daily(self) -> Dict[str, Any]:
        """
        Execute up to MAX_ROUNDS improvement cycles for today.
        Safe to call multiple times: respects the daily run cap.
        """
        from backend.app.core.rules.dynamic_rule_store import DynamicRuleStore
        from backend.app.core.rules.rule_extractor_agent import extract_rules_from_failure
        from backend.app.dab.dab_orchestrator import run_dab_query
        from backend.app.utils.llm import LLMClient

        today = str(date.today())
        today_runs = [r for r in self._log.get("runs", []) if r.get("date") == today]

        if len(today_runs) >= MAX_ROUNDS:
            return {
                "status": "limit_reached",
                "message": f"Already completed {MAX_ROUNDS} rounds today ({today}).",
            }

        if self._log.get("saturated"):
            return {
                "status": "saturated",
                "message": "Pipeline has reached saturation — no further improvement expected.",
            }

        if self._llm is None:
            self._llm = LLMClient()

        store = DynamicRuleStore()
        rounds_left = MAX_ROUNDS - len(today_runs)
        round_results: List[Dict[str, Any]] = []
        no_improve_streak = 0

        passes_before, total = self._count_passed()

        # Record baseline on very first ever run
        if self._log.get("baseline_pass_rate") is None:
            self._log["baseline_pass_rate"] = round(100 * passes_before / total, 1) if total else 0

        for round_num in range(1, rounds_left + 1):
            t_start = time.time()
            logger.info(
                f"[SelfImprove] ─── Round {round_num}/{rounds_left} ─── "
                f"baseline {passes_before}/{total} passed"
            )

            # ── Step 1: collect current failures ──────────────────────────
            failures = self._get_failures()
            if not failures:
                logger.info("[SelfImprove] No failures remaining — perfect score achieved!")
                round_results.append({
                    "round": round_num, "date": today, "status": "perfect",
                    "passes_before": passes_before, "passes_after": passes_before,
                    "delta": 0, "total": total, "new_rules_added": 0, "elapsed_s": 0,
                })
                break

            # ── Step 2: extract rules from failures ───────────────────────
            new_candidate_ids: List[str] = []
            new_rule_patterns: List[str] = []

            for f in failures[:MAX_FAILURES_PER_ROUND]:
                q, ev = f["query"], f["eval"]
                try:
                    rules = extract_rules_from_failure(
                        llm=self._llm,
                        question=q.get("question", ""),
                        sql_generated=ev.get("agent_answer_snippet", ""),
                        error_or_mismatch=ev.get("reason", ""),
                        ground_truth_hint=str(ev.get("ground_truth", ""))[:200],
                        dataset=q.get("dataset", ""),
                    )
                    for rule in rules:
                        lid = store.add_rule(
                            rule_title=rule["rule_title"],
                            generic_rule=rule["generic_rule"],
                            intent_pattern=rule["intent_pattern"],
                            category=rule["category"],
                            source_failure=f"{q['dataset']}_q{q['query_id']}",
                            db_name=q.get("dataset", "").upper(),
                        )
                        if lid:
                            new_candidate_ids.append(lid)
                            new_rule_patterns.append(rule["intent_pattern"])
                except Exception as e:
                    logger.warning(
                        f"[SelfImprove] Rule extraction failed for "
                        f"{q.get('instance_id', '?')}: {e}"
                    )

            if not new_candidate_ids:
                logger.info(
                    "[SelfImprove] No new rules extracted "
                    "(all failures already covered or MAX_RULES reached)."
                )
                no_improve_streak += 1
                round_results.append({
                    "round": round_num, "date": today, "status": "no_new_rules",
                    "passes_before": passes_before, "passes_after": passes_before,
                    "delta": 0, "total": total, "new_rules_added": 0,
                    "elapsed_s": round(time.time() - t_start, 1),
                })
                if no_improve_streak >= MAX_NO_IMPROVE:
                    self._log["saturated"] = True
                    break
                continue

            # ── Step 3: activate candidates ───────────────────────────────
            activated = store.activate_candidates(new_candidate_ids)
            logger.info(f"[SelfImprove] Activated {activated} rules → re-running failures")

            # ── Step 4: re-run the most likely to benefit ─────────────────
            prioritized = self._prioritize_failures(failures, new_rule_patterns)
            rerun_targets = prioritized[:MAX_RERUN_PER_ROUND]

            for f in rerun_targets:
                q = f["query"]
                try:
                    result = run_dab_query(q, llm_client=self._llm)
                    status_str = result.get("status", "unknown")
                    logger.info(
                        f"[SelfImprove] Re-run {q.get('instance_id','?')}: {status_str}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[SelfImprove] Re-run failed for "
                        f"{q.get('instance_id', '?')}: {e}"
                    )

            # ── Step 5: compare ───────────────────────────────────────────
            passes_after, _ = self._count_passed()
            delta = passes_after - passes_before
            elapsed = round(time.time() - t_start, 1)

            if delta >= MIN_IMPROVEMENT:
                status = "improved"
                logger.info(
                    f"[SelfImprove] Round {round_num}: +{delta} passes. "
                    f"Keeping {activated} rules ACTIVE."
                )
                store.deactivate_poor_performers()
                no_improve_streak = 0
                passes_before = passes_after
            else:
                status = "no_improvement"
                logger.info(
                    f"[SelfImprove] Round {round_num}: delta={delta}. "
                    f"Rolling back {len(new_candidate_ids)} candidates."
                )
                store.reject_candidates(new_candidate_ids)
                no_improve_streak += 1

            round_results.append({
                "round": round_num,
                "date": today,
                "status": status,
                "passes_before": passes_after - delta,
                "passes_after": passes_after,
                "delta": delta,
                "total": total,
                "new_rules_added": activated if delta >= MIN_IMPROVEMENT else 0,
                "elapsed_s": elapsed,
                "pass_rate": round(100 * passes_after / total, 1) if total else 0,
            })

            if no_improve_streak >= MAX_NO_IMPROVE:
                self._log["saturated"] = True
                logger.info("[SelfImprove] Saturation detected — stopping.")
                break

        # ── Persist run to log ─────────────────────────────────────────────
        final_passes = passes_before
        run_entry = {
            "date": today,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "rounds": round_results,
            "final_passes": final_passes,
            "total": total,
            "pass_rate": round(100 * final_passes / total, 1) if total else 0,
        }
        self._log.setdefault("runs", []).append(run_entry)
        self._log["total_rounds"] = self._log.get("total_rounds", 0) + len(round_results)
        self._log["last_run"] = run_entry["timestamp"]
        self._save_log()

        rule_counts = store.counts()
        return {
            "status": "completed",
            "run": run_entry,
            "rule_counts": rule_counts,
            "saturated": self._log.get("saturated", False),
        }
