"""One-shot script: re-apply _sanitize_reason to all failure JSONL files."""
import re, json, pathlib, sys

PATTERNS = [
    (re.compile(r"Target '[^']+' not stated"), "Answer value not found in first 200 chars of output"),
    (re.compile(r"(Missing [^:]+): .+"), r"\1 value not found in output"),
    (re.compile(r"Found ([^[]+?)\s*\[.+\], but expected '.+'"), r"Found wrong \1— output did not match expected"),
    (re.compile(r"Ground truth '[^']+' not found in LLM output: .+"), "Output value does not match ground truth — check your aggregation logic"),
    (re.compile(r"No value in LLM output (rounds to|matches) .+"), "Numeric value in output does not match expected — check aggregation/calculation"),
    (re.compile(r"Not matched \(fuzzy\) within \d+ chars?: '.+'"), "Output text does not fuzzy-match expected value — check exact spelling and capitalisation from DB"),
    (re.compile(r"No fuzzy match (found )?for '[^']+'.+"), "Fuzzy match failed — output text did not match expected value"),
    (re.compile(r"No fuzzy match \([^)]+\) found in .+"), "Output text did not fuzzy-match expected value — check title normalisation"),
    (re.compile(r"Name not found within \d+ edits: '[^']+'.+"), "Output did not match expected name — check ORDER BY and join logic"),
    (re.compile(r"Version '[^']+' not found after name '[^']+'"), "Name-version pair missing from output — ensure all required packages are listed"),
]

def sanitize(reason: str) -> str:
    for pattern, replacement in PATTERNS:
        reason = pattern.sub(replacement, reason)
    return reason

learning_dir = pathlib.Path(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\resources\memory\dab_learning")
changed = 0
for jsonl in learning_dir.glob("*_failures.jsonl"):
    entries = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    new_entries = []
    dirty = False
    for e in entries:
        old = e.get("reason", "")
        new = sanitize(old)
        if new != old:
            dirty = True
        e["reason"] = new
        new_entries.append(e)
    if dirty:
        jsonl.write_text("\n".join(json.dumps(e) for e in new_entries) + "\n", encoding="utf-8")
        print(f"  cleaned: {jsonl.name}")
        changed += 1

print(f"\nDone. {changed} files updated.")
