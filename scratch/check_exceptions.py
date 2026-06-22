import os

log_path = r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2\parallel_run.log"

if not os.path.exists(log_path):
    print("Log file does not exist.")
    exit(1)

# Try reading as UTF-16
try:
    with open(log_path, "r", encoding="utf-16") as f:
        content = f.read()
except Exception:
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

# If it has spaces between letters (common issue with UTF-16 redirected to standard streams in some configurations),
# let's detect and fix it. E.g. "P A R A L L E L" -> "PARALLEL"
# Wait, if every second character is a space, we can fix it.
# Let's inspect the first 20 characters
print("First 50 chars raw:", repr(content[:50]))

# Let's clean it up: if there's null bytes or weird spacing, clean it
# Write a cleaned version to parallel_run_clean.log
cleaned = content.replace("\x00", "")

# If it looks like "P\x00A\x00R\x00" it's UTF-16 read as UTF-8
# If it looks like "P A R A L L E L" (spaces between letters), let's check
if len(cleaned) > 100 and cleaned[1] == ' ' and cleaned[3] == ' ' and cleaned[5] == ' ':
    # It might have been double-spaced
    # Let's only do this if it's consistently double spaced
    # Actually, we can just read the file as binary and decode properly
    pass

with open(log_path, "rb") as f:
    raw = f.read()

print("Raw bytes start:", raw[:40])

# Let's try decoding raw bytes:
decodings = ["utf-16", "utf-16-le", "utf-8", "latin-1"]
decoded_content = None
for dec in decodings:
    try:
        decoded_content = raw.decode(dec)
        print(f"Successfully decoded with {dec}! First 100 chars:")
        print(repr(decoded_content[:100]))
        # Save a clean UTF-8 copy
        with open(r"c:\Users\VikasVijigiri\Documents\TT_SQL_V2\parallel_run_clean.log", "w", encoding="utf-8") as f_out:
            f_out.write(decoded_content)
        print("Saved cleaned log to parallel_run_clean.log")
        break
    except Exception as e:
        print(f"Failed {dec}: {e}")
