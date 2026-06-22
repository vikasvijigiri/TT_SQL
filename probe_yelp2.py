import sqlite3, json

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'

# Connect to business.db (SQLite)
conn = sqlite3.connect(f'{base}/business.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables in business.db:", tables)

for t in tables:
    cursor.execute(f"PRAGMA table_info('{t}')")
    cols = [c[1] for c in cursor.fetchall()]
    print(f"  {t}: {cols}")
    cursor.execute(f"SELECT * FROM '{t}' LIMIT 2")
    print(f"  Sample: {cursor.fetchall()}")

conn.close()

# Check yelp_user.db
conn2 = sqlite3.connect(f'{base}/yelp_user.db')
cursor2 = conn2.cursor()
cursor2.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables2 = [t[0] for t in cursor2.fetchall()]
print(f"\nTables in yelp_user.db: {tables2}")
for t in tables2[:3]:
    cursor2.execute(f"PRAGMA table_info('{t}')")
    cols = [c[1] for c in cursor2.fetchall()]
    print(f"  {t}: {cols}")
conn2.close()

# Check yelp_business.db
conn3 = sqlite3.connect(f'{base}/yelp_business.db')
cursor3 = conn3.cursor()
cursor3.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables3 = [t[0] for t in cursor3.fetchall()]
print(f"\nTables in yelp_business.db: {tables3}")
for t in tables3[:3]:
    cursor3.execute(f"PRAGMA table_info('{t}')")
    cols = [c[1] for c in cursor3.fetchall()]
    print(f"  {t}: {cols}")
    cursor3.execute(f"SELECT * FROM '{t}' LIMIT 3")
    print(f"  Sample: {cursor3.fetchall()}")
conn3.close()

# Read business.json to understand attributes format
print("\n=== business.json sample ===")
with open(f'{base}/business.json', encoding='utf-8') as f:
    content = json.load(f)
    print(type(content))
    if isinstance(content, list):
        print(content[:2])
    elif isinstance(content, dict):
        print(str(content)[:500])
