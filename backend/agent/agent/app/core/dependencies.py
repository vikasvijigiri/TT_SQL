from concurrent.futures import ThreadPoolExecutor

EXECUTION_POOL = ThreadPoolExecutor(max_workers=8)
