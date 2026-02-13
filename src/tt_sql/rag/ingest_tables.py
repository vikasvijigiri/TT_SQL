import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Add src to python path so we can import tt_sql
sys.path.append(str(Path(__file__).parent))

from tt_sql.rag.vector_store import VectorStoreAgent
from tt_sql.core.paths import InstancePaths

def ingest_database(db_name):
    print(f"🔌 Connecting to database: {db_name}")
    
    # Resolve path using our centralized logic
    # db_name can be just the name "IPL" or "IPL.sqlite"
    if db_name.endswith(".sqlite"):
        db_name = db_name[:-7]
        
    db_path = str(InstancePaths.database(db_name))
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Initialize Vector Store
        print("🧠 Initializing Vector Store...")
        vs = VectorStoreAgent()
        if not vs.client:
             print("❌ Failed to initialize Qdrant. Check your credentials.")
             return

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith('sqlite_')]
        
        print(f"📦 Found {len(tables)} tables. Starting ingestion...")
        
        for table in tables:
            # 1. Get Columns
            cursor.execute(f"PRAGMA table_info({table})")
            cols = cursor.fetchall()
            # Format: name (type)
            col_desc = [f"{c[1]} ({c[2]})" for c in cols]
            col_text = ", ".join(col_desc)
            
            # 2. Get Foreign Keys
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()
            fk_text = ""
            if fks:
                # Format: col -> table.col
                fk_list = [f"{fk[3]} -> {fk[2]}.{fk[4]}" for fk in fks]
                fk_text = f"\nForeign Keys: {', '.join(fk_list)}"
            
            # 3. Get Sample Data (Context is King)
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = cursor.fetchall()
            sample_text = ""
            if rows:
                sample_text = "\nSample Rows:\n" + "\n".join([str(r) for r in rows])

            # 4. Construct Rich Metadata Text
            # This text is what will be embedded
            full_text = (
                f"Table Name: {table}\n"
                f"Description: Contains data about {table}.\n"
                f"Columns: {col_text}"
                f"{fk_text}"
                f"{sample_text}"
            )
            
            # 5. Upsert
            print(f"   ⬆️  Ingesting: {table}")
            vs.upsert_table_metadata(table, full_text)
            
        print(f"\n✅ Successfully ingested {len(tables)} tables into Qdrant!")
        conn.close()

    except Exception as e:
        print(f"❌ Error during ingestion: {e}")

if __name__ == "__main__":
    load_dotenv()
    
    # Default to IPL or get from env
    target_db = os.getenv("DB_NAME", "IPL")
    
    # Allow command line override
    if len(sys.argv) > 1:
        target_db = sys.argv[1]
        
    ingest_database(target_db)
