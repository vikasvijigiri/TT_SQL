import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(os.getcwd())))

from app.services.engines.llm_service import LLMService
from app.services.schemas.agent_state import AgentState

def test_llm():
    print("Testing LLMService initialization...")
    try:
        service = LLMService(model="bedrock/openai.gpt-oss-safeguard-120b")
        print(f"Service initialized. is_bedrock: {service.is_bedrock}")
        
        messages = [{"role": "user", "content": "Hello, respond with 'SUCCESS' if you hear me."}]
        print("Requesting completion...")
        res = service.get_completion(messages)
        print(f"Response: {res}")
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_llm()
