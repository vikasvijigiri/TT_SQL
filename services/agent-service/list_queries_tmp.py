import warnings
warnings.filterwarnings("ignore")
from agent.app.dab.benchmark_loader import load_all_queries
from agent.app.core.config import DAB_REPO
qs = load_all_queries(str(DAB_REPO))
print(f"Total: {len(qs)}")
for q in qs:
    print(f"{q['instance_id']} | {q['dataset']}")
