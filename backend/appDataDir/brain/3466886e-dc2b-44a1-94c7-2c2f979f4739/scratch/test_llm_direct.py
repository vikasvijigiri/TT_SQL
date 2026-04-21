import os
import sys
from pathlib import Path
import boto3

# Add backend to path
sys.path.append(str(Path(os.getcwd())))

from app.services.engines.llm_service import LLMService

def test_llm_direct():
    print("Testing LLMService (Direct Boto3 Converse) initialization...")
    try:
        service = LLMService(model="bedrock/openai.gpt-oss-safeguard-120b")
        print(f"Service initialized. is_bedrock: {service.is_bedrock}")
        
        messages = [{"role": "user", "content": "Respond with the word 'SUCCESS' if you hear me."}]
        print("Requesting completion...")
        res = service.get_completion(messages)
        print(f"Response: {res}")
        
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_direct()
