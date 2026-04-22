from fastapi import APIRouter, HTTPException, UploadFile, File
import io
from dotenv import dotenv_values

from typing import Dict, Any
from app.repositories.settings_repo import SettingsRepository

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("")
async def get_global_settings():
    """Returns the global application settings."""
    try:
        return SettingsRepository.get_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("")
async def update_global_settings(settings: Dict[str, Any]):
    """Updates the global application settings across the whole system."""
    try:
        updated = SettingsRepository.save_settings(settings)
        return {"status": "success", "settings": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("")
async def reset_global_settings():
    """Resets the global application settings to system defaults."""
    try:
        SettingsRepository.delete_settings()
        return {"status": "success", "message": "Settings reset to defaults."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/parse-env")
async def parse_env_file(file: UploadFile = File(...)):
    """
    Parses a .env file and returns mapped settings for the UI.
    Does NOT save them automatically.
    """
    if not file.filename.lower().endswith(('.env', 'env')):
         if not ("env" in file.filename.lower()):
            raise HTTPException(status_code=400, detail="Please upload a .env file")

    try:
        content = await file.read()
        env_dict = dotenv_values(stream=io.StringIO(content.decode('utf-8')))
        
        # Mapping from .env keys to internal settings keys
        MAPPING = {
            "LLM_PROVIDER": "llm_provider",
            "LLM_MODEL": "llm_model",
            "LLM_API_BASE": "llm_api_base",
            "OPENAI_API_KEY": "openai_api_key",
            "LLM_API_KEY": "openai_api_key", # Alternate key
            "EMBEDDING_MODEL": "embedding_model",
            "BEDROCK_REGION": "bedrock_region",
            "BEDROCK_ACCESS_KEY_ID": "bedrock_access_key",
            "BEDROCK_SECRET_ACCESS_KEY": "bedrock_secret_key",
            "QDRANT_URL": "qdrant_url",
            "QDRANT_API_KEY": "qdrant_api_key"
        }
        
        result = {}
        for env_key, internal_key in MAPPING.items():
            if env_key in env_dict and env_dict[env_key]:
                result[internal_key] = env_dict[env_key]
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse .env: {e}")
