import re

log_path = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\c1126b6c-f42e-42f8-8284-e65e517de103\.system_generated\tasks\task-756.log"

with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Find specific patterns
patterns = {
    "Cache/Redis": r"Redis|Cache",
    "Concurrency": r"concurrent|parallel|workers",
    "Pre-flight/Identifier Check": r"IDENTIFIER CHECK|Hallucinated identifiers|pre-flight",
    "Rule Consolidation/Dynamic Rules": r"Consolidation complete|DynamicRuleStore|CANDIDATE",
    "Dialect Discovery/Adaptation": r"Dialect:",
    "Self Diagnosis/Correction": r"SelfDiagnosis|SELF_CORRECTOR|Self-Correction",
    "SQLGlot validation": r"SQLGlot syntax validation",
    "Failed queries summary": r"FAILED \| Passed=False",
    "Query-aware DB selection": r"Query-aware DB selection"
}

for name, pattern in patterns.items():
    print(f"\n=== MATCHES FOR: {name} (Pattern: {pattern}) ===")
    count = 0
    for idx, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            print(f"Line {idx+1}: {line.strip()}")
            count += 1
            if count >= 30:
                print("... truncated after 30 matches ...")
                break
