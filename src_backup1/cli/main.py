import argparse
import sys
import os

# Add project root to path to allow absolute imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.pipeline import Text2SQLPipeline
from src.utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description="Deterministic Text2SQL CLI")
    parser.add_argument("query", type=str, help="Natural language query")
    parser.add_argument("--metadata", type=str, default="metadata.json", help="Path to schema metadata JSON")
    
    args = parser.parse_args()
    
    # Create dummy metadata if it doesn't exist for demo purposes
    if not os.path.exists(args.metadata):
        import json
        dummy_data = [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "INTEGER", "sample_values": [1, 2, 3]},
                    {"name": "name", "type": "STRING", "sample_values": ["Alice", "Bob"]},
                    {"name": "age", "type": "INTEGER", "sample_values": [25, 30, 35]}
                ]
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "INTEGER", "sample_values": [101, 102]},
                    {"name": "user_id", "type": "INTEGER", "sample_values": [1, 2]},
                    {"name": "total", "type": "FLOAT", "sample_values": [99.99, 50.0]}
                ]
            }
        ]
        with open(args.metadata, 'w') as f:
            json.dump(dummy_data, f, indent=2)
        logger.info(f"Created dummy metadata at {args.metadata}")

    pipeline = Text2SQLPipeline(args.metadata)
    result = pipeline.run(args.query)
    
    print("\n" + "="*50)
    print(f"QUERY: {args.query}")
    print(f"SQL:   {result.sql}")
    if result.error:
        print(f"ERROR: {result.error}")
    else:
        print(f"ROWS:  {len(result.rows)}")
    print(f"CONFIDENCE: {result.confidence:.2f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
