import yaml
import os
from backend.app.core.config import get_dialect_path

class DialectLoader:
    @staticmethod
    def load_dialect_rules(dialect: str) -> str:
        dialect_path = get_dialect_path(dialect)
        if not os.path.exists(dialect_path):
            return f"No specific rules for dialect: {dialect}"
            
        with open(dialect_path, 'r') as f:
            data = yaml.safe_load(f)
            
        rules = data.get('rules', [])
        formatted = f"### {dialect.upper()} DIALECT RULES:\n"
        for r in rules:
            formatted += f"- {r['name']}: {r['rule']}\n"
        return formatted
