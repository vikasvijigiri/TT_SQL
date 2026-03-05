from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("QDRANT_URL")
api_key = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT_API")

client = QdrantClient(url=url, api_key=api_key)
# test query_points
try:
    dummy_vector = [0.1] * 768
    # Just a test call, might fail if collection doesn't exist but we check the attribute
    print(f"Has query_points: {hasattr(client, 'query_points')}")
    # results = client.query_points(collection_name="test", query=dummy_vector, limit=1)
except Exception as e:
    print(f"query_points call test: {e}")

