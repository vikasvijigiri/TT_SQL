"""
run_self_improve.py
-------------------
Standalone entry point for the daily self-improvement pipeline.
Intended to be invoked by Windows Task Scheduler or a cron job.

Usage:
    python services/agent-service/agent/scripts/run_self_improve.py

Schedule (Windows Task Scheduler):
    Action: python "C:\\path\\to\\TT_SQL_PLATFORM\\services\\agent-service\\agent\\scripts\\run_self_improve.py"
    Trigger: Daily, 02:07 AM
    Start in: C:\\path\\to\\TT_SQL_PLATFORM
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.app.core.rules.self_improving_loop import SelfImprovingLoop
from agent.app.core.config import DAB_REPO


def main():
    print("=" * 60)
    print("  TT_SQL_V2 -- Daily Self-Improvement Pipeline")
    print("=" * 60)

    loop = SelfImprovingLoop(dab_repo=str(DAB_REPO))
    result = loop.run_daily()

    print(f"\nStatus   : {result['status']}")

    if result.get("run"):
        run = result["run"]
        print(f"Date     : {run['date']}")
        print(f"Rounds   : {len(run['rounds'])}")
        print(f"Pass@1   : {run['final_passes']}/{run['total']}  ({run['pass_rate']}%)")
        print()
        for r in run["rounds"]:
            delta_str = f"+{r['delta']}" if r["delta"] > 0 else str(r["delta"])
            print(
                f"  Round {r['round']}: {r['status']:16s}  "
                f"={delta_str:>3}  rules={r.get('new_rules_added', 0):>2}  "
                f"elapsed={r.get('elapsed_s', 0):.0f}s"
            )

    if result.get("rule_counts"):
        rc = result["rule_counts"]
        print(
            f"\nRules => ACTIVE:{rc.get('ACTIVE', 0)}  "
            f"REJECTED:{rc.get('REJECTED', 0)}  "
            f"INACTIVE:{rc.get('INACTIVE', 0)}"
        )

    if result.get("saturated"):
        print(
            "\n[SATURATED] Pipeline has converged -- accuracy cannot improve further with current architecture."
        )

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
