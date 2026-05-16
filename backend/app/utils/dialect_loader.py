import yaml
import os
from pathlib import Path
from backend.app.core.config import DIALECTS_DIR
from backend.app.utils.logger import logger

class DialectLoader:
    def __init__(self):
        self.dialects_dir = DIALECTS_DIR
        self.cached_config = {}

    def _get_config(self, dialect: str) -> dict:
        if dialect in self.cached_config:
            return self.cached_config[dialect]
        
        dialect_file = self.dialects_dir / f"{dialect.lower()}.yaml"
        if not dialect_file.exists():
            return {}
            
        try:
            with open(dialect_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.cached_config[dialect] = config
                return config
        except Exception as e:
            logger.warning(f"Failed to load dialect config for {dialect}: {e}")
            return {}

    def load_dialect_reasoning(self, dialect: str) -> str:
        # 1. Load Static Reasoning from YAML
        config = self._get_config(dialect)
        static_reasoning = (config.get('reasoning') or config.get('rules')) if config else []
        
        formatted = f"DIALECT REASONING FOR {dialect.upper()}:\n"
        for r in static_reasoning:
            if isinstance(r, dict):
                name = r.get('name', 'Reasoning')
                rule = r.get('rule', '')
                formatted += f"- [Core] {name}: {rule}\n"
            elif isinstance(r, str):
                formatted += f"- [Core] {r}\n"
        
        # 2. Load Global Reasoning Patterns (.yaml)
        from backend.app.core.config import MEMORY_DIR
        generic_file = MEMORY_DIR / "reasoning" / "generic.yaml"
        if generic_file.exists():
            try:
                with open(generic_file, 'r', encoding='utf-8') as f:
                    generic_rules = yaml.safe_load(f)
                    if generic_rules:
                        formatted += "\nGLOBAL REASONING PATTERNS:\n"
                        for r in generic_rules:
                            formatted += f"- {r}\n"
            except Exception as e:
                logger.warning(f"Failed to load generic rules (.yaml): {e}")

        # 3. Load Dynamic Dialect Patterns from Memory (.yaml)
        dynamic_file = MEMORY_DIR / "dialects" / f"{dialect.lower()}.yaml"
        if dynamic_file.exists():
            try:
                with open(dynamic_file, 'r', encoding='utf-8') as f:
                    dynamic_rules = yaml.safe_load(f)
                    if dynamic_rules:
                        formatted += f"\nLEARNED {dialect.upper()} PATTERNS:\n"
                        for r in dynamic_rules:
                            # Strip any legacy tags to maintain pure reasoning format
                            rule_text = r.replace('[Dialect Rule]', '').replace('[Learned]', '').strip()
                            formatted += f"- {rule_text}\n"
            except Exception as e:
                logger.warning(f"Failed to load dynamic rules (.yaml) in loader: {e}")
                
        return formatted

    def get_sanitizers(self, dialect: str) -> list:
        config = self._get_config(dialect)
        return config.get('sanitizers', [])

    def get_error_patterns(self, dialect: str) -> dict:
        config = self._get_config(dialect)
        return config.get('error_patterns', {})
