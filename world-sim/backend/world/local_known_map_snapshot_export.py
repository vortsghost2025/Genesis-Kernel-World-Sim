"""Phase 10AQ - known map snapshot export.

Create a deterministic, sanitized, portable known-map snapshot from a
Phase 10AP public state projection.  10AQ does not re-project, does not
re-replay, does not infer adjacency, and does not touch any runtime
substrate.  It only transforms an already-projected public state into a
stable snapshot suitable for export.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in :func:`snapshot_ledger_file`,
which delegates file reading and projection to the existing 10AP
projector (:func:`project_ledger_file`).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.local_public_state_projector import project_ledger_file
from backend.world.world_event_sanitizer import sanitize_public_mapping


_SNAPSHOT_SCHEMA_VERSION = "10AQ.1"
_SNAPSHOT_TYPE = "known_map_snapshot"
_SOURCE_PHASE = "10AP"

_COPIED_FIELDS: tuple[str, ...] = (
    "agent_id",
    "current_tile_id",
    "current_territory_ref",
    "movement_count",
    "observation_count",
    "first_tick",
    "last_tick",
    "last_event_id",
    "accepted_event_count",
    "ignored_event_count",
)


def _empty_snapshot(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "snapshot_schema_version": _SNAPSHOT_SCHEMA_VERSION,
        "snapshot_type": _SNAPSHOT_TYPE,
        "snapshot_id": None,
        "source_phase": _SOURCE_PHASE,
        "source_projection_hash": None,
        "agent_id": None,
        "current_tile_id": None,
        "current_territory_ref": None,
        "observed_tile_ids": [],
        "visited_tile_ids": [],
        "known_tile_ids": [],
        "movement_count": 0,
        "observation_count": 0,
        "first_tick": None,
        "last_tick": None,
        "last_event_id": None,
        "accepted_event_count": 0,
        "ignored_event_count": 0,
        "errors": errors,
    }


def _sorted_unique(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str) and item:
            seen.add(item)
    return sorted(seen)


def _canonical_projection_json(sanitized: dict[str, Any]) -> str:
    return json.dumps(
        sanitized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _snapshot_id(hash_hex: str) -> str:
    return "10AQ-" + hash_hex[:32]


def create_known_map_snapshot(public_state: dict) -> dict:
    """Create a deterministic sanitized known-map snapshot from a 10AP public state projection."""

    if not isinstance(public_state, dict):
        snapshot = _empty_snapshot(["public_state must be a dict"])
        snapshot["ok"] = False
        return snapshot

    local = copy.deepcopy(public_state)

    if local.get("ok") is not True:
        snapshot = _empty_snapshot(["public_state ok flag is not True"])
        snapshot["ok"] = False
        return snapshot

    sanitized = sanitize_public_mapping(local)
    if not isinstance(sanitized, dict):
        snapshot = _empty_snapshot(["sanitized public_state is not a dict"])
        snapshot["ok"] = False
        return snapshot

    canonical = _canonical_projection_json(sanitized)
    source_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    observed = _sorted_unique(sanitized.get("observed_tile_ids"))
    visited = _sorted_unique(sanitized.get("visited_tile_ids"))
    known = sorted(set(observed) | set(visited))

    snapshot = _empty_snapshot([])
    snapshot["ok"] = True
    snapshot["snapshot_id"] = _snapshot_id(source_hash)
    snapshot["source_projection_hash"] = source_hash

    for field in _COPIED_FIELDS:
        snapshot[field] = sanitized.get(field)

    snapshot["observed_tile_ids"] = observed
    snapshot["visited_tile_ids"] = visited
    snapshot["known_tile_ids"] = known

    return snapshot


def export_known_map_snapshot(snapshot: dict) -> str:
    """Export a known-map snapshot as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(snapshot)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def snapshot_ledger_file(ledger_path: Path | str) -> dict:
    """Project a public ledger file through 10AP and return a known-map snapshot."""

    public_state = project_ledger_file(ledger_path)
    return create_known_map_snapshot(public_state)
