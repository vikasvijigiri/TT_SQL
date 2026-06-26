import warnings
warnings.filterwarnings("ignore")
from agent.app.services.witness_hunter import hunt
from agent.app.services.semantic_engine import SemanticContextEngine

# Test 1: agnews - should now show content sample of article descriptions
print("=== agnews ===")
db_dir = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_agnews/query_dataset'
engine = SemanticContextEngine(db_dir)
ctx = engine.build_context()
bundle = hunt(
    question="What is the title of the sports article whose description has the greatest number of characters?",
    schema_context=ctx,
    relevant_tables=["articles"],
    db_directory=db_dir,
    max_probes=3,
)
print(f"Probes: {bundle.probes_run}, Findings: {len(bundle.findings)}")
for f in bundle.findings:
    safe = f.encode('ascii', errors='replace').decode('ascii')
    print(safe[:500])
    print("---")

# Test 2: deps_dev_v1 - should still get 3 witnesses + fanout detection
print("\n=== deps_dev_v1 ===")
db_dir2 = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_DEPS_DEV_V1/query_dataset'
engine2 = SemanticContextEngine(db_dir2)
ctx2 = engine2.build_context()
bundle2 = hunt(
    question="Which NPM packages are the top 5 most popular based on Github star number?",
    schema_context=ctx2,
    relevant_tables=["project_info", "project_packageversion", "packageinfo"],
    db_directory=db_dir2,
    max_probes=5,
)
print(f"Probes: {bundle2.probes_run}, Findings: {len(bundle2.findings)}")
for f in bundle2.findings:
    safe = f.encode('ascii', errors='replace').decode('ascii')
    print(safe[:400])
    print("---")
