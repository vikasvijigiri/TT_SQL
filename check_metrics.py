import sys
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2")
sys.path.insert(0, str(ROOT_DIR))

from backend.app.api import _cached_dab_metrics
res = _cached_dab_metrics(1)
import json
print(json.dumps(res['per_dataset'], indent=2))
