from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("QDRANT_URL")
api_key = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT_API")
collection_name = os.getenv("QDRANT_COLLECTION", "acme-chatbot")

client = QdrantClient(url=url, api_key=api_key)

print(f"Checking collection: {collection_name}")
try:
    coll_info = client.get_collection(collection_name)
    print(f"Collection Info: {coll_info.config.params.vectors}")
    
    count = client.count(collection_name=collection_name).count
    print(f"Total points: {count}")
    
    # Scroll through some points
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=5,
        with_payload=True,
        with_vectors=False
    )
    
    for p in points:
        print(f"ID: {p.id}")
        print(f"Payload: {p.payload}")
        print("-" * 20)
except Exception as e:
    print(f"Error: {e}")
