import sqlite3

conn = sqlite3.connect('C:/Users/VikasVijigiri/Documents/DataAgentBench/query_agnews/query_dataset/articles.db')

# What is THE globally longest description?
rows = conn.execute("""
    SELECT article_id, title, LENGTH(description) as dlen
    FROM articles ORDER BY dlen DESC LIMIT 5
""").fetchall()
print("=== Top 5 longest descriptions overall ===")
for r in rows:
    print(f"  id={r[0]} len={r[2]} title='{r[1]}'")

# Is there a category signal in the description? Check for "Sports" literal
rows2 = conn.execute("""
    SELECT COUNT(*) FROM articles
    WHERE description LIKE 'Sports -%' OR title LIKE 'Sports -%'
""").fetchone()
print(f"\nArticles starting with 'Sports -': {rows2[0]}")

# Check the description for articles with "Rundown" - look for category prefix
rows3 = conn.execute("""
    SELECT article_id, title, description FROM articles
    WHERE title = 'The Rundown'
    ORDER BY LENGTH(description) DESC LIMIT 3
""").fetchall()
for r in rows3:
    print(f"\nid={r[0]} len={len(r[2])} desc[:50]='{r[2][:50]}'")

# Does description start with category?
rows4 = conn.execute("SELECT DISTINCT SUBSTR(description, 1, 30) FROM articles LIMIT 10").fetchall()
print("\n=== First 30 chars of descriptions ===")
for r in rows4:
    print(f"  '{r[0]}'")

conn.close()
