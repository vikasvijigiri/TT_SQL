"""
DAB run monitor — shows pass@1, pass@k, completed/failed counts, and per-dataset breakdown.
Run in a separate terminal: python monitor_dab.py
Updates every 60 seconds automatically. Ctrl+C to exit.
"""
import sqlite3, time, os, sys
from datetime import datetime

DB_PATH = "backend/agent/agent/results/evaluations/nquire.db"
USERNAME = "vikas"
TOTAL_QUERIES = 54
RUNS_PER_QUERY = 5
TOTAL_SLOTS = TOTAL_QUERIES * RUNS_PER_QUERY  # 270


def query_stats(run_id: str | None = None):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    # Find the active run_id (most recent live run)
    if run_id is None:
        cur.execute(
            """SELECT run_id FROM evaluations
               WHERE username=? AND run_id != 'live'
               ORDER BY timestamp DESC LIMIT 1""",
            (USERNAME,),
        )
        row = cur.fetchone()
        run_id = row[0] if row else "live"

    # Also include live records (pre-archive stubs)
    cur.execute(
        """SELECT dataset, query_id, run_suffix, passed, elapsed_s
           FROM evaluations
           WHERE username=? AND (run_id=? OR run_id='live')
           ORDER BY dataset, query_id, run_suffix""",
        (USERNAME, run_id),
    )
    rows = cur.fetchall()
    db.close()
    return rows, run_id


def compute_metrics(rows):
    from collections import defaultdict

    # Group by (dataset, query_id) → list of passed values
    groups = defaultdict(list)
    for dataset, query_id, run_suffix, passed, elapsed_s in rows:
        groups[(dataset, query_id)].append(passed)

    total_slots = sum(len(v) for v in groups.values())
    completed_slots = sum(1 for v in groups.values() for p in v if p is not None)
    passed_slots = sum(1 for v in groups.values() for p in v if p == 1)
    failed_slots = sum(1 for v in groups.values() for p in v if p == 0)
    pending_slots = total_slots - completed_slots

    # pass@1: fraction of queries where at least 1 run passed
    pass_at_1_queries = sum(1 for v in groups.values() if any(p == 1 for p in v))
    queries_with_all_runs = sum(1 for v in groups.values() if sum(1 for p in v if p is not None) == RUNS_PER_QUERY)

    # pass@k (all k runs passed)
    pass_at_k_queries = sum(
        1 for v in groups.values()
        if len(v) >= RUNS_PER_QUERY and all(p == 1 for p in v)
    )

    return {
        "run_id": None,
        "total_slots": total_slots,
        "completed_slots": completed_slots,
        "passed_slots": passed_slots,
        "failed_slots": failed_slots,
        "pending_slots": pending_slots,
        "unique_queries": len(groups),
        "pass_at_1_queries": pass_at_1_queries,
        "pass_at_k_queries": pass_at_k_queries,
        "queries_with_all_runs": queries_with_all_runs,
        "groups": groups,
    }


def print_status(m, run_id, iteration=None):
    os.system("cls" if os.name == "nt" else "clear")
    now = datetime.now().strftime("%H:%M:%S")
    iter_str = f" [{iteration}]" if iteration else ""
    print(f"{'='*60}")
    print(f"  DAB Monitor  {now}{iter_str}  run_id={run_id}")
    print(f"{'='*60}")

    pct_done = 100 * m["completed_slots"] / TOTAL_SLOTS if TOTAL_SLOTS else 0
    bar_len = 40
    filled = int(bar_len * m["completed_slots"] / TOTAL_SLOTS) if TOTAL_SLOTS else 0
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"\nProgress: [{bar}] {m['completed_slots']}/{TOTAL_SLOTS} slots ({pct_done:.1f}%)")
    print(f"  Pending : {m['pending_slots']}")
    print(f"  Passed  : {m['passed_slots']}")
    print(f"  Failed  : {m['failed_slots']}")

    print(f"\n{'─'*60}")
    print(f"{'Metric':<35} {'Value':>10}")
    print(f"{'─'*60}")
    print(f"{'Unique queries seen':<35} {m['unique_queries']:>10} / {TOTAL_QUERIES}")
    print(f"{'Queries with all 5 runs done':<35} {m['queries_with_all_runs']:>10} / {TOTAL_QUERIES}")

    total_completed_q = m["unique_queries"]
    p1_pct = 100 * m["pass_at_1_queries"] / total_completed_q if total_completed_q else 0
    pk_pct = 100 * m["pass_at_k_queries"] / total_completed_q if total_completed_q else 0

    print(f"{'pass@1 (>=1 run passed)':<35} {m['pass_at_1_queries']:>10} ({p1_pct:.1f}%)")
    print(f"{'pass@k (all 5 runs passed)':<35} {m['pass_at_k_queries']:>10} ({pk_pct:.1f}%)")
    print(f"{'─'*60}")

    # Per-dataset breakdown
    from collections import defaultdict
    ds_stats = defaultdict(lambda: {"slots": 0, "passed": 0, "failed": 0, "queries": set()})
    for (dataset, query_id), vals in m["groups"].items():
        ds_stats[dataset]["queries"].add(query_id)
        for p in vals:
            ds_stats[dataset]["slots"] += 1
            if p == 1:
                ds_stats[dataset]["passed"] += 1
            elif p == 0:
                ds_stats[dataset]["failed"] += 1

    print(f"\n{'Dataset':<20} {'Q':>3} {'Slots':>6} {'Pass':>5} {'Fail':>5} {'Pass%':>6}")
    print(f"{'─'*55}")
    for ds in sorted(ds_stats):
        s = ds_stats[ds]
        q_count = len(s["queries"])
        total_s = s["slots"]
        pass_s = s["passed"]
        fail_s = s["failed"]
        pct = 100 * pass_s / total_s if total_s else 0
        print(f"{ds:<20} {q_count:>3} {total_s:>6} {pass_s:>5} {fail_s:>5} {pct:>5.0f}%")

    if m["completed_slots"] >= TOTAL_SLOTS:
        print(f"\n{'='*60}")
        print(f"  BATCH COMPLETE!")
        p1_final = 100 * m['pass_at_1_queries'] / TOTAL_QUERIES
        pk_final = 100 * m['pass_at_k_queries'] / TOTAL_QUERIES
        print(f"  Final pass@1 : {m['pass_at_1_queries']}/{TOTAL_QUERIES} = {p1_final:.1f}%")
        print(f"  Final pass@k : {m['pass_at_k_queries']}/{TOTAL_QUERIES} = {pk_final:.1f}%")
        print(f"{'='*60}")
    else:
        remaining = TOTAL_SLOTS - m["completed_slots"]
        print(f"\n  {remaining} slots remaining. Refreshing every 60s. Ctrl+C to exit.")


def main():
    run_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    iteration = 0
    while True:
        try:
            rows, run_id = query_stats(run_id_arg)
            m = compute_metrics(rows)
            iteration += 1
            print_status(m, run_id, iteration)

            if m["completed_slots"] >= TOTAL_SLOTS:
                break
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
