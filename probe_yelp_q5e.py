import duckdb, sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_yelp\query_dataset'
conn = duckdb.connect(f'{base}/yelp_user.db', read_only=True)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/business.db' AS biz (TYPE sqlite)")

# Replicate the exact agent SQL
print("=== Agent SQL (exact) ===")
r = conn.execute(r"""
    SELECT REGEXP_EXTRACT(b.description, ',\s*([A-Z]{2})[\s,\.]', 1) AS state,
           AVG(r.rating::DOUBLE) AS avg_rating,
           COUNT(DISTINCT b.business_id) as biz_cnt
    FROM "biz"."business" b
    JOIN "review" r ON REPLACE(r.business_ref, 'businessref_', 'businessid_') = b.business_id
    WHERE (b.attributes ILIKE '%"WiFi"%free%' OR b.attributes ILIKE '%"WiFi"%paid%')
      AND b.attributes NOT ILIKE '%"WiFi"%no%'
      AND b.attributes NOT ILIKE '%"WiFi"%None%'
      AND REGEXP_EXTRACT(b.description, ',\s*([A-Z]{2})[\s,\.]', 1) != ''
    GROUP BY state
    ORDER BY biz_cnt DESC
    LIMIT 5
""").fetchdf()
print(r)

# Check what the NOT ILIKE excludes
print("\n=== PA WiFi businesses excluded by NOT filter ===")
r2 = conn.execute(r"""
    SELECT business_id, attributes
    FROM biz.business b
    WHERE b.attributes ILIKE '%"WiFi"%free%'
      AND REGEXP_EXTRACT(b.description, ',\s*([A-Z]{2})[\s,\.]', 1) = 'PA'
      AND (b.attributes ILIKE '%"WiFi"%no%' OR b.attributes ILIKE '%"WiFi"%None%')
""").fetchdf()
print(f"PA 'free' WiFi businesses excluded by NOT filter: {len(r2)}")
if len(r2) > 0:
    for _, row in r2.iterrows():
        print(f"  {row['business_id']}: {row['attributes'][:200]}")

# Count how many PA WiFi businesses the agent's filter finds
print("\n=== Agent filter PA businesses ===")
r3 = conn.execute(r"""
    SELECT COUNT(DISTINCT b.business_id) as cnt
    FROM biz.business b
    WHERE (b.attributes ILIKE '%"WiFi"%free%' OR b.attributes ILIKE '%"WiFi"%paid%')
      AND b.attributes NOT ILIKE '%"WiFi"%no%'
      AND b.attributes NOT ILIKE '%"WiFi"%None%'
      AND REGEXP_EXTRACT(b.description, ',\s*([A-Z]{2})[\s,\.]', 1) = 'PA'
""").fetchone()
print(f"PA WiFi count with agent filter: {r3[0]}")

conn.close()
