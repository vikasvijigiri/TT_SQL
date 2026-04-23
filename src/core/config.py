from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized configuration for the Text2SQL pipeline using Pydantic Settings.
    This provides type safety, validation, and environment-variable support.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    # Database Configuration
    DB_TYPE: str = Field(default="sqlite")
    SQLITE_DB_PATH: str = Field(default="resources")

    # Amazon Bedrock Configuration
    BEDROCK_ACCESS_KEY: str | None = Field(None, alias="BEDROCK_ACCESS_KEY_ID")
    BEDROCK_SECRET_ACCESS_KEY: str | None = None
    BEDROCK_REGION: str = Field(default="us-east-1")
    LLM_PROVIDER: str = Field(default="bedrock")
    LLM_MODEL: str = Field(default="bedrock/default-model")
    LLM_TEMPERATURE: float = Field(default=0.0)
    LLM_MAX_TOKENS: int = Field(default=4096)

    # Application Settings
    LOG_LEVEL: str = Field(default="INFO")
    MAX_RETRIES: int = Field(default=4)
    TIMEOUT_SECONDS: int = Field(default=90)

    # Qdrant Vector DB
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = Field(None, alias="QDRANT_API")
    QDRANT_COLLECTION: str | None = None

    # AWS Postgres / Bedrock KB / S3
    S3_BUCKET_NAME: str | None = None
    BEDROCK_KB_ID: str | None = None

    # Google Cloud / BigQuery
    GCP_PROJECT_ID: str | None = None
    GCP_CREDENTIALS_PATH: str = Field(default="config/gcp_credentials.json")

    # Snowflake
    SF_CREDENTIALS_PATH: str = Field(default="config/sf_credentials.json")

    @property
    def gcp_credentials_abs_path(self) -> str | None:
        """Resolves the GCP credentials path to an absolute path."""
        if not self.GCP_CREDENTIALS_PATH:
            return None
        p = Path(self.GCP_CREDENTIALS_PATH)
        if p.is_absolute():
            return str(p)

        from .paths import PROJECT_ROOT

        return str(PROJECT_ROOT / p)

    @property
    def sf_credentials_abs_path(self) -> str | None:
        """Resolves the Snowflake credentials path to an absolute path."""
        if not self.SF_CREDENTIALS_PATH:
            return None
        p = Path(self.SF_CREDENTIALS_PATH)
        if p.is_absolute():
            return str(p)

        from .paths import PROJECT_ROOT

        return str(PROJECT_ROOT / p)


# Singleton settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Returns the global settings instance, initializing if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
