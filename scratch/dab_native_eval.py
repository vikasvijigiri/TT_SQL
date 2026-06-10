"""
Re-evaluate all stored agent answers using the DAB repo's own validate.py scripts,
exactly the way DataAgentBench does it — no custom logic, no bias.

For each query, reads:
  - backend/results/DAB_{DATASET}/dab_{dataset}_q{id}.csv  (the SQL result)
  - backend/results/dab/{dataset}/query{id}_eval.json       (existing eval)

Passes the AGENT ANSWER TEXT (csv content + answer label) through the DAB
validate.py using importlib — same as common_scaffold/validate/validate.py.

Writes updated eval JSONs back to disk and prints a fresh report.
"""
import sys
import json
import importlib.util
import re
from pathlib import Path
from datetime import datetime

DAB_REPO = Path("C:/Users/VikasVijigiri/Documents/DataAgentBench")
RESULTS_DAB = Path("backend/results/dab")
RESULTS_CSV = Path("backend/results")

# Same dataset mapping as benchmark_loader
DATASET_MAP = {
    "agnews":           ("query_agnews",          "DAB_AGNEWS"),
    "bookreview":       ("query_bookreview",       "DAB_BOOKREVIEW"),
    "crmarenapro":      ("query_crmarenapro",      "DAB_CRMARENAPRO"),
    "deps_dev_v1":      ("query_DEPS_DEV_V1",      "DAB_DEPS_DEV_V1"),
    "github_repos":     ("query_GITHUB_REPOS",     "DAB_GITHUB_REPOS"),
    "googlelocal":      ("query_googlelocal",      "DAB_GOOGLELOCAL"),
    "music_brainz_20k": ("query_music_brainz_20k", "DAB_MUSIC_BRAINZ_20K"),
    "pancancer_atlas":  ("query_PANCANCER_ATLAS",  "DAB_PANCANCER_ATLAS"),
    "patents":          ("query_PATENTS",           "DAB_PATENTS"),
    "stockindex":       ("query_stockindex",       "DAB_STOCKINDEX"),
    "stockmarket":      ("query_stockmarket",      "DAB_STOCKMARKET"),
    "yelp":             ("query_yelp",             "DAB_YELP"),
}

QUERY_COUNTS = {
    "agnews": 4, "bookreview": 3, "crmarenapro": 13,
    "deps_dev_v1": 2, "github_repos": 4, "googlelocal": 4,
    "music_brainz_20k": 3, "pancancer_atlas": 3, "patents": 3,
    "stockindex": 3, "stockmarket": 5, "yelp": 7,
}


def run_dab_validate(query_dir: Path, agent_answer: str):
    """Execute the DAB repo's validate.py directly via importlib."""
    validate_py = query_dir / "validate.py"
    if not validate_py.exists():
        return False, f"validate.py not found: {validate_py}"
    try:
        spec = importlib.util.spec_from_file_location("_validate_mod", str(validate_py))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.validate(agent_answer)
        if isinstance(result, tuple) and len(result) == 2:
            return bool(result[0]), str(result[1])
        return bool(result), "OK" if result else "FAIL"
    except Exception as e:
        return False, f"validate.py error: {e}"


def build_agent_answer(dataset: str, query_id: str, csv_folder: str) -> str:
    """
    Read the full saved agent answer text.
    Priority:
      1. query{id}_answer.txt — the LLM-extracted concise answer (exact text passed to evaluate_answer)
      2. Raw CSV content — fallback if answer.txt not found
    """
    # Primary: LLM-extracted answer text (same as what evaluate_answer received)
    answer_txt = RESULTS_DAB / dataset / f"query{query_id}_answer.txt"
    if answer_txt.exists():
        try:
            return answer_txt.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            pass

    # Fallback: raw CSV
    csv_path = RESULTS_CSV / csv_folder / f"dab_{dataset}_q{query_id}.csv"
    if csv_path.exists():
        try:
            return csv_path.read_text(encoding="utf-8-sig", errors="replace").strip()
        except Exception:
            pass

    return ""



def main():
    sys.path.insert(0, str(DAB_REPO))

    total = 0
    passed_at1 = 0
    per_dataset = {}

    for dataset, (query_folder, csv_folder) in DATASET_MAP.items():
        n_queries = QUERY_COUNTS[dataset]
        per_dataset[dataset] = {"total": n_queries, "passed": 0, "failed": 0, "queries": []}

        for qid in range(1, n_queries + 1):
            total += 1
            qid_str = str(qid)
            query_dir = DAB_REPO / query_folder / f"query{qid}"

            agent_answer = build_agent_answer(dataset, qid_str, csv_folder)
            passed, reason = run_dab_validate(query_dir, agent_answer)

            if passed:
                passed_at1 += 1
                per_dataset[dataset]["passed"] += 1
            else:
                per_dataset[dataset]["failed"] += 1

            per_dataset[dataset]["queries"].append({
                "query_id": qid_str,
                "passed": passed,
                "reason": reason,
                "answer_snippet": agent_answer[:120],
            })

            status = "PASS" if passed else "FAIL"
            safe_reason = reason[:80].encode('ascii', errors='replace').decode('ascii')
            print(f"  [{status}] {dataset}/q{qid} - {safe_reason}")


            # Update the eval JSON on disk with fresh DAB-native result
            eval_path = RESULTS_DAB / dataset / f"query{qid_str}_eval.json"
            if eval_path.exists():
                with open(eval_path, encoding="utf-8") as f:
                    ev = json.load(f)
            else:
                ev = {}
            ev["passed"] = passed
            ev["reason"] = reason
            ev["method"] = "dab_native_validate_py"
            ev["re_evaluated_at"] = datetime.now().isoformat()
            eval_path.parent.mkdir(parents=True, exist_ok=True)
            with open(eval_path, "w", encoding="utf-8") as f:
                json.dump(ev, f, indent=2)

    acc = passed_at1 / total if total else 0.0
    print(f"\n{'='*60}")
    print(f"  DAB Native Re-Evaluation — SpiderDIN / TT_SQL_V2")
    print(f"{'='*60}")
    print(f"  Total   : {total}")
    print(f"  Passed  : {passed_at1}")
    print(f"  Failed  : {total - passed_at1}")
    print(f"  Pass@1  : {acc*100:.1f}%")
    print(f"{'-'*60}")
    print(f"  {'Dataset':<25} {'Total':>5} {'Pass':>5} {'Fail':>5} {'Acc':>6}")
    print(f"{'-'*60}")
    for ds, info in sorted(per_dataset.items()):
        t = info["total"]; p = info["passed"]; f = info["failed"]
        a = f"{round(p/t*100)}%" if t else "N/A"
        print(f"  {ds:<25} {t:>5} {p:>5} {f:>5} {a:>6}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
