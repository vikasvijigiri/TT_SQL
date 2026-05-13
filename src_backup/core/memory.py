class Memory:
    """
    Stores successful mappings and paths to boost future retrieval and mapping decisions.
    """

    def __init__(self, storage_path: str = "memory.json"):
        self.storage_path = storage_path
        self.data = self._load()

    def _load(self) -> dict:
        import os, json
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return {"mappings": {}, "paths": {}}

    def save(self):
        import json
        with open(self.storage_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def update(self, query: str, mapping: dict):
        """
        Stores a successful mapping for a given query.
        """
        # In a real system, we'd use semantic similarity to retrieve from memory.
        # For now, we'll use exact query match or a simple hash.
        self.data["mappings"][query] = mapping
        self.save()

    def get_boost(self, query: str, candidate: str) -> float:
        """
        Returns a boost score for a candidate based on past successful mappings.
        """
        # Placeholder for semantic boost logic
        return 0.0

    def get_path_boost(self, path: list[str]) -> float:
        """
        Returns a boost score for a join path.
        """
        path_str = "->".join(path)
        return self.data["paths"].get(path_str, 0.0)

    def record_success_path(self, path: list[str]):
        path_str = "->".join(path)
        self.data["paths"][path_str] = self.data["paths"].get(path_str, 0.0) + 1.0
        self.save()
