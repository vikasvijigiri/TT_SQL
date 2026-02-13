import os
import json
import sys
from dotenv import load_dotenv

# Ensure we can import from src
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, '../src'))

from tt_sql.core.llm_service import LLMService

def test_llm_service():
    # Load environment variables
    load_dotenv()
    
    print("--- Testing LLMService with LangChain Bedrock ---")
    model_name = os.getenv("LLM_MODEL", "bedrock/anthropic.claude-3-haiku-20240307-v1:0")
    print(f"Model: {model_name}")
    
    try:
        llm = LLMService(model=model_name)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Return the string 'LangChain Success' and nothing else."}
        ]
        
        print("Requesting completion...")
        response = llm.get_completion(messages)
        print(f"Response: {response}")
        
        if "LangChain Success" in response:
            print("SUCCESS: LangChain Bedrock integration is working!")
        else:
            print(f"FAILED: Unexpected response: {response}")
            
    except Exception as e:
        print(f"ERROR: Exception during verification: {e}")

if __name__ == "__main__":
    test_llm_service()
