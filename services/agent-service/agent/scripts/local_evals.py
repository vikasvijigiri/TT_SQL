import os
import json
import statistics
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2")
import sys
sys.path.insert(0, str(ROOT_DIR))

from agent.app.core.langsmith_evaluators import ALL_EVALUATORS

RESULTS_DIR = ROOT_DIR / "backend" / "results"
all_jsons = list(RESULTS_DIR.rglob("*_eval.json"))
if not all_jsons:
    all_jsons = list(RESULTS_DIR.rglob("*.json"))

scores = {fn.__name__.replace('eval_', ''): [] for fn in ALL_EVALUATORS}

for f in all_jsons:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, dict): continue
        if 'passed' not in data and 'status' not in data: continue
        
        # We need a standardized object for evaluators
        # they expect: "agent_answer_snippet", "ground_truth", "passed"
        if "agent_answer_snippet" not in data:
            data["agent_answer_snippet"] = str(data.get("agent_answer", ""))
            
        for fn in ALL_EVALUATORS:
            key = fn.__name__.replace('eval_', '')
            res = fn(data)
            score = res.get('score')
            if score is not None:
                scores[key].append(score)
    except Exception as e:
        pass

for k, vals in scores.items():
    if vals:
        print(f"{k}: {sum(vals)/len(vals):.3f} (N={len(vals)})")
