import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.app.core.langsmith_evaluators import run_langsmith_experiment

try:
    summary = run_langsmith_experiment("Audit_Run")
    import json
    print(json.dumps(summary, indent=2))
except Exception as e:
    print(f"Failed to run langsmith eval (likely API key or network issue): {e}")
