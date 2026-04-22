from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, List
from pathlib import Path
import os

class Settings(BaseSettings):
    """
    Centralized configuration for the Text2SQL pipeline using Pydantic Settings.
    This provides type safety, validation, and environment-variable support.
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars
    )

    # Database Configuration
    DB_TYPE: str = Field(default="sqlite")
    SQLITE_DB_PATH: str = Field(default="resources")

    # Amazon Bedrock Configuration
    BEDROCK_ACCESS_KEY: Optional[str] = Field(None, alias="BEDROCK_ACCESS_KEY_ID")
    BEDROCK_SECRET_ACCESS_KEY: Optional[str] = None
    BEDROCK_REGION: str = Field(default="us-east-1")
    LLM_PROVIDER: str = Field(default="bedrock")
    LLM_MODEL: str = Field(default="bedrock/openai.gpt-oss-safeguard-120b")
    LLM_API_BASE: Optional[str] = None
    LLM_TEMPERATURE: float = Field(default=0.0)
    LLM_MAX_TOKENS: int = Field(default=4096)

    # Application Settings
    LOG_LEVEL: str = Field(default="INFO")
    MAX_RETRIES: int = Field(default=4)
    TIMEOUT_SECONDS: int = Field(default=90)

    # Qdrant Vector DB
    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = Field(None, alias="QDRANT_API")
    QDRANT_COLLECTION: Optional[str] = None

    # AWS Postgres / Bedrock KB / S3
    S3_BUCKET_NAME: Optional[str] = None
    BEDROCK_KB_ID: Optional[str] = None
    
    # Google Cloud / BigQuery
    GCP_PROJECT_ID: Optional[str] = None
    GCP_CREDENTIALS_PATH: str = Field(default="text2sql_gcp_credentials.json")
    
    # Snowflake
    SF_CREDENTIALS_PATH: str = Field(default="config/sf_credentials.json")

    @property
    def gcp_credentials_abs_path(self) -> Optional[str]:
        """Resolves the GCP credentials path to an absolute path."""
        if not self.GCP_CREDENTIALS_PATH:
            return None
        p = Path(self.GCP_CREDENTIALS_PATH)
        if p.is_absolute():
            return str(p)
        
        # Try relative to project root
        # src/tt_sql/core/config.py -> .parent.parent.parent.parent
        root = Path(__file__).resolve().parent.parent.parent.parent
        return str(root / p)

    @property
    def sf_credentials_abs_path(self) -> Optional[str]:
        """Resolves the Snowflake credentials path to an absolute path."""
        if not self.SF_CREDENTIALS_PATH:
            return None
        p = Path(self.SF_CREDENTIALS_PATH)
        if p.is_absolute():
            return str(p)
        
        root = Path(__file__).resolve().parent.parent.parent.parent
        return str(root / p)

# Singleton settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Returns the global settings instance, initializing if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
