"""Run 3 DAB queries in parallel with 3 workers and report pass/fail."""
import sys
import time

# Ensure stdout can handle Unicode on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.core.config import DAB_REPO
from agent.app.dab.dab_orchestrator import run_dab_query

# Pick 3 diverse queries (different datasets, different difficulty)
TARGET_IDS = [
    "agnews_q1",
    "bookreview_q1",
    "deps_dev_v1_q1",
]

qs = load_all_queries(str(DAB_REPO))
query_map = {q["instance_id"]: q for q in qs}

selected = []
for iid in TARGET_IDS:
    if iid in query_map:
        selected.append(query_map[iid])
    else:
        # Fallback: pick next available
        for q in qs:
            if q["instance_id"] not in [s["instance_id"] for s in selected]:
                selected.append(q)
                break

print(f"\n{'='*70}")
print(f"Running {len(selected)} DAB queries in parallel (3 workers)")
print(f"{'='*70}")
for q in selected:
    print(f"  [{q['instance_id']}] {q['question'][:80]}")
print(f"{'='*70}\n")

results = {}
start_wall = time.time()

def run_one(q):
    t0 = time.time()
    try:
        result = run_dab_query(q, run_number=0)
        elapsed = time.time() - t0
        return q["instance_id"], result, elapsed
    except Exception as exc:
        elapsed = time.time() - t0
        return q["instance_id"], {"status": "ERROR", "passed": False, "error": str(exc)[:200]}, elapsed

with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(run_one, q): q for q in selected}
    for fut in as_completed(futures):
        iid, result, elapsed = fut.result()
        results[iid] = (result, elapsed)

wall = time.time() - start_wall

print(f"\n{'='*70}")
print(f"RESULTS  (wall clock: {wall:.1f}s)")
print(f"{'='*70}")
passed = 0
for iid in TARGET_IDS:
    if iid not in results:
        continue
    res, t = results[iid]
    status = "PASS" if res.get("passed") else "FAIL"
    verdict = res.get("status", "?")
    answer = str(res.get("agent_answer", ""))[:80]
    err = res.get("error", "")[:120] if res.get("error") else ""
    if res.get("passed"):
        passed += 1
    print(f"\n  [{status}] {iid}")
    print(f"    verdict : {verdict}")
    print(f"    answer  : {answer}")
    print(f"    time    : {t:.1f}s")
    if err:
        print(f"    error   : {err}")

print(f"\n{'='*70}")
print(f"SUMMARY: {passed}/{len(selected)} PASSED")
print(f"{'='*70}\n")
