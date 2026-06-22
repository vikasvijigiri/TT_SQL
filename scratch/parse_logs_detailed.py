import re

log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "Consolidation complete" and print surrounding lines
print("=== CONSOLIDATION DETAIL ===")
c_matches = re.findall(r"(?:.*\n){0,5}.*Consolidation complete.*(?:\n.*){0,5}", content)
for match in c_matches:
    print(match)
    print("-" * 50)

# Let's search for "DynamicRuleStore" rules added
print("\n=== DYNAMIC RULE CANDIDATES ===")
rules_added = re.findall(r"DynamicRuleStore: added CANDIDATE.*", content)
for r in rules_added[:15]:
    print(r)

# Let's search for "pre-flight error" or "Hallucinated identifiers"
print("\n=== PRE-FLIGHT / IDENTIFIER CHECKS ===")
id_checks = re.findall(r"(?:.*\n){0,2}.*Hallucinated identifiers.*(?:\n.*){0,2}", content)
for match in id_checks[:10]:
    print(match)
    print("-" * 50)

# Let's search for "SQLGlot syntax validation failed"
print("\n=== SQLGLOT WARNINGS ===")
sqlglot_warns = re.findall(r".*SQLGlot syntax validation.*", content)
for w in sqlglot_warns[:10]:
    print(w)

# Let's search for caching or redis
print("\n=== CACHING/REDIS ===")
redis_matches = re.findall(r".*Redis.*", content)
for r in redis_matches:
    print(r)

# Let's extract details for each query: GITHUB_REPOS, MUSIC_BRAINZ_20K, STOCKINDEX
print("\n=== DATASET / QUERY DETAILS ===")
for dataset in ["GITHUB_REPOS", "MUSIC_BRAINZ_20K", "STOCKINDEX"]:
    matches = re.findall(rf".*> DAB: {dataset} / QUERY \d+.*", content)
    for m in matches:
        print(m)
