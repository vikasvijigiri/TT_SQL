from typing import Dict, Any, List, Optional, Set
from src.utils.logger import logger
from src.indexing.schema_indexer import SchemaIndexer

IMPORTANT_COLUMNS = [
    "modality",
    "compression",
    "embedding",
    "tissue",
    "cancer"
]

def force_sample(col: str) -> bool:
    """Check if a column must be sampled (Step 7)."""
    col_l = col.lower()
    return any(k in col_l for k in IMPORTANT_COLUMNS)

def quote_identifier(ident: str) -> str:
    """Quotes an identifier for Snowflake."""
    if ident.startswith('"') and ident.endswith('"'):
        return ident
    if "." in ident:
        return ".".join([f'"{p}"' for p in ident.split(".")])
    return f'"{ident}"'

def build_schema_with_samples(indexer: SchemaIndexer) -> Dict[str, Dict[str, Any]]:
    """
    Initial schema build from indexer metadata.
    """
    schema = {}
    for col_fqn, col_obj in indexer.columns.items():
        table = col_obj.table
        if table not in schema:
            schema[table] = {}
        schema[table][col_obj.column] = {
            "sample_values": getattr(col_obj, 'sample_values', []),
            "data_type": getattr(col_obj, 'data_type', 'TEXT')
        }
    return schema

def enrich_schema_for_candidates(db_executor, schema: Dict[str, Dict[str, Any]], db_name: str, candidate_columns: List[tuple], sample_limit: int = 100):
    """
    Selectively enriches candidate columns with sample values, with force sampling for key columns.
    """
    enriched_count = 0
    to_enrich = set(candidate_columns)
    
    for table, col in to_enrich:
        if table not in schema or col not in schema[table]:
            continue
            
        # Step 7 Logic: Force sample if column matches important keywords
        has_samples = len(schema[table][col].get("sample_values", [])) >= 3
        
        if has_samples and not force_sample(col):
            continue
            
        try:
            quoted_table = quote_identifier(table)
            quoted_col = quote_identifier(col)
            
            # Use the FQN for the table in the FROM clause
            query = f'SELECT DISTINCT {quoted_col} FROM {quoted_table} WHERE {quoted_col} IS NOT NULL LIMIT {sample_limit}'
            
            # Explicit debug for quoting (will show up in logs)
            if "DICOM" in table:
                logger.debug(f"Sampling Query: {query}")
                
            rows, error = db_executor.execute(query, db_name=db_name)
            
            if not error:
                samples = [list(r.values())[0] for r in rows if r]
                schema[table][col]["sample_values"] = samples
                enriched_count += 1
                
        except Exception:
            pass
            
    if enriched_count > 0:
        logger.info(f"Targeted enrichment complete: {enriched_count} columns updated with live samples.")
