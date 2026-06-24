import os
import json
import statistics
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2")
RESULTS_DIR = ROOT_DIR / "backend" / "results"

all_jsons = list(RESULTS_DIR.rglob("*_eval.json"))
if not all_jsons:
    all_jsons = list(RESULTS_DIR.rglob("*.json"))

print(f"Found {len(all_jsons)} JSON result files.")

total = 0
passed = 0
latencies = []
errors = {}
datasets = {}

for f in all_jsons:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        if not isinstance(data, dict):
            continue
            
        # Standard DAB result has 'passed', 'elapsed_s', 'dataset', 'error', 'reason'
        if 'passed' not in data and 'status' not in data:
            continue
            
        total += 1
        if data.get('passed'):
            passed += 1
            
        lat = data.get('elapsed_s') or data.get('latency')
        if lat and isinstance(lat, (int, float)):
            latencies.append(lat)
            
        ds = data.get('dataset', 'unknown')
        if ds not in datasets:
            datasets[ds] = {"total": 0, "passed": 0}
        datasets[ds]["total"] += 1
        if data.get('passed'):
            datasets[ds]["passed"] += 1
            
        reason = data.get('reason', '') or data.get('error', '')
        if reason and not data.get('passed'):
            # truncate reason
            reason_short = str(reason)[:80]
            errors[reason_short] = errors.get(reason_short, 0) + 1
            
    except Exception as e:
        pass

print(f"\nTotal Analyzed: {total}")
if total > 0:
    print(f"Overall Pass Rate: {passed/total*100:.2f}% ({passed}/{total})")

if latencies:
    print(f"Avg Latency: {statistics.mean(latencies):.2f}s")
    print(f"Median Latency: {statistics.median(latencies):.2f}s")
    print(f"Max Latency: {max(latencies):.2f}s")

print("\n--- By Dataset ---")
for ds, stats in datasets.items():
    print(f"{ds}: {stats['passed']/stats['total']*100:.1f}% ({stats['passed']}/{stats['total']})")

print("\n--- Top Failure Reasons ---")
for r, c in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"{c}x: {r}")

