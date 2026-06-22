import re
import pathlib

file_path = pathlib.Path(r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\backend\agent\agent\app\core\orchestrator.py")
content = file_path.read_text(encoding="utf-8", errors="replace")

matches = re.finditer(r"self\.sql_generator\.", content)
for m in matches:
    start_line = content[:m.start()].count("\n") + 1
    print(f"Line {start_line}: {content[m.start()-50:m.end()+150].replace('\n', ' [NL] ')}")
