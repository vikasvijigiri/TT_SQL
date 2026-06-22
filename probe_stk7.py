import duckdb, sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
conn = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)

# Load NYSE non-ETF symbols that have 2017 data
conn2 = sqlite3.connect(f'{base}/stockinfo_query.db')
cursor = conn2.cursor()
cursor.execute('SELECT Symbol, "Listing Exchange", ETF, "Company Description" FROM stockinfo WHERE "Listing Exchange"=\'N\' AND ETF=\'N\'')
stockinfo = {row[0]: row[3] for row in cursor.fetchall()}
conn2.close()
print(f"NYSE non-ETF symbols: {len(stockinfo)}")

# Build unified view for all NYSE non-ETF stocks that exist in DB
tabs_all = set(t[0] for t in conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
).fetchall())

results = []
for sym, company in stockinfo.items():
    if sym not in tabs_all:
        continue
    try:
        row = conn.execute(f"""
            SELECT
                SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) as up_days,
                SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) as down_days
            FROM "{sym}"
            WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
        """).fetchone()
        if row and row[0] is not None and row[0] > row[1]:
            results.append((sym, company, row[0], row[1]))
    except:
        pass

print(f"\nNYSE non-ETF stocks with more up than down days in 2017: {len(results)}")
results.sort(key=lambda x: -x[2])  # sort by up_days desc
for r in results[:10]:
    print(f"  {r[0]}: {r[2]} up / {r[3]} down — {r[1][:60]}")
print("\nThe answer (company names, ordered by up days):")
for r in results[:5]:
    print(f"  {r[1][:80]}")
