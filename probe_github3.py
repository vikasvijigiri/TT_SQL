import sqlite3, duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_GITHUB_REPOS\query_dataset'
conn = sqlite3.connect(f'{base}/repo_metadata.db')
cursor = conn.cursor()

# Check language_description for expected repos
expected = ['apple/swift', 'twbs/bootstrap', 'Microsoft/vscode', 'facebook/react', 'tensorflow/tensorflow']
print("=== Language descriptions for expected repos ===")
for repo in expected:
    cursor.execute("SELECT language_description FROM languages WHERE repo_name=?", (repo,))
    row = cursor.fetchone()
    if row:
        print(f"\n{repo}:")
        print(f"  {row[0]}")
    else:
        print(f"\n{repo}: NOT FOUND")

# Check commit counts for expected repos
conn2 = duckdb.connect(f'{base}/repo_artifacts.db', read_only=True)
print("\n=== Commit counts for expected repos ===")
for repo in expected:
    try:
        cnt = conn2.execute(f'SELECT COUNT(*) FROM commits WHERE repo_name=?', [repo]).fetchone()[0]
        print(f"  {repo}: {cnt}")
    except Exception as e:
        print(f"  {repo}: error {e}")

# What's the actual top 5 non-python by commits?
print("\n=== Actual top 5 non-Python by commit count ===")
# First get all repos with language_description not containing 'python' as main lang
cursor.execute("SELECT repo_name, language_description FROM languages")
lang_rows = cursor.fetchall()

def get_main_lang(desc):
    import re
    # Match first language mentioned
    m = re.search(r'(?:includes:|written in )\s*([A-Za-z][A-Za-z+#]*)', desc)
    if m:
        return m.group(1)
    return desc[:20]

lang_dict = {r[0]: r[1] for r in lang_rows}
main_langs = {r: get_main_lang(d) for r, d in lang_dict.items()}

# Count where main lang != Python
non_python = {r: l for r, l in main_langs.items() if 'python' not in l.lower() and 'Python' not in l}

print(f"Non-Python repos: {len(non_python)} / {len(main_langs)}")

# Count commits
commit_counts = {}
try:
    df = conn2.execute("""
        SELECT repo_name, COUNT(*) as cnt
        FROM commits
        GROUP BY repo_name
        ORDER BY cnt DESC
        LIMIT 100
    """).fetchdf()
    for _, row in df.iterrows():
        commit_counts[row['repo_name']] = row['cnt']
except Exception as e:
    print(f"Commit count error: {e}")

# Find top 5 non-Python
results = [(r, c) for r, c in commit_counts.items() if r in non_python]
results.sort(key=lambda x: -x[1])
print("\nTop 10 non-Python by commits:")
for r, c in results[:10]:
    print(f"  {r}: {c} commits, main_lang={main_langs.get(r,'?')}")

conn.close()
conn2.close()
