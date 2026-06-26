import os
from pathlib import Path

scripts_dir = Path(r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\services\agent-service\agent\scripts")
for file in scripts_dir.glob("*.py"):
    content = file.read_text(encoding="utf-8")
    original_str = 'Path(r"c:\\Users\\VikasVijigiri\\Documents\\TT_SQL_V2")'
    if original_str in content:
        content = content.replace(
            original_str,
            "Path(__file__).resolve().parent.parent.parent.parent"
        )
        file.write_text(content, encoding="utf-8")
        print(f"Updated {file.name}")
