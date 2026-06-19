import sys
import os
from pathlib import Path

ROOT_DIR = Path("c:/Users/VikasVijigiri/Documents/TT_SQL_V2")
sys.path.insert(0, str(ROOT_DIR))

from backend.agent.agent.app.dab.benchmark_loader import load_all_queries

queries = load_all_queries("c:/Users/VikasVijigiri/Documents/DataAgentBench")
for q in queries:
    if q["dataset"] == "yelp" and q["query_id"] == "6":
        print("QUESTION:")
        print(repr(q["question"]))
        print("---")
