import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset'

conn = duckdb.connect(f'{base}/sales.duckdb', read_only=True)
conn.execute(f"ATTACH '{base}/tracks.db' AS tdb (READ_ONLY)")

# Check various formulas
print("=== 5. COUNT(*) sales transactions ===")
df5 = conn.execute("""
    SELECT t.title, COUNT(*) as txns
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY txns DESC LIMIT 5
""").fetchdf()
print(df5)

print("\n=== 6. SUM(units_sold) * AVG(revenue_usd/units_sold) global price ===")
# Maybe: SUM(units_sold) × (total_global_revenue / total_global_units) -- normalized
df6 = conn.execute("""
    WITH global AS (SELECT SUM(revenue_usd) / NULLIF(SUM(units_sold),0) as avg_price FROM main.sales),
    per_track AS (
        SELECT t.title, SUM(s.units_sold) as units
        FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
        GROUP BY t.track_id, t.title
    )
    SELECT pt.title, pt.units * g.avg_price as norm_rev
    FROM per_track pt CROSS JOIN global g
    ORDER BY norm_rev DESC LIMIT 5
""").fetchdf()
print(df6)

print("\n=== 7. What is Zo gaat revenue by different metrics ===")
df7 = conn.execute("""
    SELECT t.title, SUM(s.revenue_usd) as sum_rev, SUM(s.units_sold) as sum_units,
           COUNT(*) as txns, AVG(s.revenue_usd) as avg_rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    WHERE t.title LIKE '%Zo gaat%'
    GROUP BY t.track_id, t.title
    ORDER BY sum_rev DESC
""").fetchdf()
print(df7)

# What if using tracks.db as base and joining sales?
print("\n=== 8. From tracks.db perspective - only counting tracks that exist in sales ===")
# source_id based revenue?
df8 = conn.execute("""
    SELECT t.title, t.source_id, SUM(s.revenue_usd) as rev
    FROM tdb.tracks t JOIN main.sales s ON t.track_id=s.track_id
    GROUP BY t.track_id, t.title, t.source_id ORDER BY rev DESC LIMIT 10
""").fetchdf()
print(df8)

# Check if "Zo gaat" appears in top by source_id
print("\n=== 9. Top by source_id grouping (source = store?) ===")
df9 = conn.execute("""
    SELECT t.title, t.source_id, COUNT(*) as sales_count, SUM(s.revenue_usd) as rev
    FROM tdb.tracks t JOIN main.sales s ON t.track_id=s.track_id
    WHERE t.title LIKE '%Zo gaat%'
    GROUP BY t.track_id, t.title, t.source_id ORDER BY rev DESC LIMIT 5
""").fetchdf()
print(df9)

print("\n=== 10. Try using COUNT(DISTINCT store) * SUM(revenue_usd) ===")
df10 = conn.execute("""
    SELECT t.title, COUNT(DISTINCT s.store) * SUM(s.revenue_usd) as rev
    FROM main.sales s JOIN tdb.tracks t ON s.track_id=t.track_id
    GROUP BY t.track_id, t.title ORDER BY rev DESC LIMIT 5
""").fetchdf()
print(df10)

conn.close()
