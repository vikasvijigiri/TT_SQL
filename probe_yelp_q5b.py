import duckdb, sys, sqlite3
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'

# Check business.db schema
conn2 = sqlite3.connect(f'{base}/business.db')
cur = conn2.cursor()
cur.execute("PRAGMA table_info('business')")
biz_cols = [c[1] for c in cur.fetchall()]
print(f"business columns: {biz_cols}")
conn2.close()

conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/business.db' AS biz (TYPE sqlite)")

# Check if business has stars
if 'stars' in biz_cols:
    print("\nbusiness HAS stars column!")
else:
    print("\nbusiness has NO stars column")

# Check review columns
r = conn.execute("SELECT column_name, column_type FROM information_schema.columns WHERE table_name='review'").fetchdf()
print(f"\nreview columns: {r.to_string()}")

# Get PA WiFi businesses with avg rating from review
print("\n=== PA WiFi businesses avg review rating ===")
r2 = conn.execute("""
    SELECT
        regexp_extract(b.description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) AS state,
        COUNT(DISTINCT b.business_id) AS wifi_biz_count,
        AVG(rv.rating) AS avg_rating
    FROM biz.business b
    JOIN review rv ON REPLACE(rv.business_ref, 'businessref_', 'businessid_') = b.business_id
    WHERE b.attributes ILIKE '%"WiFi"%free%'
      OR b.attributes ILIKE '%WiFi%u''free%'
    GROUP BY state
    HAVING state IS NOT NULL AND state != ''
    ORDER BY wifi_biz_count DESC, avg_rating DESC
    LIMIT 5
""").fetchdf()
print(r2)

# Try ILIKE '%WiFi%'
print("\n=== Any WiFi mention ===")
r3 = conn.execute("""
    SELECT
        regexp_extract(b.description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) AS state,
        COUNT(DISTINCT b.business_id) AS wifi_biz_count,
        AVG(rv.rating) AS avg_rating
    FROM biz.business b
    JOIN review rv ON REPLACE(rv.business_ref, 'businessref_', 'businessid_') = b.business_id
    WHERE b.attributes ILIKE '%"WiFi"%'
    GROUP BY state
    HAVING state IS NOT NULL AND state != ''
    ORDER BY wifi_biz_count DESC
    LIMIT 5
""").fetchdf()
print(r3)

conn.close()
