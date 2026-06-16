from typing import Dict, Any, List
from src.indexing.schema_indexer import SchemaIndexer

def build_schema_with_samples(indexer: SchemaIndexer) -> Dict[str, Dict[str, Any]]:
    """
    Converts SchemaIndexer data into the structured schema format required by Resolver V2,
    preserving sample values for value-aware grounding.
    """
    schema = {}
    
    for col_fqn, col_obj in indexer.columns.items():
        table = col_obj.table
        if table not in schema:
            schema[table] = {}
        
        # Extract sample values from the indexer object
        samples = getattr(col_obj, 'sample_values', [])
        
        schema[table][col_obj.column] = {
            "sample_values": samples,
            "data_type": getattr(col_obj, 'data_type', 'TEXT')
        }
    
    # Mandatory Debug Check
    print("\n--- SCHEMA SAMPLES DEBUG ---")
    for table, cols in list(schema.items())[:2]: # Show first 2 tables
        print(f"Table: {table}")
        for col, info in list(cols.items())[:3]: # Show first 3 columns
            print(f"  {col}: {info['sample_values'][:5]}")
    print("----------------------------\n")
    
    return schema
