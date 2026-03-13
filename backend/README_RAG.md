# RAG Pipeline: Testing and Updates

This guide provides instructions on how to maintain, update, and test the advanced RAG architecture in the TT-SQL backend.

## Advanced RAG Architecture Overview

The system now implements a sophisticated RAG pipeline:
1.  **Hybrid Retrieval**: Combines Dense (Vector search via Qdrant) and Sparse (BM25) results.
2.  **RRF Fusion**: Merges results from both methods using Reciprocal Rank Fusion for optimal relevance.
3.  **Self-Healing**: Automatically expansion of queries via LLM if initial retrieval confidence is low.
4.  **Multi-Set Synthesis**: Provides three distinct sets (Set A, B, C) to downstream SQL generation agents.

---

## 1. Updating the Knowledge Base

When the database schema changes or you want to refresh the RAG context, follow these steps:

### Phase 1: Preparation (Extract & Enrich)
Extracts the schema from PostgreSQL and uses an LLM to generate business descriptions for every column.

```bash
# Full preparation (Extraction + LLM Enrichment + Ingestion)
python scripts/prep_knowledge.py --overwrite --workers 10
```

*   `--overwrite`: Forces a fresh extraction even if local metadata exists.
*   `--no-enrich`: Skip the LLM description phase (useful for quick updates).
*   `--workers`: Number of parallel threads for LLM calls.

### Phase 2: Targeted Updates (Optional)
If you only need to update specific parts:

```bash
# Just extract and enrich a specific schema
python scripts/run_extract_enrich.py --enrich --workers 5 --output my_schema.json

# Just ingest an existing metadata file into Qdrant
python scripts/populate_vector_store.py --path app/repositories/data/metadata_extracts/my_schema.json
```

---

## 2. Testing Retrieval Manually

You can test the RAG retrieval logic in isolation using the `rag_service.py` CLI. This is the best way to verify if the correct columns are being retrieved for a specific question.

```bash
# Test a specific question
python app/services/engines/rag_service.py --question "Show all accounts in standard customer segment" --instance-id test_001
```

**What to look for in the logs:**
-   **Preprocessing**: Tokenization and normalization.
-   **Sparse Retrieval**: BM25 scores for keywords.
-   **Dense Retrieval**: Qdrant vector search matches.
-   **Fusion**: The final RRF (Reciprocal Rank Fusion) scores.
-   **Self-Healing**: Look for "Expanding query..." if the initial context was considered insufficient.

**Output Location**: Results are saved to `backend/results/retrievals/test_001.json`.

---

## 3. Configuration

Key RAG settings are located in `backend/app/repositories/config.py` or `.env`:

-   `EMBEDDING_MODEL`: The local model used for dense vectors (e.g., `sentence-transformers/all-MiniLM-L6-v2`).
-   `COLLECTION_NAME`: The default Qdrant collection to query.
-   `QDRANT_URL` & `QDRANT_API_KEY`: Connection details for your Qdrant instance.

---

## 4. Troubleshooting

-   **Low Recall**: Ensure your metadata is enriched (run `prep_knowledge.py` without `--no-enrich`). BM25 relies heavily on descriptions.
-   **Performance**: Hybrid retrieval adds a sparse search step locally. Ensure your `BM25Okapi` index is cached (the service does this automatically per collection).
-   **Qdrant Errors**: Verify your API key and URL. Check if the collection name exists in the Qdrant UI.
