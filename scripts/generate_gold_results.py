import csv
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from tqdm import tqdm


def generate_gold_results():
    # Load environment variables
    load_dotenv()

    input_csv = "data/text2sql_202602261250.csv"
    gold_dir = Path("data/gold")
    sql_dir = gold_dir / "sql"
    csv_dir = gold_dir / "csv"

    sql_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    # DB Credentials
    host = os.getenv("RDS_HOST")
    database = os.getenv("RDS_DATABASE", "postgres")
    user = os.getenv("RDS_USER")
    password = os.getenv("RDS_PASSWORD")
    port = os.getenv("RDS_PORT", "5432")
    schema = os.getenv("SCHEMA", "acme-chatbot").strip().replace('"', "")

    print(f"Connecting to Postgres at {host}...")
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

        # Set search path
        cursor.execute(f'SET search_path TO "{schema}", public;')
        print(f"Search path set to {schema}")

    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    # Process CSV
    print(f"Reading ground truth from {input_csv}...")

    # Custom state-machine parser to handle malformed quoting
    def custom_csv_parser(file_path):
        import io

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        records = []
        current_record = []
        current_field = io.StringIO()
        in_quotes = False

        i = 0
        while i < len(content):
            char = content[i]

            if char == '"':
                # Check for escaped quotes (double-double quotes)
                if i + 1 < len(content) and content[i + 1] == '"':
                    current_field.write('"')
                    i += 1
                else:
                    in_quotes = not in_quotes
            elif char == "," and not in_quotes:
                current_record.append(current_field.getvalue())
                current_field = io.StringIO()
            elif char == "\n" and not in_quotes:
                current_record.append(current_field.getvalue())
                if current_record:
                    records.append(current_record)
                current_record = []
                current_field = io.StringIO()
            else:
                current_field.write(char)
            i += 1

        # Add last field/record if exists
        if current_field.getvalue() or current_record:
            current_record.append(current_field.getvalue())
            records.append(current_record)

        return records

    all_records = custom_csv_parser(input_csv)

    # Process records (Skip header)
    rows = []
    if all_records:
        header = all_records[0]
        # Map indices: db=0, questions=1, sql_query=2
        for rec in all_records[1:]:
            if len(rec) >= 3:
                rows.append(
                    {
                        "db": rec[0].strip(),
                        "questions": rec[1].strip(),
                        "sql_query": rec[2].strip(),
                    }
                )
            elif len(rec) == 2:  # Malformed but common
                rows.append(
                    {"db": rec[0].strip(), "questions": rec[1].strip(), "sql_query": ""}
                )

    print(
        f"Found {len(rows)} queries using state-machine parser. Starting execution..."
    )

    success_count = 0
    fail_count = 0

    for idx, row in enumerate(tqdm(rows, desc="Executing queries"), start=1):
        instance_id = f"q{idx:03d}"
        query = row.get("sql_query")

        if query is None:
            query = ""

        query = query.strip()

        if not query:
            print(f"Warning: Empty query for {instance_id}")
            fail_count += 1
            continue

        # Clean the query:
        # 1. Rectify double-double quotes as requested: ""table"" -> "table"
        query = query.replace('""', '"')

        # 2. Remove literal surrounding double quotes if they exist
        if query.startswith('"') and query.endswith('"'):
            query = query[1:-1].strip()

        # 3. Handle multiple statements (take only the first primary one)
        if ";" in query:
            statements = [s.strip() for s in query.split(";") if s.strip()]
            if statements:
                query = statements[0]

        sql_file = sql_dir / f"{instance_id}.sql"
        csv_file = csv_dir / f"{instance_id}.csv"

        # Save the isolated SQL query
        try:
            with open(sql_file, mode="w", encoding="utf-8") as sf:
                sf.write(query)
        except Exception as sql_err:
            print(f"Failed to write SQL file {sql_file}: {sql_err}")

        columns = []
        data = []
        try:
            cursor.execute(query)
            # Fetch results
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            success_count += 1
        except Exception as e:
            # Verbose error as requested to debug failures
            print(f"\nError executing {instance_id}: {e}")
            print(f"Target Query: {query}")
            fail_count += 1
            pass

        # Always write the CSV (even if empty/failed)
        try:
            with open(csv_file, mode="w", newline="", encoding="utf-8") as cf:
                writer = csv.writer(cf)
                writer.writerow(columns)
                writer.writerows(data)
        except Exception as file_err:
            print(f"Failed to write {csv_file}: {file_err}")

    conn.close()
    print(f"\nDone! Success: {success_count}, Failed: {fail_count}")
    print(f"Gold results stored in {gold_dir}")


if __name__ == "__main__":
    generate_gold_results()
