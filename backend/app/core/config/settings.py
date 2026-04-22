import os

class Settings:
    """
    Application-wide settings.
    Inherits defaults and dynamically loads project-specific overrides.
    """
    def __init__(self):
        self.PROJECT_NAME = "TT_SQL"
        self.PRODUCT_NAME = "nQuire"
        self.PRODUCT_ROLE = "Senior Advisor"
        
        # Qdrant Vector DB
        self.QDRANT_URL = "http://localhost:6333"
        self.QDRANT_API_KEY = ""
        
        # LLM Settings
        self.LLM_PROVIDER = "bedrock"
        self.LLM_MODEL = "bedrock/openai.gpt-oss-safeguard-120b"
        self.LLM_API_BASE = ""
        self.OPENAI_API_KEY = ""
        self.EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
        self.EMBEDDING_SIZE = 768 
        
        # Bedrock Access
        self.BEDROCK_REGION = "us-east-1"
        self.BEDROCK_ACCESS_KEY_ID = ""
        self.BEDROCK_SECRET_ACCESS_KEY = ""
        
        # Execution Defaults
        self.PARALLEL_WORKERS = 4
        self.ACTIVE_PROJECT_ID = None
        self.SECRET_KEY = "system-wide-analytical-secret"
        
        # Primary load from global registry
        self.load_global_settings()

    def load_global_settings(self):
        """Initial load of app-wide settings from the registry."""
        try:
            from app.repositories.settings_repo import SettingsRepository
            data = SettingsRepository.get_settings()
            if data:
                self._apply_dict(data)
        except Exception:
            pass

    def reload_from_project(self, project: dict):
        """Dynamic project-scoped settings override."""
        conn = project.get("connection", {})
        self.ACTIVE_PROJECT_ID = project.get("id")
        self._apply_dict(conn)
        self._invalidate_caches()

    def _apply_dict(self, data: dict):
        """Map dictionary keys to settings attributes."""
        mapping = {
            "llm_provider": "LLM_PROVIDER",
            "llm_model": "LLM_MODEL",
            "llm_api_base": "LLM_API_BASE",
            "llm_api_key": "OPENAI_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "embedding_model": "EMBEDDING_MODEL",
            "bedrock_region": "BEDROCK_REGION",
            "bedrock_access_key": "BEDROCK_ACCESS_KEY_ID",
            "bedrock_secret_key": "BEDROCK_SECRET_ACCESS_KEY",
            "qdrant_url": "QDRANT_URL",
            "qdrant_api_key": "QDRANT_API_KEY"
        }
        for k, v in data.items():
            attr = mapping.get(k)
            if attr:
                if k == "qdrant_url": v = v.rstrip("/")
                setattr(self, attr, v)

    def _invalidate_caches(self):
        """Clears relevant service caches for live settings updates."""
        try:
            from app.services.llm_service import LLMService
            LLMService._CLIENT_CACHE = {}
        except ImportError:
            pass

settings = Settings()
