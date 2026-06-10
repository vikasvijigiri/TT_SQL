"""
Check run slot completion status: for each query, how many of 5 runs are done.
270 total slots (54 queries x 5 runs). Report which are missing.
"""
import json
from pathlib import Path

RESULTS_DAB = Path("backend/results/dab")
MAX_RUNS = 5

DATASET_QUERIES = {
    "agnews": 4, "bookreview": 3, "crmarenapro": 13,
    "deps_dev_v1": 2, "github_repos": 4, "googlelocal": 4,
    "music_brainz_20k": 3, "pancancer_atlas": 3, "patents": 3,
    "stockindex": 3, "stockmarket": 5, "yelp": 7,
}

total_slots = 0
done_slots = 0
missing = []
per_ds = {}

for ds, n_queries in DATASET_QUERIES.items():
    ds_done = 0
    ds_total = n_queries * MAX_RUNS
    for qid in range(1, n_queries + 1):
        runs_done = 0
        for r in range(MAX_RUNS):
            sfx = "" if r == 0 else f"_run{r}"
            ef = RESULTS_DAB / ds / f"query{qid}{sfx}_eval.json"
            if ef.exists():
                runs_done += 1
                ds_done += 1
                done_slots += 1
            else:
                missing.append(f"{ds}/q{qid} run{r}")
        total_slots += MAX_RUNS
        if runs_done < MAX_RUNS:
            print(f"  INCOMPLETE  {ds}/q{qid}: {runs_done}/5 runs done")
    per_ds[ds] = (ds_done, ds_total)

print(f"\nTotal slots : {total_slots}")
print(f"Done        : {done_slots}")
print(f"Missing     : {total_slots - done_slots}")
print(f"\nMissing slots ({len(missing)}):")
for m in missing:
    print(f"  {m}")
