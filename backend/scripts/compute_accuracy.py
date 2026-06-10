import os, json
from math import comb

results_dir = "backend/results/dab"

def pass_at_k(n, c, k):
    if c == 0: return 0.0
    if n - c < k: return 1.0
    return 1.0 - comb(n-c, k) / comb(n, k)

dataset_scores = {}
total_queries = 0
skipped = 0

for ds in sorted(os.listdir(results_dir)):
    ds_path = os.path.join(results_dir, ds)
    if not os.path.isdir(ds_path):
        continue

    run0_files = [f for f in os.listdir(ds_path) if f.endswith("_eval.json") and "_run" not in f]
    ds_pass1 = []
    ds_pass5 = []

    for f in sorted(run0_files):
        qid = f.replace("_eval.json", "")
        results = []
        for run in range(5):
            if run == 0:
                fname = qid + "_eval.json"
            else:
                fname = qid + "_run" + str(run) + "_eval.json"
            fpath = os.path.join(ds_path, fname)
            if os.path.exists(fpath):
                with open(fpath) as fp:
                    data = json.load(fp)
                results.append(data.get("passed", False))

        if len(results) < 5:
            skipped += 1
            continue

        n, c = 5, sum(results)
        ds_pass1.append(pass_at_k(n, c, 1))
        ds_pass5.append(pass_at_k(n, c, 5))
        total_queries += 1

    if ds_pass1:
        dataset_scores[ds] = {
            "pass1": sum(ds_pass1) / len(ds_pass1),
            "pass5": sum(ds_pass5) / len(ds_pass5),
            "queries": len(ds_pass1)
        }

print("Queries with all 5 runs complete: %d  (skipped incomplete: %d)" % (total_queries, skipped))
print()
print("%-22s %7s %8s %8s" % ("Dataset", "Queries", "pass@1", "pass@5"))
print("-" * 52)
all_p1 = []
all_p5 = []
for ds, s in dataset_scores.items():
    print("%-22s %7d %7.1f%% %7.1f%%" % (ds, s["queries"], s["pass1"] * 100, s["pass5"] * 100))
    all_p1.append(s["pass1"])
    all_p5.append(s["pass5"])
print("-" * 52)
if all_p1:
    print("%-22s %7d %7.1f%% %7.1f%%" % ("AVERAGE (datasets)", total_queries, sum(all_p1) / len(all_p1) * 100, sum(all_p5) / len(all_p5) * 100))
