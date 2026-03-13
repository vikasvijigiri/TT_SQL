import os
import sys
from dotenv import load_dotenv

from app.services.llm_service import LLMService

def test_llm():
    load_dotenv()
    model_name = os.getenv("LLM_MODEL", "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0")
    print(f"Testing LLM: {model_name}")
    
    llm = LLMService(model_name)
    prompt = "Reply with 'LLM is working!' and nothing else."
    
    try:
        response = llm.get_completion([{"role": "user", "content": prompt}])
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_llm()
