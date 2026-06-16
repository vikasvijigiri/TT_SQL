import json
import os
import re

target_folder = r"C:\Users\VikasVijigiri\.gemini\antigravity-ide\brain\d1bbb0f8-62e2-495a-8561-4d7a4495a782"
transcript_path = os.path.join(target_folder, ".system_generated", "logs", "transcript.jsonl")

print("Writing clean topology to frontend/src/components/topology_backup.js...")

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            content = data.get("content", "")
            if "initialWorkflowNodes = [" in content:
                # Clean prefix line numbers like "61: " or "62: "
                cleaned_lines = []
                for l in content.split("\n"):
                    l_clean = re.sub(r"^\s*\d+:\s*", "", l)
                    cleaned_lines.append(l_clean)
                
                cleaned_content = "\n".join(cleaned_lines)
                start = cleaned_content.find("const initialWorkflowNodes = [")
                if start != -1:
                    # Find matching ending of initialConnections block
                    end2 = cleaned_content.find("];", cleaned_content.find("const initialConnections = ["))
                    if end2 != -1:
                        topology_code = cleaned_content[start:end2+2]
                        backup_path = r"C:\Users\VikasVijigiri\Documents\TT_SQL_V2\frontend\src\components\topology_backup.js"
                        with open(backup_path, "w", encoding="utf-8") as out:
                            out.write(topology_code)
                        print("Successfully wrote backup to", backup_path)
                        break
        except Exception as e:
            pass
