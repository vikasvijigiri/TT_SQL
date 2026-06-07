import duckdb, sqlite3
from pathlib import Path

base = Path(r'C:\Users\VikasVijigiri\Documents\DataAgentBench\query_stockindex\query_dataset')

print('=== indextrade_query.db (DuckDB) ===')
try:
    c = duckdb.connect(str(base / 'indextrade_query.db'), read_only=True)
    for row in c.execute('SHOW TABLES').fetchall():
        t = row[0]
        cols = c.execute('SELECT column_name FROM information_schema.columns WHERE table_name = ?', [t]).fetchall()
        print(f'  {t}: {[r[0] for r in cols]}')
    c.close()
except Exception as e:
    print(f'  ERROR: {e}')

print('=== indexInfo_query.db (SQLite) ===')
try:
    c = sqlite3.connect(str(base / 'indexInfo_query.db'))
    sql = "SELECT name FROM sqlite_master WHERE type='table'"
    tables = [r[0] for r in c.execute(sql).fetchall()]
    for t in tables:
        cols = [r[1] for r in c.execute(f'PRAGMA table_info({t})').fetchall()]
        print(f'  {t}: {cols}')
    c.close()
except Exception as e:
    print(f'  ERROR: {e}')
