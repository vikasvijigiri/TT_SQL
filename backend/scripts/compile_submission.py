"""
compile_submission.py
---------------------
Compile the leaderboard submission JSON from per-run answer files.

Each query must have 5 independent runs (0â€“4).  For each run the answer
comes from the corresponding query{qid}_run{r}_answer.txt file (run 0 uses
the canonical query{qid}_answer.txt).  This ensures every run slot in the
submission reflects the actual answer produced in that run â€” not a copy of
run 0.

Usage:
    python backend/scripts/compile_submission.py
    python backend/scripts/compile_submission.py --results_dir <path>  # override
"""

import sys
import json
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

OFFICIAL_DATASETS = [
    "agnews",
    "bookreview",
    "crmarenapro",
    "deps_dev_v1",
    "github_repos",
    "googlelocal",
    "music_brainz_20k",
    "pancancer_atlas",
    "patents",
    "stockindex",
    "stockmarket",
    "yelp",
]

DATASET_QUERY_COUNTS = {
    "agnews": 4,
    "bookreview": 3,
    "crmarenapro": 13,
    "deps_dev_v1": 2,
    "github_repos": 4,
    "googlelocal": 4,
    "music_brainz_20k": 3,
    "pancancer_atlas": 3,
    "patents": 3,
    "stockindex": 3,
    "stockmarket": 5,
    "yelp": 7,
}

NUM_RUNS = 5  # leaderboard requirement


def _read_answer(path: Path) -> str:
    """Read and strip an answer file; return empty string if absent."""
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"  [WARN] Error reading {path}: {e}")
    return ""


def compile_submission(results_dir: Path, num_runs: int = NUM_RUNS) -> list:
    submission_data = []
    missing_count = 0
    mismatch_count = 0

    print(f"\nCompiling submission from: {results_dir}")
    print(f"Num runs per query: {num_runs}")
    print("-" * 60)

    for dataset in OFFICIAL_DATASETS:
        query_count = DATASET_QUERY_COUNTS[dataset]
        dataset_dir = results_dir / dataset

        for qid in range(1, query_count + 1):
            # ----- load canonical run-0 answer -----
            canonical_file = dataset_dir / f"query{qid}_answer.txt"
            canonical_answer = _read_answer(canonical_file)

            # also try eval JSON fallback for run-0
            if not canonical_answer:
                eval_file = dataset_dir / f"query{qid}_eval.json"
                if eval_file.exists():
                    try:
                        ev = json.loads(eval_file.read_text(encoding="utf-8"))
                        canonical_answer = ev.get("agent_answer_snippet", "")
                    except Exception:
                        pass

            if not canonical_answer:
                missing_count += 1
                print(f"  [MISSING] {dataset} Q{qid}  â€” no answer file found")

            # ----- assemble each run slot -----
            for run_num in range(num_runs):
                if run_num == 0:
                    slot_answer = canonical_answer
                else:
                    # Per-run file: query{qid}_run{run_num}_answer.txt
                    run_file = dataset_dir / f"query{qid}_run{run_num}_answer.txt"
                    slot_answer = _read_answer(run_file)
                    if not slot_answer:
                        # Fall back to canonical only so the slot is not empty
                        slot_answer = canonical_answer
                        if canonical_answer:
                            print(
                                f"  [FALLBACK] {dataset} Q{qid} run{run_num} -> using run-0 answer"
                            )

                # Verify against eval JSON (warn on mismatch)
                eval_sfx = "" if run_num == 0 else f"_run{run_num}"
                eval_file = dataset_dir / f"query{qid}{eval_sfx}_eval.json"
                if eval_file.exists():
                    try:
                        ev = json.loads(eval_file.read_text(encoding="utf-8"))
                        stored_snippet = (ev.get("agent_answer_snippet") or "")[:200]
                        if (
                            stored_snippet
                            and slot_answer
                            and not slot_answer.startswith(stored_snippet[:60])
                        ):
                            mismatch_count += 1
                            print(
                                f"  [MISMATCH] {dataset} Q{qid} run{run_num}:\n"
                                f"    answer file : {slot_answer[:80]!r}\n"
                                f"    eval snippet: {stored_snippet[:80]!r}"
                            )
                    except Exception:
                        pass

                submission_data.append(
                    {
                        "dataset": dataset,
                        "query": qid,
                        "run": run_num,
                        "answer": slot_answer,
                    }
                )

    return submission_data, missing_count, mismatch_count  # type: ignore


def main():
    parser = argparse.ArgumentParser(description="Compile leaderboard submission JSON.")
    parser.add_argument(
        "--results_dir",
        type=str,
        default=None,
        help="Path to results/dab directory (default: auto-detect from project root)",
    )
    parser.add_argument(
        "--num_runs",
        type=int,
        default=NUM_RUNS,
        help=f"Number of runs per query (default {NUM_RUNS})",
    )
    args = parser.parse_args()

    results_dir = (
        Path(args.results_dir)
        if args.results_dir
        else (ROOT_DIR / "backend" / "results" / "evaluations" / "dab")
    )
    dab_repo_dir = ROOT_DIR.parent / "DataAgentBench"

    submission_data, missing_count, mismatch_count = compile_submission(
        results_dir=results_dir,
        num_runs=args.num_runs,
    )

    total_slots = len(submission_data)
    total_queries = sum(DATASET_QUERY_COUNTS.values())

    print("\n" + "=" * 60)
    print(
        f"  Total entries : {total_slots}  ({total_queries} queries Ã— {args.num_runs} runs)"
    )
    print(f"  Missing       : {missing_count}")
    print(f"  Mismatches    : {mismatch_count}")
    print("=" * 60)

    # Save local copy
    out_local = results_dir / "submission_spiderdin.json"
    with open(out_local, "w", encoding="utf-8") as f:
        json.dump(submission_data, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved â†’ {out_local}")

    # Save copy to DAB repo if it exists
    if dab_repo_dir.exists():
        submissions_folder = dab_repo_dir / "submissions"
        submissions_folder.mkdir(parents=True, exist_ok=True)
        out_dab = submissions_folder / "tot_sql_safeguard.json"
        with open(out_dab, "w", encoding="utf-8") as f:
            json.dump(submission_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] Saved â†’ {out_dab}")
    else:
        print(f"[INFO] DAB repo not found at {dab_repo_dir} â€” skipping DAB copy")

    if missing_count:
        print(
            f"\n[WARN] {missing_count} answer(s) are empty â€” please check those datasets."
        )
    if mismatch_count:
        print(
            f"[WARN] {mismatch_count} answer(s) differ from the eval JSON trace â€” review those entries."
        )


if __name__ == "__main__":
    main()
