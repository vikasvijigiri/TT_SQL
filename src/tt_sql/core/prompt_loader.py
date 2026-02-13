import os
import yaml
from typing import List, Dict, Union, Any
from .paths import PROMPTS_DIR

class PromptLoader:
    """
    Loads prompt templates from YAML files in the prompts directory.
    Uses centralized paths from paths.py module.
    """
    def __init__(self, prompts_dir: str = None):
        if prompts_dir is None:
            # Use centralized path from paths.py
            self.prompts_dir = str(PROMPTS_DIR)
        else:
            self.prompts_dir = prompts_dir

    def load_prompt(self, prompt_name: str, **kwargs) -> List[Dict[str, str]]:
        """
        Loads a prompt by name (filename without extension), formats it with kwargs,
        and returns a list of messages.
        
        Special handling for file paths:
        - If a kwarg value starts with 'file://', load the JSON file and use its content
        """
        filename = f"{prompt_name}.yaml"
        file_path = os.path.join(self.prompts_dir, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
        
        # Process kwargs to load file references
        processed_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str) and value.startswith('file://'):
                # Load JSON file
                json_path = value.replace('file://', '')
                processed_kwargs[key] = self._load_json_file(json_path)
            else:
                processed_kwargs[key] = value
            
        with open(file_path, 'r', encoding='utf-8') as f:
            template_data = yaml.safe_load(f)
            
        messages = []
        
        # Handle 'messages' list format
        if "messages" in template_data:
            for msg in template_data["messages"]:
                content = msg.get("content", "")
                # Format the content with provided kwargs
                try:
                    formatted_content = content.format(**processed_kwargs)
                except KeyError as e:
                    # If a key is missing, we might want to let it fail or invalid formatting
                    # For now let it raise, as prompts expect specific keys
                    raise KeyError(f"Missing argument for prompt '{prompt_name}': {e}")
                
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": formatted_content
                })
        else:
            # Fallback or other formats?
            pass
            
        return messages
    
    def _load_json_file(self, file_path: str) -> str:
        """Load a JSON file and return it as a formatted string"""
        import json
        
        if not os.path.exists(file_path):
            return f"[File not found: {file_path}]"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Format as readable schema
            if isinstance(data, dict):
                # Assume it's a schema dict: {table_name: [columns]}
                schema_lines = []
                for table, columns in data.items():
                    if isinstance(columns, list):
                        col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in columns]
                        schema_lines.append(f"{table}({', '.join(col_names)})")
                    else:
                        schema_lines.append(f"{table}: {columns}")
                return "\n".join(schema_lines)
            else:
                return json.dumps(data, indent=2)
        except Exception as e:
            return f"[Error loading file {file_path}: {e}]"
