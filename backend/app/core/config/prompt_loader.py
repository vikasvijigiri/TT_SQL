import os
import yaml
import json
import functools
import re
from typing import List, Dict, Optional, Any
from app.core.config.settings import settings
from app.core.logging.logger import Logger
from app.infrastructure.storage.path_manager import StorageManager

@functools.lru_cache(maxsize=32)
def _load_yaml_cached(file_path: str) -> dict:
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@functools.lru_cache(maxsize=32)
def _load_json_cached(file_path: str) -> dict:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

class PromptLoader:
    """
    Handles loading and formatting of LLM prompt templates from YAML files.
    Injects global product identity and supports dynamic file-based schema hydration.
    """
    def __init__(self, prompts_dir: Optional[str] = None):
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # Default to app/services/prompts or similar
            from app.infrastructure.storage.path_manager import PROJECT_ROOT
            self.prompts_dir = PROJECT_ROOT / "app/services/prompts"

    def load_prompt(self, prompt_name: str, sub_key: Optional[str] = None, **kwargs) -> List[Dict[str, str]]:
        file_path = self.prompts_dir / f"{prompt_name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template missing: {file_path}")
        
        # Identity Injection
        kwargs.setdefault("product_name", settings.PRODUCT_NAME)
        kwargs.setdefault("product_role", settings.PRODUCT_ROLE)

        # Content Formatting
        data = _load_yaml_cached(str(file_path))
        messages_template = data[sub_key]["messages"] if sub_key else data["messages"]
        
        formatted_messages = []
        for msg in messages_template:
            content = msg.get("content", "")
            # Safe formatting: Only replace keys that exist in kwargs
            formatted_content = re.sub(
                r'\{([a-zA-Z0-9_]+)\}',
                lambda m: str(kwargs.get(m.group(1), m.group(0))),
                content
            )
            formatted_messages.append({
                "role": msg.get("role", "user"),
                "content": formatted_content
            })
            
        return formatted_messages

    def _format_schema_file(self, file_path: str) -> str:
        """Helper to convert JSON schema files into LLM-readable text descriptions."""
        try:
            data = _load_json_cached(file_path)
            if not isinstance(data, dict): return json.dumps(data, indent=2)
            
            lines = []
            for table, info in data.items():
                cols = info.get("columns", []) if isinstance(info, dict) else info
                col_strs = []
                for c in cols:
                    if isinstance(c, dict):
                        name = c.get("column_name", "unknown")
                        ctype = c.get("type", "")
                        col_strs.append(f"{name} ({ctype})" if ctype else name)
                    else:
                        col_strs.append(str(c))
                lines.append(f"Table {table}: {', '.join(col_strs)}")
            return "\n".join(lines)
        except Exception as e:
            Logger.log(f"Schema Injection Failed: {e}", level="ERROR")
            return f"[Error: {e}]"
