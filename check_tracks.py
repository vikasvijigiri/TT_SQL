import sqlite3
for db_path in [
    r"C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset\tracks.db",
    r"C:\Users\VikasVijigiri\Documents\DataAgentBench\query_music_brainz_20k\query_dataset\tracks_query.db",
]:
    print(f"\n=== {db_path} ===")
    try:
        con = sqlite3.connect(db_path)
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print("Tables:", tables)
        for t in tables:
            name = t[0]
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})").fetchall()]
            print(f"  {name}: {cols}")
        con.close()
    except Exception as e:
        print(f"  ERROR: {e}")
