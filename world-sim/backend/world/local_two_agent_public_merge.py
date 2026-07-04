"""Phase 10AS - two-agent public merge.

Create a deterministic sanitized comparison artifact for two agents'
already-public surfaces:

    - 10AP public_state projection
    - 10AQ known_map_snapshot
    - optional 10AR route_intent_contract

10AS may say:

    "These two public surfaces overlap on tiles X/Y/Z."

10AS may not say:

    "The agents know each other, met, communicated, trust each other,
     cooperate, conflict, are aware of each other, or can travel
     between those tiles."

The module is pure.  It never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in the file-helper
:func:`create_two_agent_public_merge`'s sister entry-point, which only
reads JSON from a caller-supplied path and then delegates to
:func:`create_two_agent_public_merge`.

10AS does not call into 10AP, 10AQ, or 10AR creators; it receives
already-built sanitized surfaces and compares them.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_MERGE_SCHEMA_VERSION = "10AS.1"
_MERGE_TYPE = "two_agent_public_merge"
_SOURCE_PHASE = "10AR"
_CLAIM_SCOPE = "public_only"
_EXPECTED_SNAPSHOT_TYPE = "known_map_snapshot"
_EXPECTED_ROUTE_INTENT_TYPE = "route_intent_contract"
_EXPECTED_ROUTE_INTENT_CLAIM_SCOPE = "intent_only"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_str(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return ""


def _sorted_unique(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, str) and item:
            seen.add(item)
    return sorted(seen)


def _empty_agent_bundle() -> dict[str, Any]:
    return {
        "agent_id": None,
        "public_state_hash": None,
        "snapshot_id": None,
        "snapshot_hash": None,
        "current_tile_id": None,
        "known_tile_ids": [],
        "route_intent_id": None,
        "route_destination_tile_id": None,
        "route_destination_known": None,
    }


def _empty_merge(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "merge_schema_version": _MERGE_SCHEMA_VERSION,
        "merge_type": _MERGE_TYPE,
        "merge_id": None,
        "source_phase": _SOURCE_PHASE,
        "claim_scope": _CLAIM_SCOPE,
        "agent_a": _empty_agent_bundle(),
        "agent_b": _empty_agent_bundle(),
        "shared_known_tile_ids": [],
        "agent_a_only_known_tile_ids": [],
        "agent_b_only_known_tile_ids": [],
        "same_current_tile": False,
        "both_have_route_intent": False,
        "errors": errors,
    }


def _validate_public_state(
    value: Any,
    *,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(label + " must be a dict")
        return None
    if value.get("ok") is not True:
        errors.append(label + " ok flag is not True")
    return value


def _validate_snapshot(
    value: Any,
    *,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(label + " must be a dict")
        return None
    if value.get("ok") is not True:
        errors.append(label + " ok flag is not True")
    if value.get("snapshot_type") != _EXPECTED_SNAPSHOT_TYPE:
        errors.append(
            label + " snapshot_type is not " + repr(_EXPECTED_SNAPSHOT_TYPE)
        )
    return value


def _validate_route_intent_for(
    raw_intent: Any,
    *,
    bundle_agent_id: str,
    bundle_snapshot_id: str,
    label: str,
    sanitized_destination: dict[str, Any],
    errors: list[str],
) -> tuple[str | None, bool | None, bool] | None:
    """Return (intent_id, destination_known, intent_is_valid).

    ``intent_is_valid`` True means the intent passed all checks and may
    contribute to the merge output.  False means it failed one or
    more checks; the caller must surface safe errors and refuse to
    build a merge.  None means ``raw_intent`` was None (omitted).
    """

    if raw_intent is None:
        return None

    if not isinstance(raw_intent, dict):
        errors.append(label + " route intent must be a dict or None")
        return (None, None, False)

    intent = raw_intent

    if intent.get("ok") is not True:
        errors.append(label + " route intent ok flag is not True")
    if intent.get("intent_type") != _EXPECTED_ROUTE_INTENT_TYPE:
        errors.append(
            label + " route intent intent_type is not "
            + repr(_EXPECTED_ROUTE_INTENT_TYPE)
        )
    if intent.get("claim_scope") != _EXPECTED_ROUTE_INTENT_CLAIM_SCOPE:
        errors.append(
            label + " route intent claim_scope is not "
            + repr(_EXPECTED_ROUTE_INTENT_CLAIM_SCOPE)
        )

    intent_agent_id = _safe_str(intent.get("agent_id"))
    if intent_agent_id != bundle_agent_id:
        errors.append(
            label + " route intent agent_id does not match bundle agent_id"
        )

    intent_source_snapshot_id = _safe_str(intent.get("source_snapshot_id"))
    if intent_source_snapshot_id != bundle_snapshot_id:
        errors.append(
            label
            + " route intent source_snapshot_id does not match bundle snapshot_id"
        )

    if any(
        msg.endswith("is not True")
        or msg.endswith(
            " is not " + repr(_EXPECTED_ROUTE_INTENT_TYPE)
        )
        or msg.endswith(
            " is not " + repr(_EXPECTED_ROUTE_INTENT_CLAIM_SCOPE)
        )
        or "does not match" in msg
        for msg in errors
    ):
        return (None, None, False)

    intent_id = _safe_str(intent.get("intent_id"))
    if not intent_id:
        errors.append(label + " route intent intent_id is missing or empty")
        return (None, None, False)

    destination_known_raw = intent.get("destination_known")
    if not isinstance(destination_known_raw, bool):
        errors.append(
            label
            + " route intent destination_known must be a bool"
        )
        return (None, None, False)
    if destination_known_raw is False:
        errors.append(
            label
            + " route intent destination_known must be True for a valid contract"
        )
        return (None, None, False)

    # The destination_tile_id is stored in the sanitized destination dict
    # only; we never put the raw intent into the merge output.
    sanitized_destination[
        "route_intent_id"
    ] = intent_id
    sanitized_destination[
        "route_destination_tile_id"
    ] = _safe_str(intent.get("destination_tile_id")) or None
    sanitized_destination[
        "route_destination_known"
    ] = destination_known_raw

    return (intent_id, destination_known_raw, True)


def _build_agent_bundle_from_inputs(
    sanitized_public_state: dict[str, Any],
    sanitized_snapshot: dict[str, Any],
    *,
    route_intent_payload: dict[str, Any] | None,
    errors: list[str],
    label: str,
) -> tuple[dict[str, Any], str, str]:
    """Validate a (public_state, snapshot) pair and assemble a bundle.

    Returns ``(bundle, bundle_agent_id, bundle_snapshot_id)``.  On
    validation failure, ``bundle`` is the empty bundle shape and
    ``errors`` is appended to.  Bundle field values come from the
    sanitized inputs; hashes use canonical sanitized JSON.
    """

    bundle = _empty_agent_bundle()

    public_agent_id = _safe_str(sanitized_public_state.get("agent_id"))
    if not public_agent_id:
        errors.append(label + " public_state agent_id missing or empty")

    snapshot_agent_id = _safe_str(sanitized_snapshot.get("agent_id"))
    if not snapshot_agent_id:
        errors.append(label + " snapshot agent_id missing or empty")

    public_current = _safe_str(sanitized_public_state.get("current_tile_id"))
    if not public_current:
        errors.append(label + " public_state current_tile_id missing or empty")

    snapshot_current = _safe_str(sanitized_snapshot.get("current_tile_id"))
    if not snapshot_current:
        errors.append(label + " snapshot current_tile_id missing or empty")

    snapshot_id = _safe_str(sanitized_snapshot.get("snapshot_id"))
    if not snapshot_id:
        errors.append(label + " snapshot_id missing or empty")

    if public_agent_id and snapshot_agent_id and public_agent_id != snapshot_agent_id:
        errors.append(
            label + " public_state agent_id does not match snapshot agent_id"
        )
    if (
        public_current
        and snapshot_current
        and public_current != snapshot_current
    ):
        errors.append(
            label + " public_state current_tile_id does not match snapshot current_tile_id"
        )

    known_tile_ids = sanitized_snapshot.get("known_tile_ids")
    if not isinstance(known_tile_ids, list):
        errors.append(label + " snapshot known_tile_ids must be a list")
        known_tile_ids = []

    bundle["agent_id"] = public_agent_id or snapshot_agent_id or None
    bundle["public_state_hash"] = _hash_canonical(sanitized_public_state)
    bundle["snapshot_id"] = snapshot_id or None
    bundle["snapshot_hash"] = _hash_canonical(sanitized_snapshot)
    bundle["current_tile_id"] = (
        public_current or snapshot_current or None
    )
    bundle["known_tile_ids"] = _sorted_unique(known_tile_ids)

    if route_intent_payload is not None:
        bundle["route_intent_id"] = route_intent_payload.get(
            "route_intent_id"
        )
        bundle["route_destination_tile_id"] = route_intent_payload.get(
            "route_destination_tile_id"
        )
        bundle["route_destination_known"] = route_intent_payload.get(
            "route_destination_known"
        )

    return bundle, bundle["agent_id"] or "", bundle["snapshot_id"] or ""


def _sanitize_dict(value: Any, *, label: str, errors: list[str]) -> dict[str, Any] | None:
    sanitized = sanitize_public_mapping(value)
    if not isinstance(sanitized, dict):
        errors.append(label + " sanitized value is not a dict")
        return None
    return sanitized


def _sorted_set_difference(left: list[str], right: list[str]) -> list[str]:
    right_set = {x for x in right if isinstance(x, str) and x}
    return sorted(item for item in left if isinstance(item, str) and item and item not in right_set)


def _build_merge_material(
    *,
    agent_a: dict[str, Any],
    agent_b: dict[str, Any],
    shared: list[str],
    a_only: list[str],
    b_only: list[str],
    same_current_tile: bool,
    both_have_route_intent: bool,
) -> dict[str, Any]:
    return {
        "source_phase": _SOURCE_PHASE,
        "claim_scope": _CLAIM_SCOPE,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "shared_known_tile_ids": shared,
        "agent_a_only_known_tile_ids": a_only,
        "agent_b_only_known_tile_ids": b_only,
        "same_current_tile": same_current_tile,
        "both_have_route_intent": both_have_route_intent,
    }


def create_two_agent_public_merge(
    public_state_a: dict,
    snapshot_a: dict,
    public_state_b: dict,
    snapshot_b: dict,
    *,
    route_intent_a: dict | None = None,
    route_intent_b: dict | None = None,
) -> dict:
    """Create a deterministic sanitized two-agent public merge artifact."""

    # Deep copy every input before any read so the caller-owned data
    # can never be mutated by validation, sanitization, or hashing.
    local_state_a = copy.deepcopy(public_state_a)
    local_state_b = copy.deepcopy(public_state_b)
    local_snap_a = copy.deepcopy(snapshot_a)
    local_snap_b = copy.deepcopy(snapshot_b)
    local_route_a = copy.deepcopy(route_intent_a) if route_intent_a is not None else None
    local_route_b = copy.deepcopy(route_intent_b) if route_intent_b is not None else None

    errors: list[str] = []

    if _validate_public_state(local_state_a, label="public_state_a", errors=errors) is None:
        pass
    if _validate_public_state(local_state_b, label="public_state_b", errors=errors) is None:
        pass
    if _validate_snapshot(local_snap_a, label="snapshot_a", errors=errors) is None:
        pass
    if _validate_snapshot(local_snap_b, label="snapshot_b", errors=errors) is None:
        pass

    if errors:
        snapshot_validation_only = [
            e for e in errors
            if e.endswith(" must be a dict") or " ok flag is not True" in e
            or "snapshot_type is not" in e
        ]
        structural_only = bool(snapshot_validation_only) and len(snapshot_validation_only) == len(errors)
        if structural_only:
            merge = _empty_merge(errors)
            merge["ok"] = False
            return merge

    sanitized_state_a = _sanitize_dict(local_state_a, label="public_state_a", errors=errors)
    sanitized_state_b = _sanitize_dict(local_state_b, label="public_state_b", errors=errors)
    sanitized_snap_a = _sanitize_dict(local_snap_a, label="snapshot_a", errors=errors)
    sanitized_snap_b = _sanitize_dict(local_snap_b, label="snapshot_b", errors=errors)

    if (
        sanitized_state_a is None
        or sanitized_state_b is None
        or sanitized_snap_a is None
        or sanitized_snap_b is None
    ):
        merge = _empty_merge(errors)
        merge["ok"] = False
        return merge

    # Validate parent-phase matching on the sanitized inputs.
    for state_label, snap_label, sanitized_state, sanitized_snap in (
        ("public_state_a", "snapshot_a", sanitized_state_a, sanitized_snap_a),
        ("public_state_b", "snapshot_b", sanitized_state_b, sanitized_snap_b),
    ):
        state_agent_id = _safe_str(sanitized_state.get("agent_id"))
        snap_agent_id = _safe_str(sanitized_snap.get("agent_id"))
        if not state_agent_id:
            errors.append(state_label + " agent_id missing after sanitize")
        if not snap_agent_id:
            errors.append(snap_label + " agent_id missing after sanitize")
        if state_agent_id and snap_agent_id and state_agent_id != snap_agent_id:
            errors.append(
                state_label
                + " agent_id does not match "
                + snap_label
                + " agent_id"
            )

        state_current = _safe_str(sanitized_state.get("current_tile_id"))
        snap_current = _safe_str(sanitized_snap.get("current_tile_id"))
        if not state_current:
            errors.append(state_label + " current_tile_id missing after sanitize")
        if not snap_current:
            errors.append(snap_label + " current_tile_id missing after sanitize")
        if state_current and snap_current and state_current != snap_current:
            errors.append(
                state_label
                + " current_tile_id does not match "
                + snap_label
                + " current_tile_id"
            )

        snap_id = _safe_str(sanitized_snap.get("snapshot_id"))
        if not snap_id:
            errors.append(snap_label + " snapshot_id missing after sanitize")

        if not isinstance(sanitized_snap.get("known_tile_ids"), list):
            errors.append(snap_label + " known_tile_ids must be a list")

    # Branch: if any structural mismatch above, fail fast on the empty shape.
    if errors:
        merge = _empty_merge(errors)
        merge["ok"] = False
        return merge

    route_a_payload: dict[str, Any] = {}
    route_b_payload: dict[str, Any] = {}

    bundle_a, bundle_a_agent_id, bundle_a_snapshot_id = _build_agent_bundle_from_inputs(
        sanitized_state_a,
        sanitized_snap_a,
        route_intent_payload=None,
        errors=errors,
        label="agent_a",
    )
    bundle_b, bundle_b_agent_id, bundle_b_snapshot_id = _build_agent_bundle_from_inputs(
        sanitized_state_b,
        sanitized_snap_b,
        route_intent_payload=None,
        errors=errors,
        label="agent_b",
    )

    if errors:
        merge = _empty_merge(errors)
        merge["ok"] = False
        return merge

    # Strict route-intent validation.  Both must validate or the merge fails.
    route_a_result = _validate_route_intent_for(
        local_route_a,
        bundle_agent_id=bundle_a_agent_id,
        bundle_snapshot_id=bundle_a_snapshot_id,
        label="route_intent_a",
        sanitized_destination=route_a_payload,
        errors=errors,
    )
    route_b_result = _validate_route_intent_for(
        local_route_b,
        bundle_agent_id=bundle_b_agent_id,
        bundle_snapshot_id=bundle_b_snapshot_id,
        label="route_intent_b",
        sanitized_destination=route_b_payload,
        errors=errors,
    )

    # Sanitize the bundled destination tile ids one more time so private
    # markers from the raw route intent can never reach the merge output.
    if route_a_result is not None and route_a_result[2]:
        sanitized_dest = sanitize_public_mapping(
            route_a_payload.get("route_destination_tile_id")
        )
        if isinstance(sanitized_dest, str) and sanitized_dest:
            route_a_payload["route_destination_tile_id"] = sanitized_dest
        else:
            route_a_payload["route_destination_tile_id"] = None
    if route_b_result is not None and route_b_result[2]:
        sanitized_dest = sanitize_public_mapping(
            route_b_payload.get("route_destination_tile_id")
        )
        if isinstance(sanitized_dest, str) and sanitized_dest:
            route_b_payload["route_destination_tile_id"] = sanitized_dest
        else:
            route_b_payload["route_destination_tile_id"] = None

    if errors:
        merge = _empty_merge(errors)
        merge["ok"] = False
        return merge

    bundle_a = dict(bundle_a)
    bundle_a["route_intent_id"] = route_a_payload.get("route_intent_id")
    bundle_a["route_destination_tile_id"] = route_a_payload.get(
        "route_destination_tile_id"
    )
    bundle_a["route_destination_known"] = route_a_payload.get(
        "route_destination_known"
    )

    bundle_b = dict(bundle_b)
    bundle_b["route_intent_id"] = route_b_payload.get("route_intent_id")
    bundle_b["route_destination_tile_id"] = route_b_payload.get(
        "route_destination_tile_id"
    )
    bundle_b["route_destination_known"] = route_b_payload.get(
        "route_destination_known"
    )

    known_a = bundle_a["known_tile_ids"]
    known_b = bundle_b["known_tile_ids"]

    shared = sorted(set(known_a) & set(known_b))
    a_only = _sorted_set_difference(known_a, known_b)
    b_only = _sorted_set_difference(known_b, known_a)

    same_current = (
        bool(bundle_a["current_tile_id"])
        and bool(bundle_b["current_tile_id"])
        and bundle_a["current_tile_id"] == bundle_b["current_tile_id"]
    )

    both_have_intent = (
        bool(bundle_a["route_intent_id"])
        and bool(bundle_b["route_intent_id"])
    )

    merge_material = _build_merge_material(
        agent_a=bundle_a,
        agent_b=bundle_b,
        shared=shared,
        a_only=a_only,
        b_only=b_only,
        same_current_tile=same_current,
        both_have_route_intent=both_have_intent,
    )
    merge_id = "10AS-" + _hash_canonical(merge_material)[:32]

    return {
        "ok": True,
        "merge_schema_version": _MERGE_SCHEMA_VERSION,
        "merge_type": _MERGE_TYPE,
        "merge_id": merge_id,
        "source_phase": _SOURCE_PHASE,
        "claim_scope": _CLAIM_SCOPE,
        "agent_a": bundle_a,
        "agent_b": bundle_b,
        "shared_known_tile_ids": shared,
        "agent_a_only_known_tile_ids": a_only,
        "agent_b_only_known_tile_ids": b_only,
        "same_current_tile": same_current,
        "both_have_route_intent": both_have_intent,
        "errors": [],
    }


def export_two_agent_public_merge(merge: dict) -> str:
    """Export a two-agent public merge artifact as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(merge)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def merge_public_surface_files(
    public_state_a_path: Path | str,
    snapshot_a_path: Path | str,
    public_state_b_path: Path | str,
    snapshot_b_path: Path | str,
    *,
    route_intent_a_path: Path | str | None = None,
    route_intent_b_path: Path | str | None = None,
) -> dict:
    """Read parent public-surface JSON artifacts from caller-supplied paths and create a two-agent public merge.

    File loading is JSON-only.  No other I/O, no parent-phase chain
    delegation, no writes.
    """

    public_state_a = _read_json(public_state_a_path)
    snapshot_a = _read_json(snapshot_a_path)
    public_state_b = _read_json(public_state_b_path)
    snapshot_b = _read_json(snapshot_b_path)
    route_intent_a = (
        _read_json(route_intent_a_path) if route_intent_a_path is not None else None
    )
    route_intent_b = (
        _read_json(route_intent_b_path) if route_intent_b_path is not None else None
    )

    return create_two_agent_public_merge(
        public_state_a,
        snapshot_a,
        public_state_b,
        snapshot_b,
        route_intent_a=route_intent_a,
        route_intent_b=route_intent_b,
    )


def _read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
