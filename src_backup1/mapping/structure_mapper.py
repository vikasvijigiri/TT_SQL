import json
from typing import List, Dict, Any, Optional
from src.core.models import Intent, CandidateColumn, ColumnMapping
from src.indexing.schema_indexer import SchemaIndexer
from src.utils.logger import logger

class StructureAwareMapper:
    """Tier 2: Advanced Mapper. Explores JSON and Arrays."""
    def __init__(self, indexer: SchemaIndexer):
        self.indexer = indexer

    def map(self, intent: Intent, external_knowledge: str = "") -> List[ColumnMapping]:
        mappings = []
        
        # 1. Map Filters (Value based grounding for JSON/Arrays)
        for filt in intent.flatten_filters():
            if filt.value:
                # We can't use search_values anymore, but Indexer.search handles values too
                val_results = self.indexer.search(str(filt.value), top_k=20)
                for col, score in val_results:
                    if col.json_paths or col.is_array:
                        mappings.append(ColumnMapping(
                            source_type="filter",
                            source_name=filt.field or str(filt.value),
                            column=col,
                            confidence=0.8
                        ))

        # 2. Map Entities (Path based matching)
        for entity in intent.entities:
            # Check structure index
            for table_name, columns in self.indexer.structure_index.items():
                for col in columns:
                    if entity.lower() in col.column.lower() or \
                       any(entity.lower() in p.lower() for p in col.json_paths):
                        mappings.append(ColumnMapping(
                            source_type="entity",
                            source_name=entity,
                            column=col,
                            confidence=0.6
                        ))
        
        logger.info(f"Tier 2 Mapping: Produced {len(mappings)} mappings.")
        return mappings
