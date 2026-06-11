import os
import yaml
from typing import List, Dict, Any


class PromptLoader:
    """
    Loads and formats prompt templates from YAML files.

    Each YAML file must follow the messages-list format:
      messages:
        - role: system
          content: |
            ...
        - role: user
          content: |
            {PLACEHOLDER}
    """

    @staticmethod
    def load(file_path: str, variables: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        messages = data.get("messages", [])

        if not variables:
            return messages

        formatted = []
        for msg in messages:
            content = msg.get("content", "")
            # Manual replacement avoids KeyError from stray braces in JSON examples
            for key, val in variables.items():
                content = content.replace("{" + key + "}", str(val))
            formatted.append({"role": msg.get("role", "user"), "content": content})

        return formatted

    @staticmethod
    def system(file_path: str, variables: Dict[str, Any] | None = None) -> str:
        """Return only the system-role content string (convenience helper)."""
        messages = PromptLoader.load(file_path, variables)
        for m in messages:
            if m["role"] == "system":
                return m["content"]
        return ""

    @staticmethod
    def user(file_path: str, variables: Dict[str, Any] | None = None) -> str:
        """Return only the user-role content string (convenience helper)."""
        messages = PromptLoader.load(file_path, variables)
        for m in messages:
            if m["role"] == "user":
                return m["content"]
        return ""
