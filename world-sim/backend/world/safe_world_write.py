"""
Safe world-state write helpers.

Provides atomic writes, backup-before-write, and mutation audit logging
for world-state JSON files. Designed to prevent corruption and enable
traceability of all world mutations.

Phase 6B: WorldMutationGuardHarness
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("world.safe_write")


def compute_md5(path: Path) -> str:
    """Compute MD5 hash of a file. Returns empty string if file doesn't exist."""
    import hashlib
    if not path.exists():
        return ""
    return hashlib.md5(path.read_bytes()).hexdigest()


def atomic_json_write(path: Path, data: dict[str, Any]) -> bool:
    """
    Write JSON to a file atomically.
    
    1. Write to a temp file in the same directory
    2. fsync the temp file
    3. Rename/replace the original atomically
    
    Returns True on success, False on failure.
    Original file is never left in a corrupted state.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_fd = None
    tmp_path = None
    try:
        # Write to temp file in same directory
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        
        # Write JSON content
        content = json.dumps(data, indent=2, ensure_ascii=False)
        os.write(tmp_fd, content.encode("utf-8"))
        
        # fsync to ensure data is on disk
        os.fsync(tmp_fd)
        os.close(tmp_fd)
        tmp_fd = None
        
        # Atomic rename
        os.replace(tmp_path, path)
        tmp_path = None
        
        return True
    except Exception as e:
        logger.error("Atomic write failed for %s: %s", path, e)
        # Clean up temp file on failure
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return False


def backup_before_write(path: Path, backup_dir: Path | None = None) -> Path | None:
    """
    Create a timestamped backup of a file before writing.
    
    Returns the backup path, or None if backup failed.
    """
    path = Path(path)
    if not path.exists():
        logger.warning("No file to backup: %s", path)
        return None
    
    if backup_dir is None:
        backup_dir = path.parent / "backups"
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = path.stem
    suffix = path.suffix
    backup_name = f"{stem}_{timestamp}{suffix}"
    backup_path = backup_dir / backup_name
    
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except Exception as e:
        logger.error("Backup failed for %s: %s", path, e)
        return None


def log_mutation(
    audit_log_path: Path,
    actor: str,
    action: str,
    target_file: str,
    before_md5: str,
    after_md5: str,
    changes: dict[str, Any],
    backup_path: str | None = None,
) -> None:
    """
    Append a mutation event to the audit log (JSONL format).
    """
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "target_file": target_file,
        "before_md5": before_md5,
        "after_md5": after_md5,
        "changes": changes,
    }
    if backup_path:
        entry["backup_path"] = backup_path
    
    audit_log_path = Path(audit_log_path)
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def safe_world_write(
    path: Path,
    data: dict[str, Any],
    actor: str,
    action: str,
    changes: dict[str, Any],
    audit_log_path: Path | None = None,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Safe world-state write with atomic write, backup, and audit logging.
    
    Returns a result dict with:
        - ok: bool
        - before_md5: str
        - after_md5: str
        - backup_path: str or None
        - error: str or None
    """
    path = Path(path)
    
    # Compute before MD5
    before_md5 = compute_md5(path)
    
    # Backup
    backup_path = backup_before_write(path, backup_dir)
    
    # Atomic write
    ok = atomic_json_write(path, data)
    
    # Compute after MD5
    after_md5 = compute_md5(path) if ok else before_md5
    
    # Audit log
    if audit_log_path and ok:
        log_mutation(audit_log_path, actor, action, str(path), before_md5, after_md5, changes,
                     backup_path=str(backup_path) if backup_path else None)
    
    return {
        "ok": ok,
        "before_md5": before_md5,
        "after_md5": after_md5,
        "backup_path": str(backup_path) if backup_path else None,
        "error": None if ok else "atomic_write_failed",
    }
