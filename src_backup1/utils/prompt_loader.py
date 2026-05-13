import os
import yaml
from typing import List, Dict, Any

class PromptLoader:
    """
    Loads and formats prompt templates from YAML files.
    Each YAML file should follow the messages list format:
    messages:
      - role: system
        content: |
          ...
      - role: user
        content: |
          ...
    """
    @staticmethod
    def load(file_path: str, variables: Dict[str, Any] = None) -> List[Dict[str, str]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        messages = data.get("messages", [])
        if variables:
            formatted_messages = []
            for msg in messages:
                content = msg.get("content", "")
                # Use manual replacement to avoid KeyError from braces in JSON strings (e.g. INTENT)
                formatted_content = content
                for key, val in variables.items():
                    placeholder = "{" + key + "}"
                    formatted_content = formatted_content.replace(placeholder, str(val))
                
                formatted_messages.append({
                    "role": msg.get("role", "user"),
                    "content": formatted_content
                })
            return formatted_messages
            
        return messages
