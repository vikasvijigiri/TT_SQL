import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.app.api import _cached_dab_metrics
res = _cached_dab_metrics(1)
import json
print(json.dumps(res['per_dataset'], indent=2))
