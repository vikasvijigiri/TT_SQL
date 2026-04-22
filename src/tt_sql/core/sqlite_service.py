import sqlite3
from typing import Dict, Any, List

class SQLiteService:
    """
    Service to interact with local SQLite databases for schema extraction.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_full_schema(self) -> Dict[str, Any]:
        """
        Extracts the complete schema from the SQLite database.
        Returns a dictionary mapping table names to their column definitions.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info('{table}')")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "column_name": col[1],
                        "type": col[2],
                        "pk": bool(col[5]),
                        "description": "" # SQLite doesn't store descriptions easily in pragma
                    })
                
                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list('{table}')")
                fks = []
                for fk in cursor.fetchall():
                    fks.append({
                        "column": fk[3],
                        "referred_table": fk[2],
                        "referred_column": fk[4]
                    })
                
                schema[table] = {
                    "columns": columns,
                    "foreign_keys": fks
                }
            
            conn.close()
            return schema
        except Exception as e:
            print(f"Error extracting SQLite schema: {e}")
            return {}
