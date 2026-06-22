import re
import pathlib

checklist_path = pathlib.Path("c:/Users/VikasVijigiri/Documents/TT_SQL_V2/world_class_checks.md")

if not checklist_path.exists():
    raise FileNotFoundError(f"Checklist not found at {checklist_path}")

content = checklist_path.read_text(encoding="utf-8")

# 1. Untick all checkboxes (replace "[x] " with "[ ] ")
unticked_content = re.sub(r"\[x\]\s+", "[ ] ", content)

# 2. Find the end of the checklist and truncate any appended sections
# The original file ends with:
# END OF CHECKLIST
# ================
end_marker = "END OF CHECKLIST\n================\n"
idx = unticked_content.find(end_marker)
if idx != -1:
    unticked_content = unticked_content[:idx + len(end_marker)]

# Write back to world_class_checks.md
checklist_path.write_text(unticked_content, encoding="utf-8")
print("Original checklist restored successfully to its unticked state!")
