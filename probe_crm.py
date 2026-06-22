import duckdb, sqlite3, os

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset'

# Explore CRM DB structure
print("=== CRM DuckDB files ===")
import glob
dbs = glob.glob(os.path.join(base, '*.duckdb')) + glob.glob(os.path.join(base, '*.db'))
print(dbs)

# Connect to main DuckDB
for db_path in [os.path.join(base, 'sales_pipeline.duckdb'),
                os.path.join(base, 'crm.db'),
                os.path.join(base, 'crm.duckdb')]:
    if os.path.exists(db_path):
        conn = duckdb.connect(db_path, read_only=True)
        tabs = conn.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
        print(f"\n{os.path.basename(db_path)} tables: {tabs['table_name'].tolist()}")

        # Check Case and CaseHistory tables
        for t in tabs['table_name'].tolist():
            cols = conn.execute(f'DESCRIBE "{t}"').fetchdf()
            print(f"\n  {t}: {cols['column_name'].tolist()[:12]}")

        conn.close()
        break

# Check SQLite files
print("\n=== SQLite files ===")
for f in os.listdir(base):
    full = os.path.join(base, f)
    if os.path.isfile(full) and not f.endswith('.duckdb'):
        try:
            with open(full, 'rb') as fh:
                if fh.read(16) == b'SQLite format 3\x00':
                    conn = sqlite3.connect(full)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [t[0] for t in cursor.fetchall()]
                    print(f"\n{f}: {tables}")
                    for t in tables[:5]:
                        cursor.execute(f"PRAGMA table_info('{t}')")
                        cols = [c[1] for c in cursor.fetchall()]
                        print(f"  {t}: {cols[:15]}")
                        # Show sample for CaseHistory
                        if 'Case' in t or 'History' in t:
                            cursor.execute(f"SELECT * FROM '{t}' LIMIT 2")
                            print(f"  Sample: {cursor.fetchall()}")
                    conn.close()
        except:
            pass
