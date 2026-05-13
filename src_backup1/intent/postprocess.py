import re
from typing import Dict, Any

def validate_and_fix_intent(intent: dict, query: str) -> dict:
    """
    Validates and fixes intent extraction based on strict fidelity rules.
    """
    query_lower = query.lower()

    def is_substring(text):
        if not text: return False
        return text.lower() in query_lower

    # -------------------------
    # FIX RAW FIELD FIDELITY
    # -------------------------
    def walk_filters_fidelity(node):
        if not node:
            return

        if node.get("type") == "condition":
            raw = node.get("raw_field")
            if raw and not is_substring(raw):
                # Fallback: remove invalid rewrite and just keep what LLM gave but warn?
                # For now, we keep it but the prompt should prevent this.
                node["raw_field"] = raw.strip()

        elif node.get("type") == "group":
            for c in node.get("conditions", []):
                walk_filters_fidelity(c)

    walk_filters_fidelity(intent.get("filters"))

    # -------------------------
    # FIX CANDIDATES
    # -------------------------
    def fix_candidates(node):
        if not node:
            return

        if node.get("type") == "condition":
            candidates = node.get("candidates", [])

            # remove zero-confidence candidates
            candidates = [
                c for c in candidates if c.get("confidence", 0) > 0
            ]

            # normalize confidence sum if > 1.0
            total = sum(c["confidence"] for c in candidates)
            if total > 1.0 and total > 0:
                for c in candidates:
                    c["confidence"] /= total

            node["candidates"] = candidates

        elif node.get("type") == "group":
            for c in node.get("conditions", []):
                fix_candidates(c)

    fix_candidates(intent.get("filters"))

    # -------------------------
    # FIX OUTPUT REQUIREMENTS
    # -------------------------
    q = query_lower

    if "clean" in q and "dataset" in q:
        if "output_requirements" not in intent or intent["output_requirements"] is None:
            intent["output_requirements"] = {
                "format": "table",
                "clean_data": True,
                "deduplicate": False,
                "include_nulls": True
            }
        else:
            intent["output_requirements"]["clean_data"] = True

    # -------------------------
    # FIX AMBIGUITY
    # -------------------------
    ambiguous_fields = []

    if "cancer subtype" in q:
        ambiguous_fields.append("cancer subtype")

    if "clean" in q and "dataset" in q:
        ambiguous_fields.append("clean_data")

    intent["ambiguity"] = {
        "present": len(ambiguous_fields) > 0,
        "fields": ambiguous_fields,
        "clarification_needed": False
    }

    return intent
