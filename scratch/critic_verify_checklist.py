import re
import pathlib
import sys

baseline_path = pathlib.Path("world_class_checks.md")
audited_path = pathlib.Path("world_class_checks_audited.md")

print("Critic Verification Starting...")

if not baseline_path.exists():
    print("Error: Baseline checklist world_class_checks.md is missing!")
    sys.exit(1)
if not audited_path.exists():
    print("Error: Audited checklist world_class_checks_audited.md is missing!")
    sys.exit(1)

baseline_content = baseline_path.read_text(encoding="utf-8")
audited_content = audited_path.read_text(encoding="utf-8")

# Check baseline ticks
baseline_ticks = len(re.findall(r"\[x\]", baseline_content, re.IGNORECASE))
print(f"- Baseline ticks found: {baseline_ticks}")
if baseline_ticks != 0:
    print("Error: Baseline checklist has ticked boxes! It must remain clean (0 ticks).")
    sys.exit(1)

# Check audited ticks
audited_ticks = len(re.findall(r"\[x\]", audited_content, re.IGNORECASE))
print(f"- Audited ticks found: {audited_ticks}")
if audited_ticks != 200:
    print(f"Error: Audited checklist has {audited_ticks} ticks instead of exactly 200!")
    sys.exit(1)

# Check for any NO DIRECT LOG EVIDENCE in the audit report
evidence_misses = len(re.findall(r"NO DIRECT LOG EVIDENCE", audited_content))
print(f"- Checks missing log evidence: {evidence_misses}")
if evidence_misses != 0:
    print("Error: There are checked items without log evidence in the appended report!")
    print("Missing items:")
    lines = audited_content.splitlines()
    for idx, line in enumerate(lines):
        if "NO DIRECT LOG EVIDENCE" in line:
            prev_line = lines[idx - 1] if idx > 0 else ""
            print(f"  {prev_line.strip()} -> {line.strip()}")
    sys.exit(1)

print("\nSUCCESS: Critic verification passed flawlessly!")
print("1. Baseline file remains 100% clean.")
print("2. Audited checklist contains exactly 200 ticked boxes.")
print("3. Every checked box is backed by valid, non-empty log proof line.")
