import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend" / "agent"))

from agent.app.db.database import SessionLocal
from agent.app.db.models import Evaluation
from agent.app.core.meta.analytics_engine import generate_analytics_report

def main():
    db = SessionLocal()
    try:
        # Load the evaluations for agnews from the database
        records = db.query(Evaluation).filter(Evaluation.dataset == "agnews").all()
        results = []
        for r in records:
            results.append({
                "dataset": r.dataset,
                "query_id": r.query_id,
                "instance_id": r.instance_id,
                "passed": r.passed,
                "reason": r.reason,
                "elapsed_s": r.elapsed_s,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "status": "passed" if r.passed else "failed"
            })
        print(f"Loaded {len(results)} evaluations from database.")
        if results:
            generate_analytics_report(results)
            print("Successfully triggered generate_analytics_report!")
        else:
            print("No evaluations found.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
