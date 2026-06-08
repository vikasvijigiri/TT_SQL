api_path = "backend/app/api.py"

def safe_str(s):
    return str(s).encode("ascii", errors="replace").decode("ascii")

print("Printing lines 1680-1750 from api.py...")
with open(api_path, "r", encoding="utf-8") as f:
    lines = f.readlines()
    for idx in range(1679, 1750):
        if idx < len(lines):
            print(f"{idx+1}: {safe_str(lines[idx].strip())}")
