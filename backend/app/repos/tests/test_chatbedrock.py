import os
from dotenv import load_dotenv

load_dotenv()

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage

def test_chatbedrock():
    api_base = os.getenv("LLM_API_BASE")
    model_id = os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b")
    if model_id.startswith("bedrock/"):
        model_id = model_id.split("bedrock/")[1]
        
    api_key = os.getenv("BEDROCK_SECRET_ACCESS_KEY") or os.getenv("BEDROCK_ACCESS_KEY_ID")
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    
    print(f"Testing ChatBedrockConverse with model: {model_id}, endpoint: {api_base}")
    try:
        chat = ChatBedrockConverse(
            model_id=model_id,
            region_name=region,
            endpoint_url=api_base,
            default_headers={"Authorization": f"Bearer {api_key}"},
            max_tokens=2000,
            temperature=0.0,
        )
        messages = [HumanMessage(content="Hello! Can you hear me?")]
        response = chat.invoke(messages)
        print("Response:", response.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chatbedrock()
