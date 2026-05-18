import re
from typing import List, Dict, Any, Optional
from backend.app.models.schemas import SemanticColumn, SemanticTable

class SemanticTagger:
    """
    Enterprise semantic ontology layer. Analyzes column names, descriptions, and
    nested variant keys to assign standardized domain tags (genomics, clinical,
    geospatial, financial, temporal).
    """
    def __init__(self):
        self.ontology_rules: Dict[str, List[str]] = {
            "genomic_chromosome": ["reference_name", "chrom", "chr", "contig"],
            "genomic_position": ["start", "end", "pos", "position", "locus", "start_position", "end_position"],
            "genomic_variant": ["alt", "ref", "allele", "snv", "indel", "mutation", "snp", "variant_id"],
            "genotype_array": ["genotype", "gt", "calls", "genotype_calls", "pl"],
            "sample_id": ["sample_id", "sample_barcode", "case_barcode", "call_set_name", "biospecimen", "aliquot_barcode", "subject_id"],
            "geospatial": ["latitude", "longitude", "lat", "lon", "coordinates", "geometry", "geography", "wkt", "geojson", "bounding_box"],
            "temporal": ["created_at", "updated_at", "timestamp", "date", "year", "month", "day", "hour", "time", "event_date"],
            "financial": ["price", "amount", "cost", "revenue", "tax", "fee", "balance", "total", "subtotal", "currency"],
            "demographic": ["age", "gender", "sex", "race", "ethnicity", "country", "state", "city", "zip", "postal_code"],
            "clinical": ["diagnosis", "stage", "grade", "survival", "tumor", "status", "disease", "treatment", "therapy", "recurrence"]
        }

    def tag_column(self, col: SemanticColumn) -> List[str]:
        tags = []
        c_name = col.name.lower().replace('"', '')
        c_desc = (col.description or "").lower()

        for tag_name, keywords in self.ontology_rules.items():
            if any(kw == c_name or c_name.endswith(f".{kw}") or f"_{kw}" in c_name or f"{kw}_" in c_name for kw in keywords):
                tags.append(tag_name)
            elif any(f" {kw} " in f" {c_desc} " for kw in keywords):
                if tag_name not in tags:
                    tags.append(tag_name)

        # Check nested keys for variant columns
        if col.nested_keys:
            nested_str = " ".join(col.nested_keys).lower()
            if "genotype" in nested_str and "genotype_array" not in tags:
                tags.append("genotype_array")
            if "call_set_name" in nested_str and "sample_id" not in tags:
                tags.append("sample_id")

        return tags

    def enrich_column(self, col: SemanticColumn) -> SemanticColumn:
        tags = self.tag_column(col)
        if tags:
            tag_str = f"[Ontology: {', '.join(tags)}]"
            if not col.description:
                col.description = tag_str
            elif "[Ontology:" not in col.description:
                col.description = f"{tag_str} {col.description}"
        return col

    def enrich_table(self, table: SemanticTable) -> SemanticTable:
        enriched_cols = [self.enrich_column(c) for c in table.columns]
        table.columns = enriched_cols
        return table
