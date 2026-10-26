"""Automatic scratch evidence retention for Genesis heartbeat runs.

Safety invariants:
- Keep the newest 50 completed heartbeat evidence files per civilization.
- Prune only older scratch evidence.
- Never delete an in-flight heartbeat file.
- Never touch canonical ledgers, provenance, memories, fog, or world state.
- Run retention after successful heartbeat persistence, not during execution.
- Log deleted counts and recovered bytes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger("genesis.retention")

FORBIDDEN_DIR_SUBSTRINGS = (
    ".runtime",
    "world-sim/data",
    "world-sim\\data",
    "/data/",
    "\\data\\",
)


class RetentionSafetyError(ValueError):
    """Raised when a path violates safety invariants for scratch retention."""
    pass


@dataclass(frozen=True)
class RetentionStats:
    pair: str
    deleted_count: int
    recovered_bytes: int
    kept_count: int
    min_kept_hb: int | None
    max_kept_hb: int | None


def _validate_scratch_path(scratch_dir: Path) -> Path:
    """Ensure the target directory is strictly a .scratch directory."""
    resolved = scratch_dir.resolve()
    path_str = str(resolved).lower().replace("\\", "/")

    for forbidden in FORBIDDEN_DIR_SUBSTRINGS:
        if forbidden.lower().replace("\\", "/") in path_str:
            raise RetentionSafetyError(
                f"Retention safety violation: path points to canonical/data store: {resolved}"
            )

    if ".scratch" not in path_str:
        raise RetentionSafetyError(
            f"Retention safety violation: path is not within a .scratch directory: {resolved}"
        )

    return resolved


def prune_scratch_evidence(
    scratch_dir: Path | str,
    pair: str,
    keep_count: int = 50,
    log_fn: Callable[[str], None] | None = None,
) -> RetentionStats:
    """Prunes older scratch evidence files for a civilization, keeping newest keep_count completed.

    Args:
        scratch_dir: Path to the scratch lockstep directory.
        pair: 'east' or 'west'.
        keep_count: Number of newest completed heartbeat evidence files to keep (default 50).
        log_fn: Optional callable for logging (defaults to print/logger).

    Returns:
        RetentionStats with deletion counts, bytes recovered, and kept bounds.
    """
    target_dir = _validate_scratch_path(Path(scratch_dir))
    if not target_dir.is_dir():
        return RetentionStats(
            pair=pair,
            deleted_count=0,
            recovered_bytes=0,
            kept_count=0,
            min_kept_hb=None,
            max_kept_hb=None,
        )

    # Find candidate evidence files: lockstep_{pair}_hb{hb}_evidence.json
    pattern = re.compile(rf"^lockstep_{re.escape(pair)}_hb(\d+)_evidence\.json$")
    evidence_candidates: list[tuple[int, Path, int]] = []

    for entry in os.scandir(target_dir):
        if not entry.is_file():
            continue
        m = pattern.match(entry.name)
        if not m:
            continue
        hb = int(m.group(1))
        p = Path(entry.path)
        try:
            size = entry.stat().st_size
            evidence_candidates.append((hb, p, size))
        except OSError:
            continue

    if not evidence_candidates:
        return RetentionStats(
            pair=pair,
            deleted_count=0,
            recovered_bytes=0,
            kept_count=0,
            min_kept_hb=None,
            max_kept_hb=None,
        )

    # Invariant: Never delete an in-flight or uncompleted heartbeat file.
    # A heartbeat is completed only if lockstep_{pair}_hb{hb}_status.json exists
    # and has status == "evidence-exported".
    completed_hbs: list[tuple[int, Path, int]] = []
    for hb, ev_path, size in evidence_candidates:
        st_path = target_dir / f"lockstep_{pair}_hb{hb}_status.json"
        if not st_path.is_file():
            # In-flight or missing status: never a candidate for pruning
            continue
        try:
            status_data = json.loads(st_path.read_text(encoding="utf-8"))
            if status_data.get("status") == "evidence-exported":
                completed_hbs.append((hb, ev_path, size))
        except Exception:
            # Corrupt or unreadable status: treat as in-flight / protected
            continue

    completed_hbs.sort(key=lambda x: x[0])

    if len(completed_hbs) <= keep_count:
        min_hb = completed_hbs[0][0] if completed_hbs else None
        max_hb = completed_hbs[-1][0] if completed_hbs else None
        return RetentionStats(
            pair=pair,
            deleted_count=0,
            recovered_bytes=0,
            kept_count=len(completed_hbs),
            min_kept_hb=min_hb,
            max_kept_hb=max_hb,
        )

    # Partition into kept (newest keep_count) and to_prune (older)
    to_keep = completed_hbs[-keep_count:]
    to_prune = completed_hbs[:-keep_count]

    deleted_count = 0
    recovered_bytes = 0

    for hb, ev_path, size in to_prune:
        try:
            ev_path.unlink(missing_ok=True)
            deleted_count += 1
            recovered_bytes += size
            st_path = ev_path.parent / f"lockstep_{pair}_hb{hb}_status.json"
            if st_path.is_file():
                recovered_bytes += st_path.stat().st_size
                st_path.unlink(missing_ok=True)
        except OSError as exc:
            if log_fn:
                log_fn(f"[retention] warning: failed to unlink {ev_path.name}: {exc}")

    min_kept = to_keep[0][0] if to_keep else None
    max_kept = to_keep[-1][0] if to_keep else None

    msg = (
        f"[retention] {pair}: pruned {deleted_count} older evidence files, "
        f"recovered {recovered_bytes / (1024**2):.1f} MB "
        f"(kept newest {len(to_keep)}: HB {min_kept}..{max_kept})"
    )
    if log_fn:
        log_fn(msg)
    else:
        logger.info(msg)

    return RetentionStats(
        pair=pair,
        deleted_count=deleted_count,
        recovered_bytes=recovered_bytes,
        kept_count=len(to_keep),
        min_kept_hb=min_kept,
        max_kept_hb=max_kept,
    )
