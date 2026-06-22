import duckdb, sys, sqlite3
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'
conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/business.db' AS biz (TYPE sqlite)")

# Count all WiFi businesses with state=PA
print("=== WiFi filter variants for PA ===")

for wifi_filter in [
    "attributes ILIKE '%\"WiFi\"%free%'",
    "attributes ILIKE '%WiFi%'",
    "attributes LIKE '%WiFi%'",
]:
    r = conn.execute(f"""
        SELECT COUNT(*) as cnt
        FROM biz.business
        WHERE {wifi_filter}
          AND regexp_extract(description, '\\bin [^,]+,\\s*([A-Z]{{2}})\\b', 1) = 'PA'
    """).fetchone()
    print(f"  {wifi_filter}: {r[0]} businesses")

# Get PA WiFi businesses and their reviews
print("\n=== PA WiFi businesses and reviews ===")
r2 = conn.execute("""
    WITH wifi_biz AS (
        SELECT business_id, attributes
        FROM biz.business
        WHERE attributes ILIKE '%"WiFi"%free%'
          AND regexp_extract(description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) = 'PA'
    )
    SELECT wb.business_id,
           COUNT(rv.review_id) as review_count,
           AVG(rv.rating) as avg_rating
    FROM wifi_biz wb
    LEFT JOIN review rv ON REPLACE(rv.business_ref, 'businessref_', 'businessid_') = wb.business_id
    GROUP BY wb.business_id
""").fetchdf()
print(r2)
print(f"\nOverall avg: {r2['avg_rating'].mean():.4f}")
print(f"Total businesses: {len(r2)}, with reviews: {(r2['review_count']>0).sum()}")

# Try the expected result
print("\n=== Target query to get PA, 3.48 ===")
r3 = conn.execute("""
    SELECT
        regexp_extract(b.description, '\\bin [^,]+,\\s*([A-Z]{2})\\b', 1) AS state,
        COUNT(DISTINCT b.business_id) AS wifi_cnt,
        ROUND(AVG(rv.rating), 2) AS avg_rating
    FROM biz.business b
    JOIN review rv ON REPLACE(rv.business_ref, 'businessref_', 'businessid_') = b.business_id
    WHERE b.attributes ILIKE '%"WiFi"%free%'
    GROUP BY state
    HAVING state IS NOT NULL AND state != ''
    ORDER BY wifi_cnt DESC
    LIMIT 5
""").fetchdf()
print(r3)

conn.close()
