import duckdb, sqlite3

# --- STOCKMARKET ---
print("=== STOCKMARKET ===")
conn = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset\stocktrade_query.db', read_only=True)
tabs = conn.execute("SELECT table_name FROM information_schema.tables").fetchdf()
print("Tables:", tabs['table_name'].tolist())
for t in tabs['table_name'].tolist():
    try:
        cols = conn.execute(f'DESCRIBE "{t}"').fetchdf()[['column_name','column_type']]
        print(f"\n-- {t} --\n{cols}")
        print(conn.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchdf())
    except Exception as e:
        print(f"Error {t}: {e}")

print("\nTop 5 non-ETF stocks by name:")
try:
    print(conn.execute("""
        SELECT name, symbol FROM all_stocktrade_query
        WHERE is_etf = false OR is_etf IS NULL OR lower(type) != 'etf'
        LIMIT 5
    """).fetchdf())
except Exception as e:
    print(f"Error: {e}")
conn.close()

# --- CRMARENAPRO ---
print("\n=== CRMARENAPRO ===")
conn2 = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_crmarenapro\query_dataset\sales_pipeline.duckdb', read_only=True)
tabs2 = conn2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print("Tables:", tabs2['table_name'].tolist())
for t in tabs2['table_name'].tolist():
    try:
        cols = conn2.execute(f'DESCRIBE "{t}"').fetchdf()[['column_name','column_type']]
        print(f"\n-- {t} --\n{cols}")
        # Show Field__c values if exists
        field_cols = [c for c in cols['column_name'].tolist() if 'ield' in c or 'Type' in c or 'Stage' in c]
        for fc in field_cols[:3]:
            try:
                vals = conn2.execute(f'SELECT DISTINCT "{fc}" FROM "{t}" LIMIT 15').fetchdf()
                print(f"  {fc}: {vals[fc].tolist()}")
            except:
                pass
    except Exception as e:
        print(f"Error {t}: {e}")
conn2.close()

# --- GITHUB REPOS language values ---
print("\n=== GITHUB REPOS - language values ===")
conn3 = duckdb.connect(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_GITHUB_REPOS\query_dataset\repo_artifacts.db', read_only=True)
tabs3 = conn3.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchdf()
print("Tables:", tabs3['table_name'].tolist())
for t in tabs3['table_name'].tolist():
    try:
        cols = conn3.execute(f'DESCRIBE "{t}"').fetchdf()[['column_name','column_type']]
        print(f"\n-- {t} --")
        lang_cols = [c for c in cols['column_name'].tolist() if 'lang' in c.lower() or 'language' in c.lower()]
        print(f"Language cols: {lang_cols}")
        for lc in lang_cols[:2]:
            vals = conn3.execute(f'SELECT DISTINCT "{lc}" FROM "{t}" LIMIT 20').fetchdf()
            print(f"  {lc}: {vals[lc].tolist()}")
    except Exception as e:
        print(f"Error {t}: {e}")

# Try the q4 query
print("\nTop 5 Java repos:")
try:
    print(conn3.execute("""
        SELECT name, stargazers_count, primary_language
        FROM repos WHERE primary_language = 'Java' OR primary_language = 'java'
        ORDER BY stargazers_count DESC LIMIT 5
    """).fetchdf())
except Exception as e:
    print(f"Error: {e}")
    # Try generic
    for t in tabs3['table_name'].tolist():
        try:
            cols = conn3.execute(f'DESCRIBE "{t}"').fetchdf()['column_name'].tolist()
            if any('star' in c.lower() for c in cols):
                print(f"\nFound star cols in {t}: {[c for c in cols if 'star' in c.lower()]}")
                star_col = next(c for c in cols if 'star' in c.lower())
                print(conn3.execute(f'SELECT * FROM "{t}" ORDER BY "{star_col}" DESC LIMIT 3').fetchdf())
                break
        except:
            pass
conn3.close()
