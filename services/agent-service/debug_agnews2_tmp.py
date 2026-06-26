import sqlite3
db = 'C:/Users/VikasVijigiri/Documents/DataAgentBench/query_agnews/query_dataset/articles.db'
conn = sqlite3.connect(db)

# Top 10 globally longest articles
print("=== Globally longest articles ===")
rows = conn.execute("SELECT article_id, title, LENGTH(description) as l FROM articles ORDER BY l DESC LIMIT 10").fetchall()
for r in rows: print(f"  id={r[0]} title='{r[1]}' len={r[2]}")

# What position is The Rundown 69413 at?
cnt = conn.execute("SELECT COUNT(*) FROM articles WHERE LENGTH(description) > 841").fetchone()[0]
print(f"\nArticles longer than The Rundown 69413 (841 chars): {cnt}")

# What's at offset 50%?
row50 = conn.execute("SELECT title, SUBSTR(description,1,80) FROM articles LIMIT 3 OFFSET 63800").fetchall()
print("\n=== Offset 63800 (50%) sample ===")
for r in row50: print(f"  title='{r[0]}' desc='{r[1]}'")

# Does The Rundown 69413 contain "football"?
r = conn.execute("SELECT SUBSTR(description,1,200) FROM articles WHERE article_id=69413").fetchone()
print(f"\n=== The Rundown id=69413 description ===")
print(f"  {r[0]}")
conn.close()
