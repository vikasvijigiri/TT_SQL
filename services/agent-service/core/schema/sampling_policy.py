from typing import List
from pydantic import BaseModel
from agent.contracts.schemas import SemanticColumn


class ColumnStatsSummary(BaseModel):
    cardinality_category: str  # "HIGH", "MEDIUM", "LOW", "BOOLEAN"
    is_nullable: bool
    inferred_semantic_type: (
        str  # e.g. "CATEGORICAL", "CONTINUOUS", "IDENTIFIER", "VARIANT_JSON"
    )
    nested_key_count: int


class SchemaSamplingPolicy:
    """
    Enterprise sampling policy layer. Strictly controls when sample values or
    statistical summaries are injected into prompts, preventing raw row flooding.
    """

    def __init__(self, always_allow_identifiers: bool = True):
        self.always_allow_identifiers = always_allow_identifiers

    def infer_column_stats(self, col: SemanticColumn) -> ColumnStatsSummary:
        c_type = col.type.upper()
        s_vals = col.sample_values

        # Infer cardinality
        if len(s_vals) <= 2 and any(
            str(v).lower() in ("true", "false", "0", "1", "yes", "no") for v in s_vals
        ):
            card = "BOOLEAN"
            sem = "CATEGORICAL"
        elif len(s_vals) < 5:
            card = "LOW"
            sem = "CATEGORICAL"
        elif len(s_vals) < 15:
            card = "MEDIUM"
            sem = "CATEGORICAL"
        else:
            card = "HIGH"
            sem = (
                "CONTINUOUS"
                if any(t in c_type for t in ("INT", "FLOAT", "NUM", "DEC"))
                else "IDENTIFIER"
            )

        if "VARIANT" in c_type or "JSON" in c_type or bool(col.nested_keys):
            sem = "VARIANT_JSON"

        return ColumnStatsSummary(
            cardinality_category=card,
            is_nullable=True,  # default safe assumption
            inferred_semantic_type=sem,
            nested_key_count=len(col.nested_keys),
        )

    def should_include_samples(
        self, col: SemanticColumn, query_intent_terms: List[str] | None = None
    ) -> bool:
        """
        Determines if actual sample values should be exposed in the prompt.
        Only returns True if there is potential ambiguity or category matching needed.
        """
        stats = self.infer_column_stats(col)

        # If it's a variant/json column, we rely on signature, not sample strings
        if stats.inferred_semantic_type == "VARIANT_JSON":
            return False

        # If it's continuous numbers (like prices, timestamps), samples don't help semantic matching
        if stats.inferred_semantic_type == "CONTINUOUS":
            return False

        # If it's low/medium cardinality categorical, samples are highly valuable for exact WHERE filtering
        if stats.inferred_semantic_type == "CATEGORICAL":
            return True

        # If query terms overlap with column name or description, allow samples to help grounding
        if query_intent_terms:
            col_full_text = (col.name + " " + (col.description or "")).lower()
            if any(term.lower() in col_full_text for term in query_intent_terms):
                return True

        return self.always_allow_identifiers

    def sanitize_sample_values(
        self, col: SemanticColumn, max_length: int = 50
    ) -> List[str]:
        """
        Strips huge string payloads or JSON strings from sample values.
        """
        clean = []
        for val in col.sample_values:
            val_str = str(val).strip()
            if not val_str or (val_str.startswith("{") and val_str.endswith("}")):
                continue
            if len(val_str) > max_length:
                val_str = val_str[: max_length - 3] + "..."
            if val_str not in clean:
                clean.append(val_str)
        return clean
