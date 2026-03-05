import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from tt_sql.rag.vector_store import VectorStoreAgent
from tt_sql.core.logger import Logger

def test_retrieval():
    load_dotenv()
    
    agent = VectorStoreAgent()
    question = "Which customers have the lowest OTIF performance this month?"
    limit = 2
    
    Logger.log(f"Testing retrieval for: '{question}' with limit={limit} per type")
    results = agent.retrieve_relevant_columns(question, limit=limit)
    
    if not results:
        print("No results returned.")
        return

    print(f"\nRetrieved {len(results)} columns:")
    type_counts = {}
    for res in results:
        t = res['type']
        type_counts[t] = type_counts.get(t, 0) + 1
        print(f" - {res['table_name']}.{res['column_name']} ({t})")
    
    print("\nType counts:")
    for t, count in type_counts.items():
        print(f" - {t}: {count}")
        if count > limit:
            print(f"FAIL: Type '{t}' exceeded limit of {limit}")
        else:
            print(f"PASS: Type '{t}' is within limit")

if __name__ == "__main__":
    test_retrieval()
