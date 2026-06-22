import sqlite3, os

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'

# Check yelp_business.db (tiny 12KB file)
print("=== yelp_business.db ===")
try:
    conn = sqlite3.connect(f'{base}/yelp_business.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print("Tables:", tables)
    for t in tables:
        cursor.execute(f"PRAGMA table_info('{t}')")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"  {t}: {cols}")
        cursor.execute(f"SELECT * FROM '{t}' LIMIT 3")
        print(f"  Sample: {cursor.fetchall()}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")

# Check checkin.db
print("\n=== checkin.db ===")
try:
    conn2 = sqlite3.connect(f'{base}/checkin.db')
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables2 = [t[0] for t in cursor2.fetchall()]
    print("Tables:", tables2)
    for t in tables2[:2]:
        cursor2.execute(f"PRAGMA table_info('{t}')")
        cols = [c[1] for c in cursor2.fetchall()]
        print(f"  {t}: {cols}")
        cursor2.execute(f"SELECT * FROM '{t}' LIMIT 3")
        print(f"  Sample: {cursor2.fetchall()}")
    conn2.close()
except Exception as e:
    print(f"Error: {e}")

# Check yelp_business folder
print("\n=== yelp_business folder ===")
yelp_biz_folder = os.path.join(base, 'yelp_business')
if os.path.exists(yelp_biz_folder):
    for f in os.listdir(yelp_biz_folder)[:5]:
        full = os.path.join(yelp_biz_folder, f)
        print(f"  {f}: {os.path.getsize(full)} bytes")
        # Check if it's the MongoDB dump
        if f.endswith('.json') or f.endswith('.bson'):
            with open(full, 'rb') as fh:
                print(f"  First 100 bytes: {fh.read(100)}")

# Check business.json format
print("\n=== business.json format ===")
try:
    with open(f'{base}/business.json', encoding='utf-8', errors='replace') as f:
        content = f.read(1000)
        print(content[:500])
except Exception as e:
    print(f"Error: {e}")

# What columns does business table have vs what's needed
print("\n=== Business table WiFi and state analysis ===")
conn = sqlite3.connect(f'{base}/business.db')
cursor = conn.cursor()

# Find WiFi free businesses
cursor.execute("""
    SELECT COUNT(*) FROM business
    WHERE attributes LIKE '%"WiFi"%free%'
""")
print(f"WiFi free businesses: {cursor.fetchone()[0]}")

# Extract state from description
cursor.execute("""
    SELECT description FROM business LIMIT 3
""")
for row in cursor.fetchall():
    print(f"  Description: {row[0][:100]}")

# Try to extract state from description
cursor.execute("""
    SELECT
        CASE
            WHEN description LIKE '%, __%' THEN
                TRIM(SUBSTR(description, INSTR(description, ', ') + 2, 2))
        END as state,
        COUNT(*) as cnt
    FROM business
    WHERE attributes LIKE '%"WiFi"%free%'
       OR attributes LIKE '%WiFi%u' || '''' || 'free%'
    GROUP BY state
    ORDER BY cnt DESC
    LIMIT 5
""")
print("States:", cursor.fetchall())

conn.close()
