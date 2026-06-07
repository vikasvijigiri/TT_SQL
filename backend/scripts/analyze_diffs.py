"""Systematic analysis: compare ALL generated CSVs against gold to find patterns."""
import json
import math
import os
from pathlib import Path

import pandas as pd

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
GOLD_DIR = Path(__file__).resolve().parent.parent / "resources" / "gold" / "exec_result"
EVAL_JSONL = Path(__file__).resolve().parent.parent / "resources" / "gold" / "spider2lite_eval.jsonl"

# Load eval standards
eval_standards = {}
with open(EVAL_JSONL) as f:
    for line in f:
        item = json.loads(line.strip())
        eval_standards[item["instance_id"]] = item

def find_all_result_csvs():
    """Find all result CSVs across all database dirs."""
    results = []
    for db_dir in RESULTS_ROOT.iterdir():
        if not db_dir.is_dir():
            continue
        for csv_file in db_dir.glob("*.csv"):
            if "_evidence" in csv_file.name or "_probe" in csv_file.name or "_diag" in csv_file.name:
                continue
            instance_id = csv_file.stem
            results.append((instance_id, csv_file, db_dir.name))
    return results

def compare_values(pred_df, gold_df):
    """Find specific cell-level differences."""
    diffs = []
    # Compare by matching columns (transpose-based like evaluate.py)
    for gi, gold_col in enumerate(gold_df.columns):
        gold_vals = gold_df[gold_col].tolist()
        # Find closest matching pred column
        best_match = None
        best_diffs = None
        min_total_diff = float('inf')
        for pi, pred_col in enumerate(pred_df.columns):
            pred_vals = pred_df[pred_col].tolist()
            if len(pred_vals) != len(gold_vals):
                continue
            col_diffs = []
            total_diff = 0
            for gv, pv in zip(gold_vals, pred_vals):
                if pd.isna(gv) and pd.isna(pv):
                    col_diffs.append(("match", gv, pv, 0))
                    continue
                if isinstance(gv, (int, float)) and isinstance(pv, (int, float)):
                    d = abs(float(gv) - float(pv))
                    if d < 0.01:
                        col_diffs.append(("match", gv, pv, d))
                    else:
                        col_diffs.append(("DIFF", gv, pv, d))
                        total_diff += d
                elif str(gv) == str(pv):
                    col_diffs.append(("match", gv, pv, 0))
                else:
                    col_diffs.append(("DIFF", gv, pv, -1))
                    total_diff += 1000  # string mismatch penalty
            if total_diff < min_total_diff:
                min_total_diff = total_diff
                best_match = pred_col
                best_diffs = col_diffs
        if best_diffs:
            for i, (status, gv, pv, d) in enumerate(best_diffs):
                if status == "DIFF":
                    diffs.append({
                        "gold_col": gold_col,
                        "pred_col": best_match,
                        "row": i,
                        "gold_val": gv,
                        "pred_val": pv,
                        "abs_diff": d if d >= 0 else "str_mismatch"
                    })
    return diffs

def resolve_gold_paths(instance_id):
    base = GOLD_DIR / f"{instance_id}.csv"
    if base.exists():
        return [base]
    import re
    pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
    return sorted(GOLD_DIR / f for f in os.listdir(GOLD_DIR) if pattern.match(f))

# Main analysis
all_results = find_all_result_csvs()
print(f"Found {len(all_results)} result CSVs")
print("=" * 80)

close_misses = []
exact_matches = []
far_misses = []

for instance_id, csv_path, db_name in all_results:
    gold_paths = resolve_gold_paths(instance_id)
    if not gold_paths:
        continue

    try:
        pred_df = pd.read_csv(csv_path)
    except Exception:
        continue

    best_score = 0
    best_diffs = None
    best_gold_name = None

    for gp in gold_paths:
        try:
            gold_df = pd.read_csv(gp)
        except Exception:
            continue

        if pred_df.shape[0] != gold_df.shape[0]:
            continue

        diffs = compare_values(pred_df, gold_df)
        if not diffs:
            best_score = 1
            best_gold_name = gp.name
            best_diffs = []
            break
        elif best_diffs is None or len(diffs) < len(best_diffs):
            best_diffs = diffs
            best_gold_name = gp.name

    if best_score == 1:
        exact_matches.append(instance_id)
    elif best_diffs is not None:
        # Classify as close miss vs far miss
        numeric_diffs = [d for d in best_diffs if isinstance(d["abs_diff"], (int, float))]
        if numeric_diffs and all(d["abs_diff"] < 10 for d in numeric_diffs) and len(best_diffs) <= 10:
            close_misses.append((instance_id, db_name, best_gold_name, best_diffs))
        else:
            far_misses.append((instance_id, db_name, best_gold_name, best_diffs))

print(f"\nExact matches: {len(exact_matches)}")
print(f"Close misses (off by small amounts): {len(close_misses)}")
print(f"Far misses: {len(far_misses)}")

if close_misses:
    print("\n" + "=" * 80)
    print("CLOSE MISSES — Numbers are close but not exact:")
    print("=" * 80)
    for instance_id, db_name, gold_name, diffs in close_misses:
        print(f"\n--- {instance_id} (DB: {db_name}, Gold: {gold_name}) ---")
        for d in diffs:
            print(f"  Row {d['row']}: gold_col='{d['gold_col']}' pred_col='{d['pred_col']}' | Gold={d['gold_val']} Pred={d['pred_val']} | Diff={d['abs_diff']}")

    # Pattern analysis
    print("\n" + "=" * 80)
    print("PATTERN ANALYSIS:")
    print("=" * 80)
    all_numeric_diffs = []
    for _, _, _, diffs in close_misses:
        for d in diffs:
            if isinstance(d["abs_diff"], (int, float)) and d["abs_diff"] > 0:
                all_numeric_diffs.append(d["abs_diff"])

    if all_numeric_diffs:
        print(f"  Total numeric differences: {len(all_numeric_diffs)}")
        print(f"  Integer diffs (off by exactly N): {sum(1 for d in all_numeric_diffs if d == int(d))}")
        print(f"  Fractional diffs: {sum(1 for d in all_numeric_diffs if d != int(d))}")
        print(f"  Diff values: {sorted(set(round(d, 6) for d in all_numeric_diffs))}")
        int_diffs = [int(d) for d in all_numeric_diffs if d == int(d)]
        if int_diffs:
            from collections import Counter
            print(f"  Integer diff distribution: {dict(Counter(int_diffs).most_common(10))}")

if far_misses:
    print(f"\n--- Far misses ({len(far_misses)} total, showing first 3): ---")
    for instance_id, db_name, gold_name, diffs in far_misses[:3]:
        print(f"\n  {instance_id} (DB: {db_name}): {len(diffs)} differences")
        for d in diffs[:3]:
            print(f"    Row {d['row']}: Gold={d['gold_val']} Pred={d['pred_val']} Diff={d['abs_diff']}")
