import subprocess
import sys
import pathlib

print("Launching combined benchmark queries and system diagnostics...")
python_exe = sys.executable or "python"

# 1. Run 8 parallel queries
print("Running 8 parallel benchmark queries...")
res_queries = subprocess.run(
    [python_exe, "scratch/run_8_parallel.py"],
    capture_output=True
)
stdout_queries = res_queries.stdout.decode("utf-8", errors="replace")
stderr_queries = res_queries.stderr.decode("utf-8", errors="replace")

# 2. Run comprehensive simulation / diagnostics
print("Running system components diagnostics...")
res_sim = subprocess.run(
    [python_exe, "scratch/run_comprehensive_simulation.py"],
    capture_output=True
)
stdout_sim = res_sim.stdout.decode("utf-8", errors="replace")
stderr_sim = res_sim.stderr.decode("utf-8", errors="replace")

# Combine logs
combined_stdout = stdout_queries + "\n" + "="*50 + "\nDIAGNOSTICS & SIMULATION RUNS\n" + "="*50 + "\n" + stdout_sim
combined_stderr = stderr_queries + "\n" + stderr_sim

# Write to parallel_run_clean_new.log
output_path = pathlib.Path("parallel_run_clean_new.log")
output_path.write_text(combined_stdout + "\n" + combined_stderr, encoding="utf-8")
print("Combined parallel query execution & diagnostics output written to parallel_run_clean_new.log successfully.")
