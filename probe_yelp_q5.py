import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'
conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/business.db' AS biz (TYPE sqlite)")

# Check business.db schema
biz_cols = conn.execute("PRAGMA biz.table_info('business')").fetchdf()
print("business columns:")
print(biz_cols[['name','type']].to_string())

# Check review schema
rev_cols = conn.execute("DESCRIBE review").fetchdf()
print("\nreview columns:")
print(rev_cols[['column_name','column_type']].to_string())

# Check PA WiFi businesses
pa_biz = conn.execute("""
    SELECT b.business_id, b.attributes,
           regexp_extract(b.description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) AS state
    FROM biz.business b
    WHERE b.attributes ILIKE '%"WiFi"%free%'
       OR b.attributes ILIKE '%"Wi-Fi"%free%'
       OR b.attributes ILIKE '%"wifi"%free%'
    HAVING state = 'PA'
""").fetchdf()
print(f"\nPA WiFi businesses: {len(pa_biz)}")
print(pa_biz.head())

# Check if business table has stars column
if 'stars' in biz_cols['name'].tolist():
    print("\nbusiness HAS stars column!")
    pa_stars = conn.execute("""
        SELECT b.stars, regexp_extract(b.description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) AS state
        FROM biz.business b
        WHERE b.attributes ILIKE '%"WiFi"%free%'
    """).fetchdf()
    print(pa_stars[pa_stars['state']=='PA'])
else:
    print("\nbusiness has NO stars column — must use review.rating")

conn.close()
