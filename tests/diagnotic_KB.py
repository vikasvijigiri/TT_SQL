import sqlite3
import os
import subprocess
import json
import time
from langchain_aws import AmazonKnowledgeBasesRetriever
from dotenv import load_dotenv

# Load from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env'))

# ---------------- CONFIG ----------------
SQLITE_PATH = os.getenv("SQLITE_DB_PATH")

# Use S3_BUCKET_NAME from .env, fallback to DB_NAME (risky but better than crashing if env missing)
# But here we enforce checking.
S3_BUCKET = os.getenv("S3_BUCKET_NAME") 
S3_PREFIX = os.getenv("DB_NAME")


REGION = os.getenv("BEDROCK_REGION")
KB_ID = os.getenv("BEDROCK_KB_ID")
DATA_SOURCE_ID = os.getenv("BEDROCK_DATA_SOURCE_ID")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")


# ---------------- STEP 1: EXTRACT METADATA ----------------
def extract_metadata():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        print(f"Error: SQLITE_DB_PATH not found: {SQLITE_PATH}")
        return

    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for (table_name,) in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()

        column_text = "\n".join(
            [f"- {col[1]} ({col[2]})" for col in columns]
        )

        doc = f"""Table: {table_name}
            Columns:
            {column_text}
        """

        with open(f"{OUTPUT_DIR}/{table_name}.txt", "w") as f:
            f.write(doc)

    conn.close()
    print("Metadata extracted.")


# ---------------- STEP 2: UPLOAD TO S3 ----------------
def upload_to_s3():
    if not S3_BUCKET:
        print("❌ Error: S3_BUCKET_NAME is not set in .env")
        print("Please create an S3 bucket and add S3_BUCKET_NAME=your-bucket-name to .env")
        return

    print(f"Uploading to bucket: {S3_BUCKET}...")
    cmd = [
        "aws", "s3", "cp",
        OUTPUT_DIR,
        f"s3://{S3_BUCKET}/{S3_PREFIX}",
        "--recursive"
    ]
    try:
        subprocess.run(cmd, check=True)
        print("Uploaded to S3.")
    except subprocess.CalledProcessError as e:
        print(f"Upload failed: {e}")


# ---------------- STEP 3: START INGESTION ----------------
def start_ingestion():
    if not KB_ID or not DATA_SOURCE_ID:
        print("Skipping ingestion: BEDROCK_KB_ID or BEDROCK_DATA_SOURCE_ID not set.")
        return None
    
    if not REGION:
        print("Error: BEDROCK_REGION not set.")
        return None
        
    cmd = [
        "aws", "bedrock-agent", "start-ingestion-job",
        "--knowledge-base-id", KB_ID,
        "--data-source-id", DATA_SOURCE_ID,
        "--region", REGION
    ]

    try:
        result = subprocess.check_output(cmd)
        result = json.loads(result)

        job_id = result["ingestionJob"]["ingestionJobId"]
        print("Ingestion job started:", job_id)
        return job_id
    except subprocess.CalledProcessError as e:
        print(f"Ingestion start failed: {e}")
        return None
    except Exception as e:
        print(f"Error parsing ingestion response: {e}")
        return None


# ---------------- STEP 4: WAIT FOR INGESTION ----------------
def wait_for_ingestion(job_id):
    if not job_id:
        return

    while True:
        cmd = [
            "aws", "bedrock-agent", "list-ingestion-jobs",
            "--knowledge-base-id", KB_ID,
            "--data-source-id", DATA_SOURCE_ID,
            "--region", REGION
        ]

        try:
             result = subprocess.check_output(cmd)
             result = json.loads(result)

             for job in result["ingestionJobSummaries"]:
                 if job["ingestionJobId"] == job_id:
                     status = job["status"]
                     print("Status:", status)

                     if status in ["COMPLETE", "FAILED"]:
                         return
        except Exception as e:
            print(f"Error checking status: {e}")
            return

        time.sleep(5)


# ---------------- STEP 5: RETRIEVE TABLES ----------------
def retrieve_tables(query):
    if not KB_ID:
        print("Skipping retrieval: BEDROCK_KB_ID not set.")
        return []
        
    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id=KB_ID,
        region_name=REGION,
        retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 5}}
    )

    try:
        docs = retriever.invoke(query)
        tables = []
        for doc in docs:
            first_line = doc.page_content.split("\n")[0]
            table_name = first_line.replace("Table:", "").strip()
            tables.append(table_name)
        return tables
    except Exception as e:
        print(f"Retrieval failed: {e}")
        return []


# ---------------- MAIN ----------------
if __name__ == "__main__":
    if not SQLITE_PATH:
        print("Error: SQLITE_DB_PATH not set in .env")
        exit(1)
        
    extract_metadata()
    upload_to_s3() 
    
    job_id = start_ingestion()
    wait_for_ingestion(job_id)

    # tables = retrieve_tables("customer payments")
    # print("Relevant tables:", tables)
