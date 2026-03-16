import requests
import json

url = "http://localhost:8000/api/stream"
payload = {
    "query": "test",
    "db_name": "acme-chatbot",
    "dataset_name": "sample.jsonl",
    "use_rag": True
}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
