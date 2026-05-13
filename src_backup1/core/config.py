from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Load .env at the very beginning
load_dotenv()

class Settings(BaseSettings):
    """
    Centralized configuration with explicit .env loading.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Amazon Bedrock Configuration
    BEDROCK_ACCESS_KEY_ID: str | None = Field(None)
    BEDROCK_SECRET_ACCESS_KEY: str | None = None
    BEDROCK_REGION: str = Field(default="us-east-1")
    LLM_PROVIDER: str = Field(default="bedrock")
    LLM_MODEL: str = Field(default="bedrock/openai.gpt-oss-safeguard-120b")
    LLM_TEMPERATURE: float = Field(default=0.0)
    LLM_MAX_TOKENS: int = Field(default=8192)

    # Application Settings
    LOG_LEVEL: str = Field(default="INFO")
    TIMEOUT_SECONDS: int = Field(default=180)

    # Grounding Thresholds
    GROUNDING_MIN_VALUE_SCORE: float = Field(default=0.75)
    GROUNDING_STRONG_VALUE_SCORE: float = Field(default=0.9)
    GROUNDING_MIN_SEMANTIC_SCORE: float = Field(default=0.5)
    GROUNDING_MIN_CONFIDENCE: float = Field(default=0.6)
    
    # Generic values for grounding
    GENERIC_VALUES: list[str] = Field(default_factory=lambda: ["other", "unknown", "na", "n/a"])

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
