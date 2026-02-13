import sqlite3
import psycopg2
from langchain_aws import BedrockEmbeddings
import os
from dotenv import load_dotenv

# Load from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))


# ---------------- CONFIG ----------------
SQLITE_PATH = os.getenv("SQLITE_DB_PATH")

PG_CONFIG = {
    "host": os.getenv("PG_HOST"),
    "dbname": os.getenv("PG_DBNAME"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASSWORD"),
    "port": os.getenv("PG_PORT")
}

# Bedrock embedding model
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v1",
    region_name="us-east-1"
)


# ---------------- SQLITE METADATA ----------------
def extract_sqlite_metadata(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    metadata = []

    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        column_text = "\n".join(
            [f"- {col[1]} ({col[2]})" for col in columns]
        )

        text = f"Table: {table_name}\nColumns:\n{column_text}"
        metadata.append((table_name, text))

    conn.close()
    return metadata


# ---------------- STORE ----------------
def store_metadata(metadata):
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    for table_name, text in metadata:
        embedding = embeddings.embed_query(text)

        cursor.execute(
            """
            INSERT INTO table_metadata (table_name, metadata_text, embedding)
            VALUES (%s, %s, %s)
            """,
            (table_name, text, embedding)
        )

    conn.commit()
    cursor.close()
    conn.close()


# ---------------- RETRIEVE ----------------
def retrieve_tables(query, top_k=3):
    conn = psycopg2.connect(**PG_CONFIG)
    cursor = conn.cursor()

    query_embedding = embeddings.embed_query(query)

    cursor.execute(
        """
        SELECT table_name
        FROM table_metadata
        ORDER BY embedding <-> %s
        LIMIT %s;
        """,
        (query_embedding, top_k)
    )

    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]


# ---------------- MAIN ----------------
if __name__ == "__main__":
    metadata = extract_sqlite_metadata(SQLITE_PATH)
    store_metadata(metadata)

    tables = retrieve_tables("customer payments")
    print("Relevant tables:", tables)
