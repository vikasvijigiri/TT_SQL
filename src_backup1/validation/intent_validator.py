from typing import List, Dict, Any

def validate_intent(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Statically validates intent alignment. 
    Only flags misaligned conditions; does not modify anything.
    """
    errors = []

    filters = intent.get("filters") or {}
    conditions = filters.get("conditions", []) if isinstance(filters, dict) else getattr(filters, 'conditions', [])

    for cond in conditions:
        is_dict = isinstance(cond, dict)
        raw = (cond.get("raw_field") if is_dict else getattr(cond, 'raw_field', '')) or ""
        val = cond.get("value") if is_dict else getattr(cond, 'value', None)

        if val is None:
            continue

        # Rule: value should appear in raw_field
        val_str = str(val).lower()
        if val_str not in raw.lower():
            errors.append({
                "type": "misaligned_condition",
                "raw_field": raw,
                "value": val
            })

    return errors
