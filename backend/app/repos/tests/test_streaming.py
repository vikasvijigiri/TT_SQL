import os
import sys
from pathlib import Path
from app.services.logger import Logger
from app.models.paths import InstancePaths
from app.services.llm_service import LLMService

def test_streaming():
    load_dotenv()
    print("--- Bedrock Streaming Test ---")
    
    model_id = os.getenv("LLM_MODEL")
    print(f"Model: {model_id}")
    
    try:
        service = LLMService(model=model_id)
        messages = [{"role": "user", "content": "Write a short 3-sentence story about a data scientist."}]
        
        print("\nSending streaming request...")
        print("Yielded tokens: ", end="", flush=True)
        
        token_count = 0
        for token in service.get_completion_stream(messages):
            print(token, end="", flush=True)
            token_count += 1
            
        print(f"\n\nTotal tokens yielded: {token_count}")
        
        if token_count > 1:
            print("\n✅ Bedrock streaming verified successfully!")
        else:
            print("\n❌ Bedrock streaming failed (only one or no tokens yielded).")
            
    except Exception as e:
        import traceback
        print(f"\n❌ Exception during Bedrock streaming test: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_streaming()
