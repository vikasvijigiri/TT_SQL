from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.engines.llm_service import LLMService
from app.services.utils.logger import Logger

class EnrichmentService:
    def __init__(self, llm_service=None):
        self.llm = llm_service or LLMService()
        self.logger = Logger

    def enrich_metadata(self, metadata: Dict[str, Any], max_workers: int = 5) -> Dict[str, Any]:
        """Uses LLM to generate business descriptions for database columns."""
        self.logger.log(f"Enriching metadata with {max_workers} workers...")
        
        def enrich_table(table_name, columns):
            col_list_str = "\n".join([
                f"- {c['column_name']} ({c['type']}). Samples: {c['sample_values']}" 
                for c in columns
            ])
            system_prompt = (
                "You are a Senior Data Analyst. Provide concise (1-2 lines), business-oriented descriptions "
                "for the following database columns. Expand abbreviations and use sample values for context."
                "\n\nOutput ONLY a valid JSON object: {\"column_name\": \"description\"}"
            )
            user_prompt = f"Table: {table_name}\nColumns:\n{col_list_str}"
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                return self.llm.get_json_completion(messages)
            except Exception as e:
                self.logger.log(f"Failed to enrich {table_name}: {e}", level="WARN")
                return {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_table = {
                executor.submit(enrich_table, t_name, t_info["columns"]): t_name
                for t_name, t_info in metadata["tables"].items()
            }
            for future in as_completed(future_to_table):
                table_name = future_to_table[future]
                descriptions = future.result()
                if descriptions:
                    for col in metadata["tables"][table_name]["columns"]:
                        name = col["column_name"]
                        col["description"] = descriptions.get(name, f"Data for {name}")
        return metadata

if __name__ == "__main__":
    import argparse
    import json
    import os
    
    parser = argparse.ArgumentParser(description="Standalone Metadata Enrichment Tool")
    parser.add_argument("--input", type=str, required=True, help="Path to raw metadata JSON")
    parser.add_argument("--output", type=str, help="Path to save enriched metadata JSON")
    parser.add_argument("--workers", type=int, default=5, help="Number of parallel workers")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        exit(1)
        
    with open(args.input, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        
    service = EnrichmentService()
    enriched = service.enrich_metadata(metadata, max_workers=args.workers)
    
    output_path = args.output or args.input.replace(".json", "_enriched.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=4)
    print(f"Enriched metadata saved to {output_path}")
