"""
Prompt versioning and change-detection registry.

Each YAML prompt file is given a SHA-256 content checksum.  Checksums are
persisted to ``resources/memory/prompt_checksums.json`` on first load and
compared on every subsequent load.  Any content change increments that
prompt's version counter and emits a structured warning so operators can
audit which prompts changed between deployments.
"""

import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

from agent.services.logger import logger


class PromptRegistry:
    """
    Scans the prompts directory, computes SHA-256 checksums, detects drift.
    Thread-safe singleton - construct via `PromptRegistry.get_instance()`.
    """

    _instance: Optional["PromptRegistry"] = None
    _class_lock = threading.Lock()

    def __init__(self, prompts_dir: Path, checksum_path: Path) -> None:
        self._prompts_dir = prompts_dir
        self._checksum_path = checksum_path
        self._manifest: dict[str, dict] = {}

    @classmethod
    def get_instance(cls, prompts_dir: Path, checksum_path: Path) -> "PromptRegistry":
        """Return (or create) the process-wide singleton."""
        with cls._class_lock:
            if cls._instance is None:
                inst = cls(prompts_dir, checksum_path)
                inst._load()
                cls._instance = inst
            return cls._instance

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def _load(self) -> None:
        """Scan prompts, compare against persisted baseline, alert on drift."""
        baseline: dict[str, dict] = {}
        if self._checksum_path.exists():
            try:
                baseline = json.loads(self._checksum_path.read_text(encoding="utf-8"))
            except Exception:
                baseline = {}

        manifest: dict[str, dict] = {}
        for yaml_file in sorted(self._prompts_dir.glob("*.yaml")):
            name = yaml_file.stem
            checksum = self._sha256(yaml_file)
            prev = baseline.get(name, {})

            version = prev.get("version", 1)
            changed = bool(prev) and (prev.get("checksum", "") != checksum)
            if changed:
                version += 1
                logger.warning(
                    f"[PromptRegistry] PROMPT CHANGED: '{name}' -> version {version} "
                    f"(prev={prev['checksum'][:8]}... now={checksum[:8]}...)"
                )

            manifest[name] = {
                "checksum": checksum,
                "version": version,
                "changed_since_baseline": changed,
            }

        self._manifest = manifest
        self._persist(manifest)

    def _persist(self, manifest: dict) -> None:
        try:
            self._checksum_path.parent.mkdir(parents=True, exist_ok=True)
            self._checksum_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"[PromptRegistry] Could not persist checksum baseline: {exc}")

    def get_manifest(self) -> dict:
        """Return a copy of the full prompt version manifest."""
        return dict(self._manifest)

    def has_changed_prompts(self) -> bool:
        """True if any prompt changed since the stored baseline."""
        return any(v.get("changed_since_baseline", False) for v in self._manifest.values())

    def reload(self) -> None:
        """Force a re-scan (useful after in-place prompt edits in long-running processes)."""
        with self._class_lock:
            self._load()
