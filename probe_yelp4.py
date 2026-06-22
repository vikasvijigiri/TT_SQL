import duckdb, sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'

# Check yelp_user.db (DuckDB)
print("=== yelp_user.db ===")
try:
    conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
    tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
    print("Tables:", tabs['table_name'].tolist())
    for t in tabs['table_name'].tolist():
        cols = conn.execute(f'DESCRIBE "{t}"').fetchdf()
        print(f"\n  {t}: {cols['column_name'].tolist()}")
        print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf())
    conn.close()
except Exception as e:
    print(f"Error: {e}")

# Check business.db more carefully for rating
print("\n=== business.db full scan for rating ===")
conn2 = sqlite3.connect(f'{base}/business.db')
cursor = conn2.cursor()
cursor.execute("PRAGMA table_info('business')")
print("Columns:", [(c[1], c[2]) for c in cursor.fetchall()])

# Sample with WiFi free
cursor.execute("""
    SELECT name, description, attributes, review_count
    FROM business
    WHERE attributes LIKE '%"WiFi"%free%'
    LIMIT 5
""")
for row in cursor.fetchall():
    print(f"\n  {row[0]}")
    print(f"  desc: {row[1][:100]}")
    print(f"  attrs: {row[2][:100]}")
    print(f"  review_count: {row[3]}")

# Extract state and try to compute average rating from description
# Maybe rating is in description too?
cursor.execute("""
    SELECT description FROM business LIMIT 3
""")
for row in cursor.fetchall():
    print(f"\n  Full desc: {row[0]}")

conn2.close()

# Try to find reviews with ratings
print("\n=== review.json ===")
import json, os
review_path = f'{base}/review.json'
if os.path.exists(review_path):
    with open(review_path, encoding='utf-8', errors='replace') as f:
        content = json.load(f)
    if isinstance(content, dict):
        print("Keys:", list(content.keys()))
        if 'sample_rows' in content:
            print("Sample rows:", content['sample_rows'][:2])
        if 'column_names' in content:
            print("Columns:", content['column_names'])
    elif isinstance(content, list):
        print("List length:", len(content))
        print("First 2:", content[:2])
