import yaml
import os

class DialectLoader:
    @staticmethod
    def load_dialect_rules(dialect: str) -> str:
        dialect_path = f"resources/dialects/{dialect.lower()}.yaml"
        if not os.path.exists(dialect_path):
            return f"No specific rules for dialect: {dialect}"
            
        with open(dialect_path, 'r') as f:
            data = yaml.safe_load(f)
            
        rules = data.get('rules', [])
        formatted = f"### {dialect.upper()} DIALECT RULES:\n"
        for r in rules:
            formatted += f"- {r['name']}: {r['rule']}\n"
        return formatted
