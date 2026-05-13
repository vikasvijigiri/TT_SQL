from typing import Dict, Any, List

def repair_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal and safe repair. 
    Only performs deduplication to prevent redundant filters.
    Does NOT attempt contextual splitting or modification.
    """
    conditions = intent.get("filters", {}).get("conditions", [])
    if not conditions:
        return intent

    seen = set()
    cleaned = []

    for c in conditions:
        is_dict = isinstance(c, dict)
        raw = (c.get("raw_field") if is_dict else getattr(c, 'raw_field', '')) or ""
        val = str(c.get("value") if is_dict else getattr(c, 'value', None))
        
        # Deduplicate by (raw_field, value)
        key = (raw.lower().strip(), val.lower().strip())
        if key not in seen:
            seen.add(key)
            cleaned.append(c)

    if isinstance(intent.get("filters"), dict):
        intent["filters"]["conditions"] = cleaned
    else:
        intent.filters.conditions = cleaned
        
    return intent
