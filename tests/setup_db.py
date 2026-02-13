import sqlite3
import os

os.makedirs('tests', exist_ok=True)
db_path = 'tests/dummy.db'

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')
c.execute("INSERT OR IGNORE INTO users VALUES (1, 'Alice', 30)")
c.execute("INSERT OR IGNORE INTO users VALUES (2, 'Bob', 25)")
conn.commit()
conn.close()
print(f'Dummy DB created at {db_path}')
