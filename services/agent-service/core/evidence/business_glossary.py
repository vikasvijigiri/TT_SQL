"""
business_glossary.py
--------------------
Domain-specific term mappings that help the schema linker and SQL generator
translate natural-language business terms into the exact DB literals used in
each dataset.

The glossary maps a canonical term (lowercase) to one or more possible DB
representations.  The pipeline's schema linker injects matched entries into
the LLM prompt so the model uses the right literals without probing.

Usage
-----
    from core.utils.business_glossary import BusinessGlossary

    gl = BusinessGlossary()
    hint = gl.lookup("churned customer")
    # -> "DB representations of 'churned customer': status IN ('churned', 'inactive', 'cancelled')"
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Built-in seed glossary (database-agnostic, curated from common benchmarks)
# ---------------------------------------------------------------------------

_SEED: Dict[str, List[str]] = {
    # Subscription status
    "active customer": ["active", "Active", "ACTIVE", "1", "true"],
    "inactive customer": ["inactive", "Inactive", "INACTIVE", "0", "false"],
    "churned customer": ["churned", "Churned", "cancelled", "Cancelled", "inactive"],
    "paying customer": ["paying", "subscribed", "premium", "active"],
    # Open source
    "most starred": ["ORDER BY stargazers_count DESC"],
    "most forked": ["ORDER BY forks_count DESC"],
    "open issue": ["state = 'open'", "state = 'opened'"],
    "closed issue": ["state = 'closed'"],
    # Music / media
    "album": ["release_type = 'Album'", "type = 'album'"],
    "single": ["release_type = 'Single'", "type = 'single'"],
    # Reviews
    "open business": ["is_open = 1", "is_open = true"],
    "closed business": ["is_open = 0", "is_open = false"],
    # Financial / stock
    "closing price": ["close", "Close", "adj_close"],
    "trading volume": ["volume", "Volume"],
    # Generic
    "null": ["NULL", "None", "nan", "--"],
    "yes": ["1", "true", "True", "Y", "yes"],
    "no": ["0", "false", "False", "N", "no"],
}


class BusinessGlossary:
    """Lightweight term-to-literal mapping with optional user-supplied overrides."""

    def __init__(self, overrides_path: Optional[str] = None):
        self._glossary: Dict[str, List[str]] = dict(_SEED)
        if overrides_path:
            self._load_overrides(overrides_path)
        else:
            # Auto-discover overrides file next to config/
            _auto = Path(__file__).parent.parent.parent / "config" / "business_glossary.json"
            if _auto.exists():
                self._load_overrides(str(_auto))

    def _load_overrides(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    self._glossary[k.lower()] = v if isinstance(v, list) else [str(v)]
        except Exception:
            pass

    def lookup(self, term: str) -> Optional[str]:
        """Return a prompt hint for *term*, or None if not found."""
        key = term.lower().strip()
        if key in self._glossary:
            vals = self._glossary[key]
            return f"DB representations of '{term}': {' OR '.join(vals)}"
        # Partial match: check if any glossary key is a substring of the term
        for gk, gv in self._glossary.items():
            if gk in key or key in gk:
                return f"DB representations of '{gk}' (matched from '{term}'): {' OR '.join(gv)}"
        return None

    def enrich_prompt(self, question: str) -> str:
        """Return a glossary hints block relevant to *question*, or empty string."""
        q_lower = question.lower()
        hits = []
        for term, vals in self._glossary.items():
            if term in q_lower:
                hits.append(f"  - '{term}' -> {vals}")
        if not hits:
            return ""
        return "BUSINESS GLOSSARY HINTS (use these exact literals):\n" + "\n".join(hits)

    def all_terms(self) -> List[str]:
        return list(self._glossary.keys())


# Module-level singleton
_default_glossary = BusinessGlossary()


def enrich_prompt_with_glossary(question: str) -> str:
    """Return glossary hints for *question* using the default glossary instance."""
    return _default_glossary.enrich_prompt(question)
