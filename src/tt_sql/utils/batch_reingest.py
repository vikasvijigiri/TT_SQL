import os
import glob
from tt_sql.utils.qdrant_ingest import ingest_metadata
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

def reingest_all():
    load_dotenv()
    schema_dir = r"c:\Users\VikasVijigiri\Documents\TT_SQL\results\bedrock_openai.gpt-oss-safeguard-120b\schema"
    json_files = glob.glob(os.path.join(schema_dir, "*.json"))
    
    print(f"Found {len(json_files)} schema files to ingest.")
    
    print("Initializing SentenceTransformer (BAAI/bge-base-en-v1.5) once...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')
    
    for i, json_file in enumerate(json_files):
        # Recreate collection on the first file, then append
        recreate = (i == 0)
        
        print(f"[{i+1}/{len(json_files)}] Ingesting {os.path.basename(json_file)}...")
        
        try:
            ingest_metadata(json_file, recreate=recreate, model=model)
        except Exception as e:
            print(f"Error ingesting {json_file}: {e}")

if __name__ == "__main__":
    reingest_all()
