import os
import yaml
import json
from typing import List, Dict, Union, Any
from .paths import PROMPTS_DIR, PIPELINE_CONFIG

class PromptLoader:
    """
    Loads prompt templates from YAML files in the prompts directory.
    Uses centralized paths from paths.py module and caches results.
    """
    # Class-level caches for shared across instances/threads
    _TEMPLATE_CACHE = {}  # prompt_name -> template_data
    _GLOBAL_CONFIG_CACHE = None
    _JSON_FILE_CACHE = {} # path -> parsed_string

    def __init__(self, prompts_dir: str = None):
        self.prompts_dir = prompts_dir or str(PROMPTS_DIR)
        
        # 1. Warm global config cache if not already loaded
        if PromptLoader._GLOBAL_CONFIG_CACHE is None:
            PromptLoader._GLOBAL_CONFIG_CACHE = {}
            if os.path.exists(PIPELINE_CONFIG):
                try:
                    with open(PIPELINE_CONFIG, 'r') as f:
                        cfg = yaml.safe_load(f)
                        PromptLoader._GLOBAL_CONFIG_CACHE = cfg.get("prompts", {}).get("global", {})
                        # Also include general labels
                        PromptLoader._GLOBAL_CONFIG_CACHE.update(cfg.get("labels", {}))
                except Exception:
                    pass # Fallback to empty if config fails

    def load_prompt(self, prompt_name: str, **kwargs) -> List[Dict[str, str]]:
        """
        Loads a prompt by name (filename without extension), formats it with kwargs,
        and returns a list of messages.
        """
        # 1. Get or Load template data
        if prompt_name not in PromptLoader._TEMPLATE_CACHE:
            filename = f"{prompt_name}.yaml"
            file_path = os.path.join(self.prompts_dir, filename)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Prompt file not found: {file_path}")
                
            with open(file_path, 'r', encoding='utf-8') as f:
                PromptLoader._TEMPLATE_CACHE[prompt_name] = yaml.safe_load(f)
        
        template_data = PromptLoader._TEMPLATE_CACHE[prompt_name]
        
        # 2. Merge global configuration variables
        processed_kwargs = PromptLoader._GLOBAL_CONFIG_CACHE.copy()
        
        # 3. Process Keyword Arguments (with JSON file loading)
        for key, value in kwargs.items():
            if isinstance(value, str) and value.startswith('file://'):
                json_path = value.replace('file://', '')
                processed_kwargs[key] = self._get_cached_json_schema(json_path)
            else:
                processed_kwargs[key] = value
            
        # 4. Generate Messages
        messages = []
        if "messages" in template_data:
            for msg in template_data["messages"]:
                content = msg.get("content", "")
                try:
                    # Inject variables into template
                    formatted_content = content.format(**processed_kwargs)
                except KeyError as e:
                    raise KeyError(f"Missing argument for prompt '{prompt_name}': {e}")
                
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": formatted_content
                })
        return messages
    
    def _get_cached_json_schema(self, file_path: str) -> str:
        """Load a JSON file and return it as a formatted string, caching results."""
        abs_path = os.path.abspath(file_path)
        
        if abs_path not in PromptLoader._JSON_FILE_CACHE:
            if not os.path.exists(abs_path):
                return f"[File not found: {abs_path}]"
            
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Format as readable schema
                result = ""
                if isinstance(data, dict):
                    # Assume it's a schema dict: {table_name: [columns]}
                    schema_lines = []
                    for table, columns in data.items():
                        if isinstance(columns, list):
                            col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in columns]
                            schema_lines.append(f"{table}({', '.join(col_names)})")
                        else:
                            schema_lines.append(f"{table}: {columns}")
                    result = "\n".join(schema_lines)
                else:
                    result = json.dumps(data, indent=2)
                
                PromptLoader._JSON_FILE_CACHE[abs_path] = result
            except Exception as e:
                return f"[Error loading file {abs_path}: {e}]"
        
        return PromptLoader._JSON_FILE_CACHE[abs_path]
