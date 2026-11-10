# retention.py
# Audio artifact retention: recordings are sensitive, so run-scoped artifact
# directories are swept on startup when they exceed the configured age.
# Deterministic, best-effort: a failed deletion is logged, never raised.

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def sweep_old_artifacts(base_dir: Path | str, retention_days: int) -> dict[str, int]:
    """Delete run-scoped artifact subdirs older than the retention cutoff.

    A directory's age is the mtime of its most recently modified entry.
    retention_days <= 0 disables the sweep (keep forever). Returns stats.
    """
    stats = {"scanned": 0, "deleted": 0, "errors": 0}
    if retention_days <= 0:
        return stats
    base = Path(base_dir)
    if not base.exists():
        return stats
    cutoff = time.time() - retention_days * 86400.0
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue
        stats["scanned"] += 1
        try:
            newest = max(
                (p.stat().st_mtime for p in run_dir.rglob("*") if p.is_file()),
                default=run_dir.stat().st_mtime,
            )
            if newest < cutoff:
                shutil.rmtree(run_dir)
                stats["deleted"] += 1
                logger.info("retention: deleted stale artifact dir %s", run_dir.name)
        except OSError as exc:
            stats["errors"] += 1
            logger.warning("retention: could not sweep %s: %s", run_dir.name, exc)
    return stats
