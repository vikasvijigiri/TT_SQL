import sqlite3
import time
from typing import Any

from core.state import ExecutionResult
from core.logger import Logger


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

            # Clean query for keyword check
            import re
            clean_query = re.sub(r'--.*$', '', query, flags=re.MULTILINE).strip()
            
            if not any(
                clean_query.upper().startswith(kw)
                for kw in ["SELECT", "WITH", "PRAGMA", "EXPLAIN"]
            ):
                raise sqlite3.Error(
                    f"String does not appear to be a valid SQL command: '{clean_query[:50]}...'"
                )

            cursor.execute(query)

            # Fetch columns
            if cursor.description:
                result.columns = [description[0] for description in cursor.description]

            # Fetch rows
            if sampling:
                from core.logger import Logger
                Logger.log("Large table avoided (sampling applied)")
                # Task 3: Enforce Lightweight & Bounded inspection
                # Ensure LIMIT is present or use fetchmany(3)
                if "LIMIT" not in query.upper():
                    rows = cursor.fetchmany(50)
                else:
                    rows = cursor.fetchmany(100) # Respect existing limit but capped
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

    def get_table_names(self) -> list[str]:
        """Task 2: Stage 1 - Fetch ONLY table names for progressive retrieval."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Exception as e:
            from core.logger import Logger
            Logger.log(f"Error fetching SQLite table names: {e}", level="ERROR")
            return []

    def get_full_schema(self, table_list: list[str] | None = None, sample_rows: bool = False) -> dict[str, Any]:
        """
        Extracts the schema from the SQLite database.
        If table_list is provided, only fetches metadata for those tables.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if table_list:
                tables = [t.split('.')[-1].replace('"', '').replace("'", "") for t in table_list]
            else:
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
                            "description": "", 
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

                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
                row_count = cursor.fetchone()[0]

                schema[table] = {"columns": columns, "foreign_keys": fks, "row_count": row_count}
                
                if sample_rows:
                    try:
                        cursor.execute(f"SELECT * FROM \"{table}\" LIMIT 3")
                        rows = cursor.fetchall()
                        desc = cursor.description
                        if desc:
                            c_names = [d[0] for d in desc]
                            schema[table]["sample"] = [dict(zip(c_names, row)) for row in rows]
                    except Exception as se:
                        Logger.log(f"Samples skipped for {table}: {se}", level="WARN")

            conn.close()
            return schema
        except Exception as e:
            print(f"Error extracting SQLite schema: {e}")
            return {}
