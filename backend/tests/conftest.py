import pytest
import os
from dotenv import load_dotenv
from app.services.engines.llm_service import LLMService

@pytest.fixture(scope="module")
def llm():
    load_dotenv()
    model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    return LLMService(model=model)
