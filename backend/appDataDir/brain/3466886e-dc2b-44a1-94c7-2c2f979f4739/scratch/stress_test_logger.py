import threading
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(os.getcwd())))

from app.services.utils.logger import Logger

def stress_test_logger():
    test_file = "test_stress.md"
    Logger.bind_log_file(test_file)
    print(f"Stress testing logger on: {test_file}")
    
    def log_worker(worker_id):
        # We MUST bind here because Logger._storage is thread-local
        Logger.bind_log_file(test_file)
        for i in range(50):
            Logger.log(f"Worker {worker_id} - Log entry {i}")
            
    threads = []
    for i in range(10):
        t = threading.Thread(target=log_worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    print("Stress test complete. Checking file...")
    if os.path.exists(test_file):
        with open(test_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"Total lines logged: {len(lines)}")
        os.remove(test_file)
    else:
        print("ERROR: Test file not found")

if __name__ == "__main__":
    stress_test_logger()
