"""Phase 10AR - route intent contract.

Create a deterministic sanitized route-intent contract artifact from a
Phase 10AQ known-map snapshot.  10AR proves only that the agent has a
known destination tile; it does not plan routes, does not record any
intermediate tiles, does not infer adjacency, does not write to the
ledger, and does not produce a ledger-bound admission claim.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_snapshot_file`, which only reads JSON from a caller-
supplied path.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_INTENT_SCHEMA_VERSION = "10AR.1"
_INTENT_TYPE = "route_intent_contract"
_SOURCE_PHASE = "10AQ"
_CLAIM_SCOPE = "intent_only"

_EXPECTED_SNAPSHOT_TYPE = "known_map_snapshot"

# Required fields lifted from the 10AQ snapshot for the contract.
_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id",
    "agent_id",
    "current_tile_id",
)


def _empty_contract(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "intent_schema_version": _INTENT_SCHEMA_VERSION,
        "intent_type": _INTENT_TYPE,
        "intent_id": None,
        "source_phase": _SOURCE_PHASE,
        "source_snapshot_id": None,
        "source_snapshot_hash": None,
        "agent_id": None,
        "from_tile_id": None,
        "destination_tile_id": None,
        "destination_known": False,
        "claim_scope": _CLAIM_SCOPE,
        "reason": None,
        "errors": errors,
    }


def _safe_str(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return ""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _snapshot_hash(sanitized_snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(sanitized_snapshot).encode("utf-8")
    ).hexdigest()


def _intent_id(intent_material: dict[str, Any]) -> str:
    return "10AR-" + hashlib.sha256(
        _canonical_json(intent_material).encode("utf-8")
    ).hexdigest()[:32]


def create_route_intent_contract(
    snapshot: dict,
    destination_tile_id: str,
    *,
    reason: str | None = None,
) -> dict:
    """Create a deterministic sanitized route-intent contract from a 10AQ known-map snapshot."""

    errors: list[str] = []

    if not isinstance(snapshot, dict):
        contract = _empty_contract(["snapshot must be a dict"])
        contract["ok"] = False
        return contract

    # Deep copy the snapshot before any read so the caller-owned dict
    # can never be mutated by validation or sanitization.
    local_snapshot = copy.deepcopy(snapshot)

    # Validate the snapshot is a real 10AQ known-map snapshot.
    if local_snapshot.get("ok") is not True:
        errors.append("snapshot ok flag is not True")
    if local_snapshot.get("snapshot_type") != _EXPECTED_SNAPSHOT_TYPE:
        errors.append(
            "snapshot_type is not " + repr(_EXPECTED_SNAPSHOT_TYPE)
        )

    snapshot_id = _safe_str(local_snapshot.get("snapshot_id"))
    if not snapshot_id:
        errors.append("snapshot_id is missing or empty")

    from_tile_id = _safe_str(local_snapshot.get("current_tile_id"))
    if not from_tile_id:
        errors.append("current_tile_id is missing or empty")

    if not isinstance(destination_tile_id, str) or not destination_tile_id:
        errors.append("destination_tile_id must be a non-empty string")
        normalized_destination = ""
    else:
        # Sanitize the destination BEFORE any further use so that private
        # markers can never appear in the returned contract or hash input.
        sanitized_destination = sanitize_public_mapping(destination_tile_id)
        if isinstance(sanitized_destination, str):
            normalized_destination = sanitized_destination
        else:
            normalized_destination = ""

    if errors:
        contract = _empty_contract(errors)
        contract["ok"] = False
        contract["destination_tile_id"] = (
            normalized_destination if normalized_destination else None
        )
        return contract

    # Sanitize the snapshot after structural validation so the hash and
    # downstream fields are always redaction-safe.
    sanitized_snapshot = sanitize_public_mapping(local_snapshot)
    if not isinstance(sanitized_snapshot, dict):
        contract = _empty_contract(["sanitized snapshot is not a dict"])
        contract["ok"] = False
        return contract

    agent_id = _safe_str(sanitized_snapshot.get("agent_id"))
    source_snapshot_id = _safe_str(sanitized_snapshot.get("snapshot_id"))
    from_tile = _safe_str(sanitized_snapshot.get("current_tile_id"))

    source_hash = _snapshot_hash(sanitized_snapshot)

    known_tile_ids = sanitized_snapshot.get("known_tile_ids")
    if not isinstance(known_tile_ids, list):
        known_tile_ids = []
    known_set = {
        item for item in known_tile_ids
        if isinstance(item, str) and item
    }
    destination_known = normalized_destination in known_set

    if not destination_known:
        contract = _empty_contract(
            ["destination_tile_id is not in known_tile_ids"]
        )
        contract["ok"] = False
        contract["source_snapshot_id"] = source_snapshot_id
        contract["source_snapshot_hash"] = source_hash
        contract["agent_id"] = agent_id or None
        contract["from_tile_id"] = from_tile or None
        contract["destination_tile_id"] = normalized_destination
        contract["destination_known"] = False
        contract["reason"] = (
            sanitize_public_mapping(reason) if isinstance(reason, str) else None
        )
        return contract

    sanitized_reason: str | None
    if isinstance(reason, str):
        sanitized_reason_local = sanitize_public_mapping(reason)
        sanitized_reason = (
            sanitized_reason_local
            if isinstance(sanitized_reason_local, str)
            else None
        )
    elif reason is None:
        sanitized_reason = None
    else:
        sanitized_reason = None

    # Build the intent material deterministically.  Only contract-level
    # fields feed intent_id so the id is stable across input ordering
    # and across repeated calls with the same inputs.
    intent_material: dict[str, Any] = {
        "source_snapshot_hash": source_hash,
        "agent_id": agent_id,
        "from_tile_id": from_tile,
        "destination_tile_id": normalized_destination,
        "claim_scope": _CLAIM_SCOPE,
    }
    if sanitized_reason:
        intent_material["reason"] = sanitized_reason

    intent_id = _intent_id(intent_material)

    return {
        "ok": True,
        "intent_schema_version": _INTENT_SCHEMA_VERSION,
        "intent_type": _INTENT_TYPE,
        "intent_id": intent_id,
        "source_phase": _SOURCE_PHASE,
        "source_snapshot_id": source_snapshot_id,
        "source_snapshot_hash": source_hash,
        "agent_id": agent_id,
        "from_tile_id": from_tile,
        "destination_tile_id": normalized_destination,
        "destination_known": True,
        "claim_scope": _CLAIM_SCOPE,
        "reason": sanitized_reason,
        "errors": [],
    }


def export_route_intent_contract(contract: dict) -> str:
    """Export a route-intent contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_snapshot_file(
    snapshot_json_path: Path | str,
    destination_tile_id: str,
    *,
    reason: str | None = None,
) -> dict:
    """Read an exported 10AQ snapshot JSON file and create a route-intent contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.
    """

    path = Path(snapshot_json_path)
    with path.open("r", encoding="utf-8") as handle:
        snapshot = json.loads(handle.read())
    return create_route_intent_contract(
        snapshot,
        destination_tile_id,
        reason=reason,
    )
