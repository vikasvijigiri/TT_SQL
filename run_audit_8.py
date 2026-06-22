"""8 heavy DAB queries in parallel with 8 workers — performance audit."""
import sys, os, time, pathlib, concurrent.futures, threading

os.environ["PYTHONUNBUFFERED"] = "1"
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, "backend/agent")

from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.dab.dab_orchestrator import run_dab_query
from agent.app.utils.llm import LLMClient

DAB_PATH = pathlib.Path("c:/Users/VikasVijigiri/Documents/DataAgentBench")

PICKS = [
    ("crmarenapro",      "5"),
    ("crmarenapro",      "10"),
    ("github_repos",     "4"),
    ("deps_dev_v1",      "1"),
    ("music_brainz_20k", "3"),
    ("pancancer_atlas",  "2"),
    ("yelp",             "5"),
    ("stockmarket",      "4"),
]

queries = load_all_queries(DAB_PATH)
selected = []
for ds, qid in PICKS:
    m = next((q for q in queries if q["dataset"] == ds and q["query_id"] == qid), None)
    if m:
        selected.append(m)
    else:
        print(f"[WARN] Not found: {ds} q{qid}")

print_lock = threading.Lock()

def run_one(q):
    ds, qid = q["dataset"], q["query_id"]
    tag = f"[{ds}/q{qid}]"
    with print_lock:
        print(f"{tag} START  Q: {q['question'][:80]}")
    llm = LLMClient(temperature=0.0)
    t0 = time.time()
    result = run_dab_query(q, llm_client=llm, run_number=99)
    elapsed = time.time() - t0
    with print_lock:
        passed = result["passed"]
        status = result["status"]
        ans = str(result.get("agent_answer", ""))[:100].encode("ascii", errors="replace").decode("ascii")
        print(f"{tag} DONE  {elapsed:.1f}s  passed={passed}  status={status}  ans={ans!r}")
    return {"ds": ds, "qid": qid, "elapsed": elapsed, "result": result}

print(f"\nLaunching {len(selected)} queries across {len(selected)} parallel workers...\n")
wall_start = time.time()

outcomes = []
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(run_one, q): q for q in selected}
    for f in concurrent.futures.as_completed(futures):
        try:
            outcomes.append(f.result())
        except Exception as e:
            q = futures[f]
            outcomes.append({
                "ds": q["dataset"], "qid": q["query_id"], "elapsed": 0,
                "result": {"passed": False, "status": "exception", "error": str(e), "agent_answer": ""}
            })

wall_elapsed = time.time() - wall_start
print(f"\nAll done in {wall_elapsed:.1f}s wall time.\n")
print("=" * 72)
print("SUMMARY")
print("=" * 72)
passed_count = sum(1 for o in outcomes if o["result"]["passed"])
for o in sorted(outcomes, key=lambda x: x["elapsed"]):
    r = o["result"]
    mark = "PASS" if r["passed"] else "FAIL"
    print(f"  [{mark}] [{o['ds']}/q{o['qid']}]  {o['elapsed']:.1f}s  status={r['status']}")
    ans = str(r.get("agent_answer",""))[:120].encode("ascii","replace").decode("ascii")
    if ans:
        print(f"         answer: {ans}")
    if r.get("error"):
        err = str(r["error"])[:150].encode("ascii","replace").decode("ascii")
        print(f"         error:  {err}")

print("=" * 72)
print(f"PASS RATE: {passed_count}/{len(outcomes)}  ({100*passed_count/len(outcomes):.0f}%)")
print(f"WALL TIME: {wall_elapsed:.1f}s")
