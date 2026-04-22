import argparse
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


def execute_sql_files(
    directory: str = None, files: list = None, save_csv: bool = False
):
    """Refactored core logic for SQL execution."""
    load_dotenv()

    # DB Credentials
    host = os.getenv("RDS_HOST")
    database = os.getenv("RDS_DATABASE", "postgres")
    user = os.getenv("RDS_USER")
    password = os.getenv("RDS_PASSWORD")
    port = os.getenv("RDS_PORT", "5432")
    schema = os.getenv("SCHEMA", "acme-chatbot").strip().replace('"', "")

    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
            connect_timeout=10,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f'SET search_path TO "{schema}", public;')
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    sql_files = []
    if files:
        for f in files:
            p = Path(f)
            if not p.exists():
                # Fallback to a default data location if needed
                p = Path("data/gold/sql") / f
            if p.exists():
                sql_files.append(p)
            else:
                print(f"File not found: {f}")
    elif directory:
        dir_path = Path(directory)
        if dir_path.exists():
            sql_files = sorted(list(dir_path.glob("*.sql")))
    else:
        # Default behavior: run all in gold/sql
        dir_path = Path("data/gold/sql")
        if dir_path.exists():
            sql_files = sorted(list(dir_path.glob("*.sql")))

    print(f"Found {len(sql_files)} SQL files to execute.")

    for sql_file in sql_files:
        print(f"\n--- Executing {sql_file.name} ---")
        try:
            with open(sql_file, encoding="utf-8") as f:
                query = f.read().strip()

            if not query:
                print("Empty query.")
                continue

            cursor.execute(query)

            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                data = cursor.fetchall()
                print(f"Columns: {columns}")
                print(f"Rows: {len(data)}")
                for row in data[:5]:  # Show first 5 rows
                    print(row)
                if len(data) > 5:
                    print(f"... and {len(data) - 5} more.")
            else:
                print("Command executed successfully (no result set).")

        except Exception as e:
            print(f"Error: {e}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Execute SQL files from a directory or specific paths."
    )
    parser.add_argument(
        "--dir", type=str, help="Directory containing .sql files to execute."
    )
    parser.add_argument("--files", nargs="+", help="Specific .sql files to execute.")
    parser.add_argument(
        "--save-csv",
        action="store_true",
        help="Whether to save results back to data/gold/csv",
    )

    args = parser.parse_args()
    execute_sql_files(directory=args.dir, files=args.files, save_csv=args.save_csv)


if __name__ == "__main__":
    main()
