from tt_sql.rag.vector_store import VectorStoreAgent
from tt_sql.core.llm_service import LLMService
import os
from dotenv import load_dotenv

load_dotenv()

def test_rag():
    agent = VectorStoreAgent()
    query = "Which materials (SKUs) had the highest order volume but failed OTIF?"
    print(f"Testing RAG with query: {query}")
    
    # Directly call the internal search logic to see raw results
    query_vector = agent.model.encode(query).tolist()
    print(f"Query vector size: {len(query_vector)}")
    
    raw_results = agent.client.query_points(
        collection_name=agent.collection_name,
        query=query_vector,
        using="text_embedding",
        limit=10,
        with_payload=True
    ).points
    
    print(f"Raw results count: {len(raw_results)}")
    for i, res in enumerate(raw_results):
        print(f"Result {i+1} [Score: {res.score}]: {res.payload}")
    
    # Now call the public method
    final_cols = agent.retrieve_relevant_columns(query)
    print(f"Final columns count: {len(final_cols)}")

if __name__ == "__main__":
    test_rag()
