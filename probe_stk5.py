import duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
conn = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)

# Build a small version of all_stocktrade_query with a few tickers
# First, see what columns the individual ticker tables have
tabs = conn.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema='main' LIMIT 5
""").fetchall()
print("Sample tables:", [t[0] for t in tabs])
first_tab = tabs[0][0]
print(f"\nColumns of '{first_tab}':")
cols = conn.execute(f'DESCRIBE "{first_tab}"').fetchdf()
print(cols[['column_name', 'column_type']].to_string())
print(f"\nSample rows:")
print(conn.execute(f'SELECT * FROM "{first_tab}" WHERE "Date" LIKE \'2017%\' LIMIT 3').fetchdf())

# Create the unified view ourselves
all_tabs = conn.execute("""
    SELECT table_name FROM information_schema.tables WHERE table_schema='main'
""").fetchall()
tab_names = [t[0] for t in all_tabs]
print(f"\nTotal tables: {len(tab_names)}")

# Check some known NYSE tickers exist as tables
nyse_tickers = ['AEFC', 'AIN', 'AIV', 'IBM', 'JNJ', 'GE', 'BA', 'JPM', 'WMT']
for t in nyse_tickers:
    exists = t in tab_names
    print(f"  {t}: {'EXISTS' if exists else 'MISSING'}")

# Build a small union of just a few tickers to test join
# Use column names from first table
col_names = cols['column_name'].tolist()
print(f"\nColumn names: {col_names}")

# Create the view for a small subset that includes _entity_name
select_parts = []
for t in tab_names[:10]:  # just first 10
    cols_q = ', '.join(f'"{c}"' for c in col_names)
    select_parts.append(f"SELECT {cols_q}, '{t}' AS _entity_name FROM \"{t}\"")

small_view_sql = "\nUNION ALL\n".join(select_parts)
conn.execute(f"CREATE OR REPLACE TEMP VIEW all_stocktrade_query AS {small_view_sql}")

# Attach stockinfo
conn2 = duckdb.connect(f'{base}/stocktrade_query.db')
conn2.execute("INSTALL sqlite; LOAD sqlite;")
si_path = f"{base}/stockinfo_query.db".replace("\\", "/")
conn2.execute(f"ATTACH '{si_path}' AS stockinfo_db (TYPE sqlite);")
conn2.execute('CREATE OR REPLACE TEMPORARY TABLE stockinfo AS SELECT * FROM stockinfo_db.stockinfo;')

# Recreate small view in conn2
conn2.execute(f"CREATE OR REPLACE TEMP VIEW all_stocktrade_query AS {small_view_sql}")

# Test the join
print("\n=== Join test ===")
result = conn2.execute("""
    SELECT DISTINCT stq._entity_name, si."Symbol", si."Listing Exchange", si."ETF"
    FROM all_stocktrade_query stq
    JOIN stockinfo si ON stq._entity_name = si."Symbol"
    LIMIT 10
""").fetchdf()
print(result)

conn.close()
conn2.close()
