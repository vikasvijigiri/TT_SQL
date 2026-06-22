import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'

conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute(f"ATTACH '{base}/tracks.db' AS tdb (READ_ONLY)")

# Try many formulas to find "Zo gaat het leven aan je voor"
target = "Zo gaat het leven aan je voor"

print("=== 1. SUM(revenue_usd) - current approach ===")
df1 = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 10
""").fetchdf()
print(df1)
print(f"Target in top10: {target in df1['title'].tolist()}")

print("\n=== 2. SUM(units_sold * unit_price) where unit_price=revenue_usd/units_sold ===")
# This should be same as SUM(revenue_usd) per-row but let's verify
df2 = conn.execute("""
    SELECT t.title, SUM(CAST(s.units_sold AS DOUBLE) * (s.revenue_usd / NULLIF(s.units_sold,0))) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 5
""").fetchdf()
print(df2.head())

print("\n=== 3. SUM(units_sold) (unit count, not revenue) ===")
df3 = conn.execute("""
    SELECT t.title, SUM(s.units_sold) as units
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY units DESC LIMIT 10
""").fetchdf()
print(df3)
print(f"Target in top10: {target in df3['title'].tolist()}")

print("\n=== 4. COUNT(distinct countries) * SUM(revenue_usd) ===")
df4 = conn.execute("""
    SELECT t.title, COUNT(DISTINCT s.country) * SUM(s.revenue_usd) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 5
""").fetchdf()
print(df4.head())

# Find where target appears
print(f"\n=== Find '{target}' rank ===")
df5 = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as rev,
           RANK() OVER (ORDER BY SUM(s.revenue_usd) DESC) as rnk
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title
""").fetchdf()
target_rows = df5[df5['title'].str.contains('Zo gaat', na=False)]
print("Target rows:", target_rows)

conn.close()
