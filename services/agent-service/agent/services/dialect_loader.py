import yaml
from agent.app.core.config import DIALECTS_DIR
from agent.services.logger import logger


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
            with open(dialect_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.cached_config[dialect] = config
                return config
        except Exception as e:
            logger.warning(f"Failed to load dialect config for {dialect}: {e}")
            return {}

    def load_dialect_reasoning(self, dialect: str) -> str:
        # 1. Load Static Reasoning from YAML
        config = self._get_config(dialect)
        static_reasoning = (
            (config.get("reasoning") or config.get("rules")) if config else []
        )

        formatted = f"DIALECT REASONING FOR {dialect.upper()}:\n"
        for r in static_reasoning:  # type: ignore
            if isinstance(r, dict):
                name = r.get("name", "Reasoning")
                rule = r.get("rule", "")
                formatted += f"- [Core] {name}: {rule}\n"
            elif isinstance(r, str):
                formatted += f"- [Core] {r}\n"

        examples = config.get("examples", []) if config else []
        if examples:
            formatted += "\nPRISTINE SYNTAX TEMPLATES (EXACT STRUCTURAL EXAMPLES):\n"
            for ex in examples:
                name = ex.get("name", "Template")
                sql = ex.get("sql", "").strip()
                formatted += f"\n=== [Template] {name} ===\n```sql\n{sql}\n```\n"

        return formatted

    def get_sanitizers(self, dialect: str) -> list:
        config = self._get_config(dialect)
        return config.get("sanitizers", [])

    def get_error_patterns(self, dialect: str) -> dict:
        config = self._get_config(dialect)
        return config.get("error_patterns", {})
