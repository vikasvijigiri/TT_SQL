"""
Schema drift detector.

Hashes every schema metadata JSON file in the databases directory, persists a
baseline to ``resources/memory/schema_checksums.json``, and emits structured
warnings whenever files are added, removed, or modified between pipeline runs.

Industry-standard pattern: full-directory content-hash -> detect any file-level
change without a live database connection.
"""

import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

from agent.services.logger import logger


class SchemaDriftDetector:
    """
    Content-fingerprints the schema metadata directory and detects drift.
    Thread-safe singleton - construct via `SchemaDriftDetector.get_instance()`.
    """

    _instance: Optional["SchemaDriftDetector"] = None
    _class_lock = threading.Lock()

    def __init__(self, schema_dir: Path, baseline_path: Path) -> None:
        self._schema_dir = schema_dir
        self._baseline_path = baseline_path
        self._drift_report: dict = {
            "drifted": False,
            "added": [],
            "removed": [],
            "modified": [],
            "total_files": 0,
        }

    @classmethod
    def get_instance(cls, schema_dir: Path, baseline_path: Path) -> "SchemaDriftDetector":
        """Return (or create) the process-wide singleton and run an initial check."""
        with cls._class_lock:
            if cls._instance is None:
                inst = cls(schema_dir, baseline_path)
                inst.check()
                cls._instance = inst
            return cls._instance

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def _scan(self) -> dict[str, str]:
        """Walk the schema directory and return a {relative_path: sha256} map."""
        result: dict[str, str] = {}
        if not self._schema_dir.exists():
            return result
        for path in sorted(self._schema_dir.rglob("*.json")):
            try:
                key = str(path.relative_to(self._schema_dir))
                result[key] = self._hash_file(path)
            except Exception:
                pass
        return result

    def check(self) -> dict:
        """Run a full drift check against the persisted baseline and return the report."""
        baseline: dict[str, str] = {}
        if self._baseline_path.exists():
            try:
                baseline = json.loads(self._baseline_path.read_text(encoding="utf-8"))
            except Exception:
                baseline = {}

        current = self._scan()
        baseline_keys = set(baseline)
        current_keys = set(current)

        added = sorted(current_keys - baseline_keys)
        removed = sorted(baseline_keys - current_keys)
        modified = sorted(
            k for k in (current_keys & baseline_keys) if current[k] != baseline[k]
        )
        drifted = bool(added or removed or modified) and bool(baseline)

        self._drift_report = {
            "drifted": drifted,
            "added": added,
            "removed": removed,
            "modified": modified,
            "total_files": len(current),
        }

        if drifted:
            logger.warning(
                f"[SchemaDrift] SCHEMA CHANGED - "
                f"added={len(added)}, removed={len(removed)}, modified={len(modified)}. "
                "Re-extract schema metadata and rebuild embeddings."
            )
        elif baseline:
            logger.info(f"[SchemaDrift] Schema stable ({len(current)} files, no drift)")
        else:
            logger.info(f"[SchemaDrift] Baseline created ({len(current)} schema files indexed)")

        try:
            self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
            self._baseline_path.write_text(
                json.dumps(current, indent=2, sort_keys=True), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"[SchemaDrift] Could not persist baseline: {exc}")

        return dict(self._drift_report)

    @property
    def drift_report(self) -> dict:
        """Most recent drift report (from the last `check()` call)."""
        return dict(self._drift_report)
