import duckdb, sys, os, glob

# Test if SHOW ALL TABLES lists SQLite-attached tables
base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
si_path = f"{base}/stockinfo_query.db".replace("\\", "/")

# Mimick exactly what the executor does
conn = duckdb.connect(f'{base}/stocktrade_query.db')
print(f"Primary DuckDB opened (write mode)")
conn.execute("INSTALL sqlite; LOAD sqlite;")
alias = "stockinfo_query_db"
conn.execute(f"ATTACH IF NOT EXISTS '{si_path}' AS \"{alias}\" (TYPE sqlite);")
print("Attached as stockinfo_query_db")

# Test SHOW ALL TABLES
all_tabs = conn.execute("SHOW ALL TABLES;").fetchall()
print(f"\nSHOW ALL TABLES returned {len(all_tabs)} rows")
attached_aliases = {alias}
for row in all_tabs:
    db_alias = row[0]
    if db_alias in attached_aliases:
        t_name = row[2]
        print(f"  Found attached table: {db_alias}.{t_name}")

# Test information_schema
is_tabs = conn.execute("SELECT table_catalog, table_schema, table_name FROM information_schema.tables WHERE table_schema=?", [alias]).fetchall()
print(f"\ninformation_schema returned: {is_tabs}")

# Test if stockinfo exists and can create a temp view
try:
    conn.execute(f'CREATE OR REPLACE TEMPORARY TABLE "stockinfo" AS SELECT * FROM "{alias}"."stockinfo";')
    cnt = conn.execute("SELECT COUNT(*) FROM stockinfo").fetchone()[0]
    print(f"\nTemp table 'stockinfo' created with {cnt} rows")
except Exception as e:
    print(f"\nFailed to create temp table: {e}")

conn.close()

# Test is_sqlite_file for stockinfo_query.db
print("\n=== is_sqlite_file check ===")
f = f'{base}/stockinfo_query.db'
with open(f, 'rb') as fh:
    header = fh.read(16)
    is_sqlite = header[:16] == b'SQLite format 3\x00'
    print(f"Header bytes: {header[:16]}")
    print(f"Is SQLite: {is_sqlite}")

f2 = f'{base}/stocktrade_query.db'
with open(f2, 'rb') as fh:
    header2 = fh.read(16)
    print(f"\nstocktrade_query.db header: {header2[:16]}")
    print(f"Is SQLite: {header2[:16] == b'SQLite format 3\\x00'}")

# Check all .db files in the stockmarket dir
print("\n=== All .db files in stockmarket dir ===")
for ext in ("*.sqlite", "*.db", "*.sqlite3"):
    files = glob.glob(os.path.join(base, ext))
    for f in files:
        with open(f, 'rb') as fh:
            h = fh.read(16)
        is_sq = h[:16] == b'SQLite format 3\x00'
        print(f"  {os.path.basename(f)}: is_sqlite={is_sq}, size={os.path.getsize(f)//1024//1024}MB")
