"""
Multi-DB Alias Registry

Provides a single source of truth for database aliases across all agents,
preventing hardcoded aliases and multi-db naming confusion.
"""

from typing import Optional, Dict

class AliasRegistry:
    # Canonical mapping of known business contexts to their specific database alias
    _REGISTRY: Dict[str, str] = {
        "sales": "sales_pipeline",
        "support": "support_db",
        "products": "products_orders_db",
        "activities": "activities_db",
        "crm": "core_crm_db",
        "knowledge": "knowledge_db",
        "finance": "finance_db"
    }

    @classmethod
    def get_canonical_alias(cls, context_key: str) -> Optional[str]:
        """
        Retrieve the canonical database alias for a given context key.
        E.g., 'sales' -> 'sales_pipeline'
        """
        # Normalize key
        normalized_key = str(context_key).lower().strip()
        
        # Exact match
        if normalized_key in cls._REGISTRY:
            return cls._REGISTRY[normalized_key]
            
        # Reverse lookup (if they passed the canonical alias directly)
        if normalized_key in cls._REGISTRY.values():
            return normalized_key
            
        # Fallback heuristic for partial matches
        for key, value in cls._REGISTRY.items():
            if key in normalized_key or normalized_key in value:
                return value
                
        return None

    @classmethod
    def validate_alias(cls, alias: str) -> bool:
        """
        Check if the given alias is a known canonical alias.
        """
        normalized_alias = str(alias).lower().strip()
        return normalized_alias in cls._REGISTRY.values()

    @classmethod
    def all_canonical_aliases(cls) -> list[str]:
        """Return all valid canonical aliases."""
        return list(cls._REGISTRY.values())

    @classmethod
    def register_alias(cls, context_key: str, canonical_alias: str) -> None:
        """
        Dynamically register a new alias mapping.
        """
        cls._REGISTRY[context_key.lower().strip()] = canonical_alias.lower().strip()

# Global singleton instance if needed, though class methods suffice
alias_registry = AliasRegistry()
