import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Force UTF-8 stdout to prevent Windows cp1252 charmap crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.dab.dab_orchestrator import run_dab_query
from agent.app.core.config import DAB_REPO
from agent.services.logger import logger

queries = load_all_queries(str(DAB_REPO))

targets = [
    ('deps_dev_v1', '1'),
    ('patents', '1')
]

print(f'Starting rigorous audit run on {len(targets)} failed queries...')

target_dicts = []
for q in queries:
    if (q['dataset'], q['query_id']) in targets:
        target_dicts.append(q)

print(f"Found {len(target_dicts)} target queries to run.")

from agent.services.llm import LLMClient
llm = LLMClient()

for q in target_dicts:
    ds = q["dataset"]
    qid = q["query_id"]
    print(f'\nRunning {ds}_q{qid}...')
    logger.info(f'\n================ AUDIT TEST RUN: {ds}_q{qid} ================')
    try:
        # Run it once
        res = run_dab_query(q, llm_client=llm)
        print(f'Status: {res.get("status")}')
        print(f'Passed: {res.get("passed")}')
        print(f'Reason: {res.get("reason")}')
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'Exception: {e}')

print('Live querying complete.')
