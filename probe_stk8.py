import sqlite3, duckdb

base = r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockmarket\query_dataset'

# Check what columns MFA Financial and ARGO use
conn = sqlite3.connect(f'{base}/stockinfo_query.db')
cursor = conn.cursor()

# Get ALL columns for MFA and ARGO
cursor.execute("PRAGMA table_info('stockinfo')")
cols = [c[1] for c in cursor.fetchall()]
print("All stockinfo columns:", cols)

for sym in ['MFA', 'ARGO', 'HDB', 'AIN', 'DTQ']:
    cursor.execute("SELECT * FROM stockinfo WHERE Symbol=?", (sym,))
    row = cursor.fetchone()
    if row:
        print(f"\n{sym}:")
        for c, v in zip(cols, row):
            print(f"  {c}: {v!r}")
    else:
        print(f"\n{sym}: NOT FOUND")

conn.close()

# Now check MFA and ARGO date ranges in stocktrade
print("\n=== MFA and ARGO in stocktrade ===")
conn2 = duckdb.connect(f'{base}/stocktrade_query.db', read_only=True)
for sym in ['MFA', 'ARGO']:
    try:
        row = conn2.execute(f"""
            SELECT MIN("Date"), MAX("Date"),
                   SUM(CASE WHEN "Close">"Open" THEN 1 ELSE 0 END) as up,
                   SUM(CASE WHEN "Close"<"Open" THEN 1 ELSE 0 END) as down
            FROM "{sym}"
            WHERE "Date" >= '2017-01-01' AND "Date" < '2018-01-01'
        """).fetchone()
        print(f"  {sym}: min={row[0]}, max={row[1]}, up={row[2]}, down={row[3]}")
    except Exception as e:
        print(f"  {sym}: {e}")
conn2.close()
