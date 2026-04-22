import json
from pathlib import Path
from typing import Any

from .logger import Logger


class DataLoader:
    """
    Generic Data Loader for Text2SQL datasets.
    Handles JSONL parsing and field mapping consistency.
    """

    @staticmethod
    def load_jsonl(file_path: Union[str, Path]) -> list[dict[str, Any]]:
        """Loads a JSONL file and returns a list of dictionaries."""
        tasks = []
        path = Path(file_path)

        if not path.exists():
            Logger.log(f"Dataset not found: {path}", level="ERROR")
            return []

        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            # Standardize mapping
                            task = {
                                "instance_id": item.get("instance_id")
                                or item.get("id")
                                or "unknown",
                                "db": item.get("db")
                                or item.get("db_id")
                                or item.get("database"),
                                "question": item.get("question")
                                or item.get("utterance"),
                                "external_knowledge": item.get("external_knowledge")
                                or item.get("knowledge"),
                                "raw_data": item,  # Keep original just in case
                            }
                            tasks.append(task)
                        except json.JSONDecodeError as e:
                            Logger.log(
                                f"Skipping invalid JSON line in {path.name}: {e}",
                                level="WARN",
                            )

            Logger.log(f"Successfully loaded {len(tasks)} tasks from {path.name}.")
            return tasks
        except Exception as e:
            Logger.log(f"Failed to load dataset {path}: {e}", level="ERROR")
            return []


