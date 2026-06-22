import subprocess
import sys
import pathlib

print("Launching 8 parallel queries runner with robust decoding...")
python_exe = sys.executable or "python"
res = subprocess.run(
    [python_exe, "scratch/run_8_parallel.py"],
    capture_output=True
)

stdout = res.stdout.decode("utf-8", errors="replace")
stderr = res.stderr.decode("utf-8", errors="replace")

output_path = pathlib.Path("parallel_run_clean_new.log")
output_path.write_text(stdout + "\n" + stderr, encoding="utf-8")
print("Clean parallel queries output written to parallel_run_clean_new.log successfully.")
