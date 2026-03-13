"""
Generates data/retrieval_info.txt from the already-indexed metadata.
Run this AFTER populate_cloud_inference.py has successfully pushed to Qdrant.
"""
import json
import os
from app.services.logger import Logger

def format_table_document(table_name, table_info):
    doc_lines = [
        f"Table Name: {table_name}",
        f"Description: Schema information for table {table_name}. Contains tracking, metrics, and data about {table_name.replace('-', ' ')}.",
        "Columns:"
    ]
    for col in table_info.get("columns", []):
        col_name = col.get("column_name")
        data_type = col.get("type")
        doc_lines.append(f" - {col_name} ({data_type})")
    return " ".join(doc_lines)

def export_retrieval_info():
    from app.models.config import settings
    from app.models.paths import METADATA_DIR
    
    collection_name = settings.COLLECTION_NAME
    metadata_path = METADATA_DIR / f"{collection_name}.json"
    if not metadata_path.exists():
        metadata_path = METADATA_DIR / "metadata_injestion_files.json"
        
    output_path = METADATA_DIR / f"{collection_name}_retrieval_info.txt"

    if not metadata_path.exists():
        print(f"Error: {metadata_path} not found. Run extraction scripts first.")
        return

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    schema_name = metadata.get("schema", "public")
    tables = metadata.get("tables", {})
    embedding_model = settings.EMBEDDING_MODEL

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("=== Qdrant Vector DB Retrieval Info ===\n")
        out.write(f"Collection Name  : {collection_name}\n")
        out.write(f"Embedding Model  : {embedding_model}\n")
        out.write(f"Vector Dimension : 384 (Cosine Similarity)\n")
        out.write(f"Schema           : {schema_name}\n")
        out.write(f"Total Tables     : {len(tables)}\n")
        out.write("\n")
        out.write("=== How to Query ===\n")
        out.write("Run: python src/query_qdrant.py\n")
        out.write("The script accepts natural language questions and returns the most\n")
        out.write("semantically relevant table + columns from your database.\n")
        out.write("\n")
        out.write("=== Indexed Documents (Semantic Search Targets) ===\n")

        for i, (table_name, table_info) in enumerate(tables.items()):
            columns = table_info.get("columns", [])
            doc_text = format_table_document(table_name, table_info)
            out.write(f"\n{'='*60}\n")
            out.write(f"  Point ID : {i + 1}\n")
            out.write(f"  Table    : {table_name}\n")
            out.write(f"  Schema   : {schema_name}\n")
            out.write(f"  Columns  : {len(columns)}\n")
            out.write(f"\n  Columns List:\n")
            for col in columns:
                out.write(f"    - {col['column_name']} ({col['type']})\n")
            out.write(f"\n  Vectorized Document Text:\n")
            out.write(f"    {doc_text}\n")

    print(f"Successfully wrote retrieval info to: {output_path}")

if __name__ == "__main__":
    export_retrieval_info()
