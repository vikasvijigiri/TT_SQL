import duckdb, sqlite3, os

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_DEPS_DEV_V1'

print("=== Files ===")
for f in os.listdir(base):
    full = os.path.join(base, f)
    if os.path.isfile(full):
        print(f"  {f}: {os.path.getsize(full)} bytes")
    elif os.path.isdir(full):
        print(f"  {f}/ (dir)")

print("\n=== DB config ===")
with open(os.path.join(base, 'db_config.yaml'), encoding='utf-8') as f:
    print(f.read())

# Check dataset files
ds_dir = os.path.join(base, 'query_dataset')
if os.path.exists(ds_dir):
    print("\n=== query_dataset files ===")
    for f in os.listdir(ds_dir):
        full = os.path.join(ds_dir, f)
        size = os.path.getsize(full)
        print(f"  {f}: {size//1024//1024}MB")

# Try to connect to the DB
for db_file in ['deps_dev.duckdb', 'deps.db', 'deps_dev.db']:
    path = os.path.join(ds_dir, db_file)
    if os.path.exists(path):
        print(f"\n=== {db_file} ===")
        try:
            # Check if SQLite first
            with open(path, 'rb') as fh:
                header = fh.read(16)
            if header[:16] == b'SQLite format 3\x00':
                conn = sqlite3.connect(path)
            else:
                conn = duckdb.connect(path, read_only=True)
            # Get tables
            try:
                tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
                print("Tables:", tabs['table_name'].tolist())
                for t in tabs['table_name'].tolist()[:3]:
                    cols = conn.execute(f'DESCRIBE "{t}"').fetchdf()
                    print(f"  {t}: {cols['column_name'].tolist()}")
                    print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf())
            except:
                pass
            conn.close()
        except Exception as e:
            print(f"Error: {e}")

# Ground truth q1
print("\n=== Q1 full ground truth ===")
with open(os.path.join(base, 'query1', 'ground_truth.csv'), encoding='utf-8') as f:
    print(f.read())
