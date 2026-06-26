import sqlite3

db = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_bookreview/query_dataset/review_query.db'
conn = sqlite3.connect(db)
for (tbl,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    cols = [(c[1], c[2]) for c in conn.execute(f'PRAGMA table_info({tbl})').fetchall()]
    cnt = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
    print(f"TABLE {tbl} ({cnt} rows): {cols}")
    rows = conn.execute(f"SELECT * FROM {tbl} LIMIT 2").fetchall()
    for r in rows:
        print(f"  {r}")

# Try the expected SQL for decade grouping
print("\n=== decade query test ===")
try:
    rows = conn.execute("""
        SELECT CAST(CAST(SUBSTR(review_time, 1, 4) AS INTEGER) / 10 * 10 AS TEXT) || 's' AS decade,
               AVG(CAST(rating AS FLOAT)) AS avg_rating,
               COUNT(DISTINCT book_id) AS distinct_books
        FROM review
        GROUP BY decade
        HAVING COUNT(DISTINCT book_id) >= 10
        ORDER BY avg_rating DESC
        LIMIT 3
    """).fetchall()
    for r in rows:
        print(f"  {r}")
except Exception as e:
    print(f"Error: {e}")
    # Try without column names
    try:
        rows2 = conn.execute("SELECT * FROM review LIMIT 2").fetchall()
        print(f"  review sample: {rows2}")
    except Exception as e2:
        print(f"  error2: {e2}")

conn.close()
