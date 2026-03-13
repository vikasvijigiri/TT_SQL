import os
from dotenv import load_dotenv
from multiprocessing import cpu_count

# Load .env with override to ensure it's prioritized over system env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
env_path = os.path.join(PROJECT_ROOT, "backend", ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(PROJECT_ROOT, ".env")
    
load_dotenv(env_path, override=True)

class Settings:
    def __init__(self):
        self.PROJECT_NAME = "TT_SQL"
        
        # Path Overrides (managed by paths.py typically, but accessible here)
        self.REPO_DIR = os.getenv("REPO_DIR")
        self.RESULTS_DIR = os.getenv("RESULTS_DIR")
        self.DATA_DIR = os.getenv("DATA_DIR")
        self.METADATA_DIR = os.getenv("METADATA_DIR")
        
        # Qdrant Vector DB
        self.QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API") or os.getenv("QDRANT_API_KEY")
        self.COLLECTION_NAME = os.getenv("QDRANT_COLLECTION") or os.getenv("SCHEMA") or os.getenv("DB_NAME") or "acme-chatbot"
        self.SCHEMA = os.getenv("SCHEMA") or os.getenv("DB_NAME") or "public"
        self.DB_NAME = os.getenv("DB_NAME") or "postgres"
        
        print(f"DEBUG: Loaded Settings - SCHEMA: {self.SCHEMA}, DB_NAME: {self.DB_NAME}")
        
        # LLM Settings
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "bedrock")
        self.LLM_MODEL = os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b")
        self.LLM_API_BASE = os.getenv("LLM_API_BASE")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
        self.EMBEDDING_SIZE = 768 # 768 for bge-base, 1024 for bge-large
        
        # Bedrock Specific
        self.BEDROCK_REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        self.BEDROCK_ACCESS_KEY_ID = os.getenv("BEDROCK_ACCESS_KEY_ID")
        self.BEDROCK_SECRET_ACCESS_KEY = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
        
        # Batch & Pipeline Defaults
        self.BATCH_INPUT_PATH = os.getenv("BATCH_INPUT_PATH", "app/repositories/data/input_queries/sample.jsonl")
        try:
            self.PARALLEL_WORKERS = int(os.getenv("PARALLEL_WORKERS", cpu_count()))
        except (ValueError, TypeError):
            self.PARALLEL_WORKERS = cpu_count()
        
        # Custom_DB connection details here (Currently: AWS / RDS)
        self.DB_TYPE = os.getenv("DB_TYPE", "postgres")
        self.SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "app/repositories/data/sqlite")
        self.RDS_DATABASE = os.getenv("RDS_DATABASE", "postgres")
        self.RDS_HOST = os.getenv("RDS_HOST")
        self.RDS_PORT = os.getenv("RDS_PORT", "5432")
        self.RDS_USER = os.getenv("RDS_USER")
        self.RDS_PASSWORD = os.getenv("RDS_PASSWORD")

settings = Settings()
