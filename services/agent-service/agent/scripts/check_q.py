import sys
from pathlib import Path
ROOT_DIR = Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2")
sys.path.insert(0, str(ROOT_DIR))
from agent.app.core.config import DAB_REPO
from agent.app.dab.benchmark_loader import load_all_queries
queries = load_all_queries(DAB_REPO)
datasets = {}
for q in queries:
    datasets.setdefault(q['dataset'], []).append(q['query_id'])
for d, ids in datasets.items():
    print(f"{d}: {ids[:5]} (total: {len(ids)})")
