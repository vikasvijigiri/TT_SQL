import duckdb, os

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp'

# Read q5 question
with open(f'{base}/query5/query.json', encoding='utf-8', errors='replace') as f:
    print("=== Q5 question ===")
    print(f.read()[:300])
print("\n=== Q5 expected answer ===")
with open(f'{base}/query5/ground_truth.csv', encoding='utf-8') as f:
    print(f.read()[:300])

# Probe yelp DB
conn = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset\yelp.duckdb', read_only=True)
tabs = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print(f"\nYelp tables: {tabs['table_name'].tolist()}")

# Check business attributes for WiFi
biz_cols = conn.execute("DESCRIBE business").fetchdf()
print(f"\nBusiness columns: {biz_cols['column_name'].tolist()}")

# Check WiFi attribute format
wifi_sample = conn.execute("""
    SELECT business_id, name, attributes
    FROM business
    WHERE attributes IS NOT NULL
    AND attributes::TEXT LIKE '%WiFi%'
    LIMIT 3
""").fetchdf()
print("\nWiFi attribute sample:")
for _, row in wifi_sample.iterrows():
    print(f"  {row['business_id']}: {row['attributes'][:200] if row['attributes'] else 'NULL'}")

# Check review table join key
rev_cols = conn.execute("DESCRIBE review").fetchdf()
print(f"\nReview columns: {rev_cols['column_name'].tolist()}")

# Check WiFi free/paid patterns
print("\n=== WiFi values in attributes ===")
try:
    wifi_vals = conn.execute("""
        SELECT DISTINCT json_extract_string(attributes::JSON, '$.WiFi') as wifi_val
        FROM business
        WHERE attributes IS NOT NULL
        LIMIT 10
    """).fetchdf()
    print("json_extract_string approach:", wifi_vals['wifi_val'].tolist())
except Exception as e:
    print(f"json_extract_string error: {e}")

# Try ILIKE approach
try:
    wifi_free = conn.execute("""
        SELECT business_id, name
        FROM business
        WHERE attributes::TEXT ILIKE '%"WiFi":%free%'
           OR attributes::TEXT ILIKE '%wifi%free%'
        LIMIT 3
    """).fetchdf()
    print("ILIKE WiFi free:", wifi_free['name'].tolist())
except Exception as e:
    print(f"ILIKE error: {e}")

# What does a full attributes entry look like?
sample_attrs = conn.execute("""
    SELECT attributes FROM business WHERE attributes IS NOT NULL LIMIT 1
""").fetchone()
if sample_attrs:
    print(f"\nSample attributes (full): {sample_attrs[0][:500]}")

conn.close()
