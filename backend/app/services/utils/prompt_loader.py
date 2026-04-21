import os
import yaml
import functools
from typing import List, Dict, Union, Any
from app.repositories.registry.paths import PROMPTS_DIR
from app.repositories.config import settings


@functools.lru_cache(maxsize=32)
def _load_yaml_cached(file_path: str) -> dict:
    """Cached YAML file loader â€” eliminates repeated disk I/O across pipeline calls."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=32)
def _load_json_cached(file_path: str) -> dict:
    """Cached JSON file loader for schema-in-prompt injections."""
    import json
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


class PromptLoader:
    """
    Loads prompt templates from YAML files in the prompts directory.
    Uses centralized paths from paths.py module.
    """
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            self.prompts_dir = str(PROMPTS_DIR)
        else:
            self.prompts_dir = str(prompts_dir)

    def load_prompt(self, prompt_name: str, sub_key: str = None, **kwargs) -> List[Dict[str, str]]:
        """
        Loads a prompt by name (filename without extension), formats it with kwargs,
        and returns a list of messages.
        """
        filename = f"{prompt_name}.yaml"
        file_path = os.path.join(self.prompts_dir, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        # Inject global variables from settings if not overridden
        if "product_name" not in kwargs:
            kwargs["product_name"] = settings.PRODUCT_NAME
        if "product_role" not in kwargs:
            kwargs["product_role"] = settings.PRODUCT_ROLE

        # Process kwargs to load file references
        processed_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str) and value.startswith('file://'):
                json_path = value.replace('file://', '')
                processed_kwargs[key] = self._load_json_file(json_path)
            else:
                processed_kwargs[key] = value
            
        # Use LRU-cached YAML load — no repeated disk reads
        full_data = _load_yaml_cached(file_path)
            
        # Select data based on sub_key
        template_data = full_data[sub_key] if sub_key else full_data
            
        messages = []
        
        # Handle 'messages' list format
        if "messages" in template_data:
            for msg in template_data["messages"]:
                content = msg.get("content", "")
                # Format the content with provided kwargs safely
                try:
                    # Use a safer formatting approach that doesn't crash on literal braces
                    # This only replaces {key} if key is in processed_kwargs
                    import re
                    pattern = re.compile(r'\{([a-zA-Z0-9_]+)\}')
                    def replace_match(match):
                        key = match.group(1)
                        return str(processed_kwargs.get(key, match.group(0)))
                    
                    formatted_content = pattern.sub(replace_match, content)
                except Exception as e:
                    raise RuntimeError(f"Formatting failed for prompt '{prompt_name}': {e}")
                
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": formatted_content
                })
        else:
            # Fallback or other formats?
            pass
            
        return messages
    
    def _load_json_file(self, file_path: str) -> str:
        """Load a JSON file and return it as a formatted string using LRU caching."""
        from app.services.utils.logger import Logger
        
        if not os.path.exists(file_path):
            Logger.log(f"WARNING: JSON file not found: {file_path}", level="WARNING")
            return f"[File not found: {file_path}]"
        
        try:
            # Use cached JSON load
            data = _load_json_cached(file_path)
            
            # Format as readable schema
            if isinstance(data, dict):
                # Assume it's a schema dict: {table_name: [columns]}
                schema_lines = []
                for table, columns in data.items():
                    if isinstance(columns, list):
                        col_details = []
                        for c in columns:
                            if isinstance(c, dict):
                                cname = c.get("column_name") or c.get("name") or "unknown"
                                ctype = c.get("type") or c.get("data_type") or ""
                                cdesc = c.get("description") or ""
                                detail = f"{cname} ({ctype})" if ctype else cname
                                if cdesc:
                                    detail += f" -- {cdesc}"
                                col_details.append(detail)
                            else:
                                col_details.append(str(c))
                        schema_lines.append(f"Table: {table}\n - " + "\n - ".join(col_details))
                    else:
                        schema_lines.append(f"{table}: {columns}")
                return "\n\n".join(schema_lines)
            else:
                return json.dumps(data, indent=2)
        except Exception as e:
            return f"[Error loading file {file_path}: {e}]"
