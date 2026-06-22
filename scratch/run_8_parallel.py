import sys
import asyncio
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend" / "agent"))

from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.dab.dab_runner import run_all_concurrent
from agent.app.utils.llm import LLMClient
from agent.app.core.config import DAB_REPO

async def main():
    queries = load_all_queries(str(DAB_REPO))
    
    # Select 8 specific Docker-free queries
    selected_targets = [
        ("github_repos", "1"),
        ("github_repos", "2"),
        ("github_repos", "3"),
        ("github_repos", "4"),
        ("stockindex", "1"),
        ("stockindex", "2"),
        ("stockindex", "3"),
        ("music_brainz_20k", "1")
    ]
    
    work = []
    for q in queries:
        for ds, qid in selected_targets:
            if q["dataset"] == ds and q["query_id"] == qid:
                work.append((q, 0)) # run_number = 0
                break
                
    if len(work) != 8:
        print(f"Error: Found {len(work)} queries instead of 8.")
        sys.exit(1)
        
    print(f"Selected 8 queries for parallel run:")
    for q, r in work:
        print(f"  - {q['dataset']}_q{q['query_id']}: {q['question'][:80]}...")
        
    # Reset cancellation flags
    try:
        from agent.app.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG
        DAB_CANCEL_FLAG.set(False)
        SPIDER_CANCEL_FLAG.set(False)
    except Exception:
        pass
        
    llm_client = LLMClient()
    print("\nStarting parallel execution of 8 queries with 8 workers...")
    
    results = await run_all_concurrent(work, llm_client, max_concurrent=8)
    
    print("\n" + "="*50)
    print("PARALLEL RUN RESULTS SUMMARY:")
    print("="*50)
    for res in results:
        status = res.get("status", "unknown")
        passed = res.get("passed", False)
        elapsed = res.get("elapsed_s", 0.0)
        print(f"  {res['dataset']}_q{res['query_id']}: {status.upper()} | Passed={passed} | Time={elapsed}s")
        
if __name__ == "__main__":
    asyncio.run(main())
