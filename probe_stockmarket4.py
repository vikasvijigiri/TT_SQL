import duckdb, sys
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'

conn = duckdb.connect(f'{base}/stocktrade_query.db', read_only=False)
conn.execute("LOAD sqlite")
conn.execute(f"ATTACH '{base}/stockinfo_query.db' AS si_db (TYPE sqlite)")
conn.execute('CREATE OR REPLACE TEMPORARY TABLE "stockinfo" AS SELECT * FROM "si_db"."stockinfo";')

# Get all NYSE non-ETF symbols
nyse_syms = conn.execute("SELECT \"Symbol\" FROM stockinfo WHERE \"Listing Exchange\"='N' AND \"ETF\"='N'").fetchdf()
syms = nyse_syms['Symbol'].tolist()
print(f"Total NYSE non-ETF symbols: {len(syms)}")

# Build UNION ALL for all of them
parts = []
for s in syms:
    parts.append(f"SELECT '{s}' AS _entity_name, \"Date\", \"Open\", \"Close\" FROM \"{s}\"")

union_sql = " UNION ALL ".join(parts)

# Full query
query = f"""
WITH all_daily AS (
    {union_sql}
),
updown_2017 AS (
    SELECT _entity_name,
           SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) AS up_days,
           SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) AS down_days
    FROM all_daily
    WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
    GROUP BY _entity_name
    HAVING SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) > SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END)
)
SELECT si."Company Description",
       u.up_days,
       u.down_days,
       (u.up_days - u.down_days) AS net_up
FROM updown_2017 u
JOIN stockinfo si ON si."Symbol" = u._entity_name
ORDER BY net_up DESC
LIMIT 10
"""

print("\n=== Top 10 NYSE non-ETF stocks by net up days in 2017 ===")
result = conn.execute(query).fetchdf()
print(result.to_string())

# Also get just the names (first 5)
print("\n=== Top 5 company names ===")
for i, row in result.head(5).iterrows():
    print(f"  {i+1}. {row['Company Description'][:100]}")

conn.close()
