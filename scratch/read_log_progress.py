import os

log_path = r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2\parallel_run.log"

if not os.path.exists(log_path):
    print("Log file does not exist yet.")
else:
    size = os.path.getsize(log_path)
    print(f"Log file size: {size} bytes")
    # Try reading as UTF-16
    try:
        with open(log_path, "r", encoding="utf-16") as f:
            content = f.read()
        print(f"Total characters: {len(content)}")
        lines = content.splitlines()
        print(f"Total lines: {len(lines)}")
        print("\nLast 30 lines:")
        for line in lines[-30:]:
            print(line)
    except Exception as e:
        print(f"Failed to read as UTF-16: {e}")
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            print(f"Total characters (UTF-8 fallback): {len(content)}")
            lines = content.splitlines()
            print(f"Total lines: {len(lines)}")
            print("\nLast 30 lines:")
            for line in lines[-30:]:
                print(line)
        except Exception as e2:
            print(f"Failed to read as UTF-8: {e2}")
