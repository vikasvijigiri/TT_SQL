import duckdb, sqlite3

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'
conn = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)

# Check date ranges for NYSE non-ETF stocks
nyse_exists = ['AEFC', 'AIN', 'AIV', 'IBM']

for t in nyse_exists:
    try:
        row = conn.execute(f"""
            SELECT MIN("Date"), MAX("Date"), COUNT(*)
            FROM "{t}"
        """).fetchone()
        print(f"  {t}: min={row[0]}, max={row[1]}, rows={row[2]}")
        # Sample 2017
        cnt2017 = conn.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "Date" >= \'2017-01-01\' AND "Date" < \'2018-01-01\'').fetchone()[0]
        print(f"         2017 rows: {cnt2017}")
    except Exception as e:
        print(f"  {t}: error {e}")

# Find any NYSE non-ETF ticker that has 2017 data
# Load NYSE non-ETF symbols from stockinfo
conn2 = sqlite3.connect(f'{base}/stockinfo_query.db')
nyse_symbols = [row[0] for row in conn2.execute(
    "SELECT Symbol FROM stockinfo WHERE \"Listing Exchange\"='N' AND ETF='N'"
).fetchall()]
conn2.close()
print(f"\nTotal NYSE non-ETF symbols: {len(nyse_symbols)}")

# Check which ones exist as tables AND have 2017 data
has_2017 = []
tabs_all = set(t[0] for t in conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
).fetchall())

for sym in nyse_symbols[:50]:
    if sym not in tabs_all:
        continue
    try:
        cnt = conn.execute(f'SELECT COUNT(*) FROM "{sym}" WHERE "Date" >= \'2017-01-01\' AND "Date" < \'2018-01-01\'').fetchone()[0]
        if cnt > 0:
            has_2017.append((sym, cnt))
    except:
        pass

print(f"\nNYSE non-ETF symbols with 2017 data (first 50 checked): {len(has_2017)}")
if has_2017:
    print("Sample:", has_2017[:5])
    # Run the actual query for these
    for sym, cnt in has_2017[:3]:
        ud = conn.execute(f"""
            SELECT
                SUM(CASE WHEN "Close" > "Open" THEN 1 ELSE 0 END) as up_days,
                SUM(CASE WHEN "Close" < "Open" THEN 1 ELSE 0 END) as down_days
            FROM "{sym}"
            WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
        """).fetchone()
        print(f"  {sym}: up={ud[0]}, down={ud[1]}")
else:
    print("No NYSE non-ETF stocks have 2017 data in the first 50 checked")
    # What year range is in the whole DB?
    first = nyse_symbols[0]
    if first in tabs_all:
        r = conn.execute(f'SELECT MIN("Date"), MAX("Date") FROM "{first}"').fetchone()
        print(f"  {first} date range: {r[0]} to {r[1]}")

conn.close()
