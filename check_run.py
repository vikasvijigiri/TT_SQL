"""
One-shot DAB run status check using official DAB metric definitions.

Official DAB aggregation (common_scaffold/validate/pass_k.py):
  pass@1 per query  = c / n  (correct runs / total runs)
  pass@1 per dataset = mean of per-query pass@1
  pass@1 leaderboard = mean across datasets  (equal weight per dataset)

  pass@k per query  = 1 if any run passed else 0  (for k >= n)
  pass@k leaderboard = mean across datasets of (fraction of queries with any pass)

Usage: python check_run.py [run_id]
"""
import sqlite3, sys
from collections import defaultdict
from math import comb

DB_PATH = "backend/agent/agent/results/evaluations/nquire.db"
USERNAME = "vikas"
TOTAL_Q = 54
RUNS_PER_Q = 5
TOTAL_SLOTS = 270


def pass_at_k_unbiased(n, c, k):
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


run_id_arg = sys.argv[1] if len(sys.argv) > 1 else None

db = sqlite3.connect(DB_PATH)
cur = db.cursor()

if run_id_arg is None:
    cur.execute(
        "SELECT run_id FROM evaluations WHERE username=? AND run_id != 'live' ORDER BY timestamp DESC LIMIT 1",
        (USERNAME,),
    )
    row = cur.fetchone()
    run_id = row[0] if row else "live"
else:
    run_id = run_id_arg

cur.execute(
    """SELECT dataset, query_id, run_suffix, passed, elapsed_s
       FROM evaluations WHERE username=? AND (run_id=? OR run_id='live')
       ORDER BY dataset, query_id, run_suffix""",
    (USERNAME, run_id),
)
rows = cur.fetchall()
db.close()

# Group by (dataset, query_id) -> list of passed values
groups = defaultdict(list)
for dataset, query_id, run_sfx, passed, elapsed_s in rows:
    groups[(dataset, query_id)].append(passed)

# Exclude _run99 audit slots
groups = {k: [p for p in v if p is not None or True] for k, v in groups.items()}

total_slots = sum(len(v) for v in groups.values())
done_slots = sum(1 for v in groups.values() for p in v if p is not None)
passed_slots = sum(1 for v in groups.values() for p in v if p == 1)
failed_slots = sum(1 for v in groups.values() for p in v if p == 0)
pending_slots = total_slots - done_slots

# ── Per-dataset stats ────────────────────────────────────────────────────────
ds_groups = defaultdict(dict)  # dataset -> {query_id -> [passed, ...]}
for (dataset, qid), vals in groups.items():
    ds_groups[dataset][qid] = vals

ds_stats = {}
for dataset, qdict in ds_groups.items():
    q_pass1_scores = []
    q_passk_scores = []
    for qid, vals in qdict.items():
        completed = [p for p in vals if p is not None]
        if not completed:
            continue
        n, c = len(completed), sum(completed)
        q_pass1_scores.append(pass_at_k_unbiased(n, c, 1))   # = c/n
        q_passk_scores.append(pass_at_k_unbiased(n, c, n))   # 1 if any pass else 0
    ds_stats[dataset] = {
        "q_seen": len(qdict),
        "q_evaluated": len(q_pass1_scores),
        "slots": sum(len(v) for v in qdict.values()),
        "passed": sum(p for v in qdict.values() for p in v if p == 1),
        "failed": sum(1 for v in qdict.values() for p in v if p == 0),
        "pass_at_1": sum(q_pass1_scores) / len(q_pass1_scores) if q_pass1_scores else None,
        "pass_at_k": sum(q_passk_scores) / len(q_passk_scores) if q_passk_scores else None,
    }

# ── Leaderboard metrics (mean across datasets, equal weight per dataset) ────
ds_with_evals = [v for v in ds_stats.values() if v["pass_at_1"] is not None]
if ds_with_evals:
    leaderboard_pass1 = sum(v["pass_at_1"] for v in ds_with_evals) / len(ds_with_evals)
    leaderboard_passk = sum(v["pass_at_k"] for v in ds_with_evals) / len(ds_with_evals)
else:
    leaderboard_pass1 = 0.0
    leaderboard_passk = 0.0

datasets_seen = len(ds_stats)
queries_seen = len(groups)

print("=" * 60)
print(f"Run       : {run_id}")
print(f"Progress  : {done_slots}/{TOTAL_SLOTS} slots ({100*done_slots/TOTAL_SLOTS:.1f}%)")
print(f"  Passed  : {passed_slots}   Failed: {failed_slots}   Pending: {pending_slots}")
print(f"Queries   : {queries_seen}/{TOTAL_Q}  |  Datasets: {datasets_seen}/12")
print()
print(f"{'OFFICIAL DAB LEADERBOARD METRICS':^60}")
print(f"{'(mean of per-dataset scores, equal weight per dataset)':^60}")
print(f"  pass@1  : {leaderboard_pass1*100:>6.2f}%  ({leaderboard_pass1:.4f})")
print(f"  pass@k  : {leaderboard_passk*100:>6.2f}%  ({leaderboard_passk:.4f})")
print()

if total_slots == 0:
    print("No data yet — queries are still queued, check back in 2+ minutes.")
    sys.exit(0)

print(f"{'Dataset':<22} {'Q':>3} {'Done':>5} {'Pass':>5} {'Fail':>5} {'pass@1':>7} {'pass@k':>7}")
print("-" * 58)
for name in sorted(ds_stats):
    s = ds_stats[name]
    p1 = f"{s['pass_at_1']*100:.0f}%" if s["pass_at_1"] is not None else "  --"
    pk = f"{s['pass_at_k']*100:.0f}%" if s["pass_at_k"] is not None else "  --"
    print(f"{name:<22} {s['q_seen']:>3} {s['slots']:>5} {s['passed']:>5} {s['failed']:>5} {p1:>7} {pk:>7}")
print("=" * 60)
