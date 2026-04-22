import sqlite3
import time
from typing import Any

from core.state import ExecutionResult


class SQLiteService:
    """
    Service to interact with local SQLite databases for schema extraction and query execution.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute_query(self, query: str, sampling: bool = False) -> ExecutionResult:
        """Executes a query and returns an ExecutionResult object."""
        start_t = time.time()
        result = ExecutionResult()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Final sanity check: must start with SELECT, WITH, etc.
            if not any(
                query.upper().strip().startswith(kw)
                for kw in ["SELECT", "WITH", "PRAGMA", "EXPLAIN"]
            ):
                raise sqlite3.Error(
                    f"String does not appear to be a valid SQL command: '{query[:50]}...'"
                )

            cursor.execute(query)

            # Fetch columns
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]

            # Fetch rows
            if sampling:
                rows = cursor.fetchmany(5)
            else:
                rows = cursor.fetchall()

            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
            conn.close()

        except sqlite3.Error as e:
            result.error_message = str(e)
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        return result

    def get_full_schema(self) -> dict[str, Any]:
        """
        Extracts the complete schema from the SQLite database.
        Returns a dictionary mapping table names to their column definitions.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = [row[0] for row in cursor.fetchall()]

            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info('{table}')")
                columns = []
                for col in cursor.fetchall():
                    columns.append(
                        {
                            "column_name": col[1],
                            "type": col[2],
                            "pk": bool(col[5]),
                            "description": "",  # SQLite doesn't store descriptions easily in pragma
                        }
                    )

                # Get foreign keys
                cursor.execute(f"PRAGMA foreign_key_list('{table}')")
                fks = []
                for fk in cursor.fetchall():
                    fks.append(
                        {
                            "column": fk[3],
                            "referred_table": fk[2],
                            "referred_column": fk[4],
                        }
                    )

                schema[table] = {"columns": columns, "foreign_keys": fks}

            conn.close()
            return schema
        except Exception as e:
            print(f"Error extracting SQLite schema: {e}")
            return {}
