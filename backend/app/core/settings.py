import os
# load_dotenv() - Removed to fulfill "NO .env" requirement

class Settings:
    def __init__(self):
        self.PROJECT_NAME = "TT_SQL"
        self.PRODUCT_NAME = "nQuire"
        self.PRODUCT_ROLE = "Senior Advisor"
        
        # Qdrant Vector DB (Defaults only)
        self.QDRANT_URL = "http://localhost:6333"
        self.QDRANT_API_KEY = ""
        
        # LLM Settings (Defaults only)
        self.LLM_PROVIDER = "bedrock"
        self.LLM_MODEL = "bedrock/openai.gpt-oss-safeguard-120b"
        self.LLM_API_BASE = ""
        self.OPENAI_API_KEY = ""
        self.EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
        self.EMBEDDING_SIZE = 768 
        
        # Bedrock Authority (Defaults only)
        self.BEDROCK_REGION = "us-east-1"
        self.BEDROCK_ACCESS_KEY_ID = ""
        self.BEDROCK_SECRET_ACCESS_KEY = ""
        
        # Batch & Pipeline Defaults
        self.BATCH_INPUT_PATH = "data/input_queries/sample.jsonl"
        self.PARALLEL_WORKERS = 4
        
        # Path Overrides
        self.RESULTS_DIR = None
        self.SQLITE_DB_PATH = None
        
        # Active Project Context
        self.ACTIVE_PROJECT_ID = None
        
        # Project Defaults
        self.DB_TYPE = ""
        self.SCHEMA = ""
        self.COLLECTION_NAME = ""
        self.BQ_CREDENTIALS_PATH = ""
        
        # OAuth & Auth
        self.GOOGLE_CLIENT_ID = ""
        self.SECRET_KEY = "system-wide-analytical-secret"
        
        # Load Global Settings from Registry (Primary Source)
        self.load_global_settings()
        

    def reload_from_project(self, project: dict):
        """In-memory update of settings for the current session."""
        conn = project.get("connection", {})
        self.ACTIVE_PROJECT_ID = project.get("id")
        self.DB_TYPE = conn.get("db_type", "")
        self.SCHEMA = conn.get("db_name", "")
        self.COLLECTION_NAME = conn.get("qdrant_collection") or self.SCHEMA
        self.BQ_CREDENTIALS_PATH = conn.get("bq_credentials_path", "")

        # LLM Overrides
        if conn.get("llm_provider"):
            self.LLM_PROVIDER = conn.get("llm_provider")
        if conn.get("llm_model"):
            self.LLM_MODEL = conn.get("llm_model")
        if conn.get("llm_api_base"):
            self.LLM_API_BASE = conn.get("llm_api_base")
        if conn.get("llm_api_key"):
            self.OPENAI_API_KEY = conn.get("llm_api_key")
        if conn.get("embedding_model"):
            self.EMBEDDING_MODEL = conn.get("embedding_model")
            
        # Bedrock Overrides
        if conn.get("bedrock_region"):
            self.BEDROCK_REGION = conn.get("bedrock_region")
        if conn.get("bedrock_access_key"):
            self.BEDROCK_ACCESS_KEY_ID = conn.get("bedrock_access_key")
        if conn.get("bedrock_secret_key"):
            self.BEDROCK_SECRET_ACCESS_KEY = conn.get("bedrock_secret_key")

        # RAG Overrides
        if conn.get("qdrant_url"):
            self.QDRANT_URL = conn.get("qdrant_url").rstrip("/")
        if conn.get("qdrant_api_key"):
            self.QDRANT_API_KEY = conn.get("qdrant_api_key")

        # Invalidate LLM Cache to ensure new credentials/models are used
        try:
            from app.services.llm_service import LLMService
            LLMService._CLIENT_CACHE = {}
        except ImportError:
            pass

    def load_global_settings(self):
        """Loads app-wide settings from the global registry."""
        try:
            from app.repositories.settings_repo import SettingsRepository
            global_data = SettingsRepository.get_settings()
            if global_data:
                self.apply_global_settings(global_data)
        except Exception as e:
            print(f"Failed to load global settings: {e}")

    def apply_global_settings(self, data: dict):
        """Applies global overrides (LLM/RAG) in-memory."""
        # LLM Settings
        if data.get("llm_provider"): self.LLM_PROVIDER = data.get("llm_provider")
        if data.get("llm_model"): self.LLM_MODEL = data.get("llm_model")
        if data.get("llm_api_base"): self.LLM_API_BASE = data.get("llm_api_base")
        if data.get("openai_api_key"): self.OPENAI_API_KEY = data.get("openai_api_key")
        if data.get("embedding_model"): self.EMBEDDING_MODEL = data.get("embedding_model")
        
        # Bedrock Settings
        if data.get("bedrock_region"): self.BEDROCK_REGION = data.get("bedrock_region")
        if data.get("bedrock_access_key"): self.BEDROCK_ACCESS_KEY_ID = data.get("bedrock_access_key")
        if data.get("bedrock_secret_key"): self.BEDROCK_SECRET_ACCESS_KEY = data.get("bedrock_secret_key")

        # Qdrant Settings
        if data.get("qdrant_url"): self.QDRANT_URL = data.get("qdrant_url").rstrip("/")
        if data.get("qdrant_api_key"): self.QDRANT_API_KEY = data.get("qdrant_api_key")

        # Invalidate LLM Cache
        try:
            from app.services.llm_service import LLMService
            LLMService._CLIENT_CACHE = {}
        except ImportError:
            pass

    def reset(self):
        """Reset to non-project defaults."""
        # Re-initialize from defaults and registry 
        self.__init__()

        # Invalidate cached DB connections
        try:
            from app.services.agents.execution_layer import SQLiteExecutorAgent, PostgresExecutorAgent
            SQLiteExecutorAgent.reset_connection_pool()
            # PostgresExecutorAgent.connection_pool()
        except ImportError:
            pass

        # Invalidate LLM Cache
        try:
            from app.services.llm_service import LLMService
            LLMService._CLIENT_CACHE = {}
        except ImportError:
            pass

# settings = Settings()
# Module-level startup load removed to prevent circular deadlocks in multi-user mode.
# Data connections are now resolved per-request based on user slug.
settings = Settings()
