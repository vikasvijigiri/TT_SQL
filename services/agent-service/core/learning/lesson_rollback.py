"""
Versioned snapshots for the dynamic lessons store.

The self-improving loop appends synthesised SQL rules to
``resources/memory/dynamic_lessons.json``.  A bad rule can degrade accuracy.
This module provides:

  - ``save_snapshot()``   - copy the current lessons file to a timestamped
                            snapshot before each improvement run.
  - ``list_snapshots()``  - enumerate available restore points.
  - ``rollback_to(ver)``  - atomically replace the live lessons file with a
                            snapshot using write-then-rename so readers never
                            see a partial file.
  - ``_prune_old_snapshots()`` - keep the most recent N snapshots and delete
                                 the rest (configurable via MAX_LESSON_SNAPSHOTS).

Snapshot files are stored in ``resources/memory/lessons_snapshots/``
and named by UTC timestamp: ``YYYYMMDD_HHMMSS.json``.
"""

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from core.utils.logger import logger

MAX_SNAPSHOTS: int = int(os.getenv("MAX_LESSON_SNAPSHOTS", "20"))


class LessonRollback:
    """
    Manages versioned snapshots of ``dynamic_lessons.json``.

    Thread-safe for all public methods: OS-level ``os.replace()`` is atomic
    on POSIX and Windows; snapshot writes are independent files.
    """

    def __init__(self, lessons_path: Path, snapshot_dir: Path) -> None:
        self._lessons_path = lessons_path
        self._snapshot_dir = snapshot_dir
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self) -> Optional[str]:
        """
        Copy the current lessons file into the snapshot directory.

        Returns the snapshot filename (e.g. ``20250618_142301.json``),
        or None if the lessons file does not exist yet.
        """
        if not self._lessons_path.exists():
            return None
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        dest = self._snapshot_dir / f"{ts}.json"
        shutil.copy2(self._lessons_path, dest)
        logger.info(f"[LessonRollback] Snapshot saved: {dest.name}")
        self._prune_old_snapshots()
        return dest.name

    def list_snapshots(self) -> list[dict]:
        """
        Return metadata for all available snapshots, newest-first.

        Each entry contains ``version`` (stem), ``filename``, ``size_bytes``,
        and ``rule_count`` (number of JSON entries in the snapshot).
        """
        snapshots = sorted(self._snapshot_dir.glob("*.json"), reverse=True)
        result: list[dict] = []
        for snap in snapshots:
            try:
                data = json.loads(snap.read_text(encoding="utf-8"))
                rule_count = len(data) if isinstance(data, list) else -1
            except Exception:
                rule_count = -1
            result.append(
                {
                    "version": snap.stem,
                    "filename": snap.name,
                    "size_bytes": snap.stat().st_size,
                    "rule_count": rule_count,
                }
            )
        return result

    def rollback_to(self, version: str) -> bool:
        """
        Atomically replace the live lessons file with snapshot ``version``.

        ``version`` is the snapshot stem (``YYYYMMDD_HHMMSS``).  The
        write-then-rename pattern ensures readers never see a partial file.

        Returns True on success, False if the version does not exist.
        """
        snap = self._snapshot_dir / f"{version}.json"
        if not snap.exists():
            logger.warning(f"[LessonRollback] Snapshot not found: {version}")
            return False
        tmp = self._lessons_path.with_suffix(".json.tmp")
        shutil.copy2(snap, tmp)
        os.replace(tmp, self._lessons_path)  # atomic on POSIX and Windows
        logger.warning(
            f"[LessonRollback] ROLLED BACK to {version} "
            f"({snap.stat().st_size} bytes, source: {snap.name})"
        )
        return True

    def _prune_old_snapshots(self) -> None:
        """Delete snapshots beyond the MAX_SNAPSHOTS retention limit."""
        snapshots = sorted(self._snapshot_dir.glob("*.json"), reverse=True)
        for old in snapshots[MAX_SNAPSHOTS:]:
            try:
                old.unlink()
                logger.info(f"[LessonRollback] Pruned old snapshot: {old.name}")
            except Exception:
                pass
