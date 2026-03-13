import os
import sys
import time
from pathlib import Path
from app.services.logger import Logger
from app.models.paths import InstancePaths
from app.services.pipeline_service import run_analysis_pipeline

# Add src to path
# from app.services.llm_service import LLMService

def test_streaming_timing():
    # load_dotenv() # This call is removed as load_dotenv is no longer imported
    print("--- Bedrock Streaming Timing Test ---")
    
    model_id = os.getenv("LLM_MODEL")
    print(f"Model: {model_id}")
    
    try:
        service = LLMService(model=model_id)
        messages = [{"role": "user", "content": "Write a 50-word story about a cat."}]
        
        print("\nSending streaming request...")
        
        start_time = time.time()
        first_token_time = None
        token_count = 0
        
        for token in service.get_completion_stream(messages):
            if first_token_time is None:
                first_token_time = time.time()
                print(f"\nFirst token received after {first_token_time - start_time:.2f}s")
            
            # print(token, end="", flush=True) # Don't clutter, we want to see timing
            token_count += 1
            
        end_time = time.time()
        print(f"\nLast token received after {end_time - start_time:.2f}s")
        print(f"Total tokens: {token_count}")
        print(f"Average time per token: {(end_time - first_token_time) / (token_count - 1) if token_count > 1 else 0:.4f}s")
        
        if first_token_time and (end_time - first_token_time) > 0.5:
             print("\n✅ Streaming detected (tokens arrived over time).")
        else:
             print("\n❌ NOT STREAMING (tokens arrived all at once or too fast).")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    test_streaming_timing()
