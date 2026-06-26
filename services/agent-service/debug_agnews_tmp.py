import sqlite3
db = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_agnews/query_dataset/articles.db'
conn = sqlite3.connect(db)

# What prefix does The Rundown have?
rows = conn.execute("SELECT article_id, SUBSTR(description,1,100) FROM articles WHERE title='The Rundown' LIMIT 3").fetchall()
print("=== The Rundown prefix ===")
for r in rows: print(f"  id={r[0]}: {repr(r[1])}")

# Count Sports Network
cnt1 = conn.execute("SELECT COUNT(*) FROM articles WHERE description LIKE '%(Sports Network)%'").fetchone()[0]
print(f"\nSports Network articles: {cnt1}")

# Does The Rundown have Sports Network?
cnt2 = conn.execute("SELECT COUNT(*) FROM articles WHERE title='The Rundown' AND description LIKE '%(Sports Network)%'").fetchone()[0]
print(f"The Rundown + Sports Network: {cnt2}")

# Longest Sports Network article
rows2 = conn.execute("SELECT title, LENGTH(description) as l FROM articles WHERE description LIKE '%(Sports Network)%' ORDER BY l DESC LIMIT 5").fetchall()
print("\n=== Longest Sports Network articles ===")
for r in rows2: print(f"  title='{r[0]}' len={r[1]}")

# What is The Rundown's description length?
rows3 = conn.execute("SELECT article_id, title, LENGTH(description) as l FROM articles WHERE title='The Rundown' ORDER BY l DESC LIMIT 3").fetchall()
print("\n=== The Rundown length ===")
for r in rows3: print(f"  id={r[0]} len={r[2]}")

# What common prefix do ESPN/College football articles have?
rows4 = conn.execute("""
    SELECT SUBSTR(description,1,30), COUNT(*) as cnt FROM articles
    WHERE description LIKE '%ESPN%' OR description LIKE '%college football%' OR description LIKE '%Rundown%'
    GROUP BY 1 ORDER BY cnt DESC LIMIT 10
""").fetchall()
print("\n=== ESPN/football description prefixes ===")
for r in rows4: print(f"  '{r[0]}' => {r[1]}")
conn.close()
