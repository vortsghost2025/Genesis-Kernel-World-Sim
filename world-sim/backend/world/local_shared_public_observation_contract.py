"""Phase 10AT - shared public observation contract.

Create a deterministic sanitized shared-public-observation contract
artifact from a Phase 10AS two-agent public merge.  10AT formalizes how
two agents can produce a shared public observation artifact from their
already-public surfaces, without ever inferring private knowledge,
co-presence, awareness, trust, cooperation, conflict, communication,
or any kind of relationship.

10AT may say:

    "These two agents share public observation of tiles X/Y/Z."

    "Their two published public surfaces report the same current
     public tile T (a public-surface match; no co-presence claim)."

    "Both agents have each published an intent_only route intent toward
     the same destination tile D."

10AT may not say:

    "The agents are / were co-present, met, became aware of each other,
     or know each other privately."

    "The agents trust, cooperate, conflict, communicate, exchange
     memory, share private state, perceive each other, or traveled
     together."

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_shared_observation_file`, which only reads JSON from a
caller-supplied path.

10AT consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10AT imports is
``sanitize_public_mapping`` from the public egress sanitizer (the same
helper 10AR and 10AS already import).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10AT.1"
_CONTRACT_TYPE = "shared_public_observation_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_public_only"

_EXPECTED_MERGE_TYPE = "two_agent_public_merge"
_EXPECTED_MERGE_SCHEMA_VERSION = "10AS.1"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _empty_contract(errors: list[str]) -> dict[str, Any]:
    return {
        "ok": not errors,
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "contract_type": _CONTRACT_TYPE,
        "contract_id": None,
        "source_phase": _SOURCE_PHASE,
        "source_merge_id": None,
        "source_merge_hash": None,
        "source_merge_schema_version": None,
        "agent_a_id": None,
        "agent_b_id": None,
        "shared_known_tile_ids": [],
        "shared_known_tile_count": 0,
        "same_current_tile": False,
        "shared_current_tile_id": None,
        "both_have_route_intent": False,
        "both_route_to_same_destination": False,
        "shared_route_destination_tile_id": None,
        "agent_a_route_destination_tile_id": None,
        "agent_b_route_destination_tile_id": None,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


def _sorted_unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, str) and item:
            seen.add(item)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_public_observation_contract(merge: dict) -> dict:
    """Create a deterministic sanitized shared-public-observation contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    and emits a thin shared-public-observation contract recording which
    public observations the two agents demonstrably share.  Never
    infers private knowledge, co-presence, awareness, trust,
    cooperation, conflict, or communication.  Never raises; always
    returns a dict.
    """

    errors: list[str] = []

    if not isinstance(merge, dict):
        contract = _empty_contract(["merge must be a dict"])
        contract["ok"] = False
        return contract

    # Deep-copy before any read so the caller-owned data can never be
    # mutated by validation, sanitization, or hashing.
    local_merge = copy.deepcopy(merge)

    # --- Structural validation of the 10AS merge --------------------------

    if local_merge.get("ok") is not True:
        errors.append("merge ok flag is not True")

    merge_type = local_merge.get("merge_type")
    if merge_type != _EXPECTED_MERGE_TYPE:
        errors.append(
            "merge_type is not " + repr(_EXPECTED_MERGE_TYPE)
        )

    merge_schema_version = local_merge.get("merge_schema_version")
    if merge_schema_version != _EXPECTED_MERGE_SCHEMA_VERSION:
        errors.append(
            "merge_schema_version is not "
            + repr(_EXPECTED_MERGE_SCHEMA_VERSION)
        )

    agent_a_raw = local_merge.get("agent_a")
    agent_b_raw = local_merge.get("agent_b")
    if not isinstance(agent_a_raw, dict):
        errors.append("agent_a must be a dict")
    if not isinstance(agent_b_raw, dict):
        errors.append("agent_b must be a dict")

    # Early bail on structural failure — we cannot trust bundle shape
    # past this point, and reading them would risk KeyError-ing.
    if errors:
        contract = _empty_contract(errors)
        contract["ok"] = False
        # Surface the source merge id where determinable so the caller
        # can correlate a failed contract with its source merge.
        source_merge_id = _safe_str(local_merge.get("merge_id"))
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_schema_version"] = (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        )
        return contract

    assert isinstance(agent_a_raw, dict)
    assert isinstance(agent_b_raw, dict)

    a_id_raw = _safe_str(agent_a_raw.get("agent_id"))
    b_id_raw = _safe_str(agent_b_raw.get("agent_id"))
    if not a_id_raw:
        errors.append("agent_a_id is missing or empty")
    if not b_id_raw:
        errors.append("agent_b_id is missing or empty")
    if a_id_raw and b_id_raw and a_id_raw == b_id_raw:
        errors.append("agent_a_id and agent_b_id must be distinct")

    shared_known_raw = local_merge.get("shared_known_tile_ids")
    if not isinstance(shared_known_raw, list):
        errors.append("shared_known_tile_ids must be a list")

    if not isinstance(local_merge.get("same_current_tile"), bool):
        errors.append("same_current_tile must be a bool")
    if not isinstance(local_merge.get("both_have_route_intent"), bool):
        errors.append("both_have_route_intent must be a bool")

    if errors:
        contract = _empty_contract(errors)
        contract["ok"] = False
        source_merge_id = _safe_str(local_merge.get("merge_id"))
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_schema_version"] = (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        )
        return contract

    # --- Sanitize the whole merge for the provenance hash -----------------

    sanitized_merge = sanitize_public_mapping(local_merge)
    if not isinstance(sanitized_merge, dict):
        contract = _empty_contract(["sanitized merge is not a dict"])
        contract["ok"] = False
        return contract

    source_merge_id = _safe_str(sanitized_merge.get("merge_id"))
    source_merge_hash = _hash_canonical(sanitized_merge)

    sanitized_agent_a = sanitized_merge.get("agent_a")
    sanitized_agent_b = sanitized_merge.get("agent_b")
    if not isinstance(sanitized_agent_a, dict):
        contract = _empty_contract(["sanitized agent_a is not a dict"])
        contract["ok"] = False
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_hash"] = source_merge_hash
        return contract
    if not isinstance(sanitized_agent_b, dict):
        contract = _empty_contract(["sanitized agent_b is not a dict"])
        contract["ok"] = False
        if source_merge_id:
            contract["source_merge_id"] = source_merge_id
        contract["source_merge_hash"] = source_merge_hash
        return contract

    agent_a_id = _safe_str(sanitized_agent_a.get("agent_id"))
    agent_b_id = _safe_str(sanitized_agent_b.get("agent_id"))

    # Re-sanitize the ids one more time for belt-and-suspenders: a
    # private marker that survived sanitize_public_mapping (shouldn't
    # happen, but the contract must never leak one) cannot reach the
    # output via the agent id fields.
    agent_a_id = _safe_str(sanitize_public_mapping(agent_a_id)) or agent_a_id
    agent_b_id = _safe_str(sanitize_public_mapping(agent_b_id)) or agent_b_id

    # Read public bundle fields from the sanitized bundle only.
    a_current = _safe_str(sanitized_agent_a.get("current_tile_id"))
    b_current = _safe_str(sanitized_agent_b.get("current_tile_id"))
    a_route_dest = _safe_str(sanitized_agent_a.get("route_destination_tile_id"))
    b_route_dest = _safe_str(sanitized_agent_b.get("route_destination_tile_id"))

    shared_known_tile_ids = _sorted_unique_strings(
        sanitized_merge.get("shared_known_tile_ids")
    )

    same_current_tile = bool(sanitized_merge.get("same_current_tile"))
    both_have_route_intent = bool(sanitized_merge.get("both_have_route_intent"))

    if same_current_tile and a_current and b_current:
        # Guard against the 10AS contract publishing same_current_tile
        # while the bundle current tiles differ — surface it as a safe
        # error rather than silently producing a wrong contract.
        if a_current != b_current:
            errors.append(
                "same_current_tile is True but agent current_tile_ids differ"
            )
            contract = _empty_contract(errors)
            contract["ok"] = False
            contract["source_merge_id"] = source_merge_id or None
            contract["source_merge_hash"] = source_merge_hash
            contract["source_merge_schema_version"] = (
                merge_schema_version
                if isinstance(merge_schema_version, str)
                else None
            )
            return contract
        shared_current_tile_id: str | None = a_current
    else:
        shared_current_tile_id = None

    # Both route to the same destination only when both have an intent
    # AND both destination tile ids are non-empty and equal.
    both_route_same = (
        both_have_route_intent
        and bool(a_route_dest)
        and bool(b_route_dest)
        and a_route_dest == b_route_dest
    )
    shared_route_destination_tile_id: str | None = (
        a_route_dest if both_route_same else None
    )

    # Build the contract material — only contract-level public fields
    # feed the hash input so the id is stable across repeated calls
    # with the same inputs and across arbitrary input ordering.
    contract_material: dict[str, Any] = {
        "source_merge_id": source_merge_id or "",
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "shared_known_tile_ids": shared_known_tile_ids,
        "same_current_tile": same_current_tile,
        "shared_current_tile_id": shared_current_tile_id or "",
        "both_have_route_intent": both_have_route_intent,
        "both_route_to_same_destination": both_route_same,
        "shared_route_destination_tile_id": (
            shared_route_destination_tile_id or ""
        ),
        "claim_scope": _CLAIM_SCOPE,
    }
    contract_id = "10AT-" + _hash_canonical(contract_material)[:32]

    return {
        "ok": True,
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "contract_type": _CONTRACT_TYPE,
        "contract_id": contract_id,
        "source_phase": _SOURCE_PHASE,
        "source_merge_id": source_merge_id or None,
        "source_merge_hash": source_merge_hash,
        "source_merge_schema_version": (
            merge_schema_version
            if isinstance(merge_schema_version, str)
            else None
        ),
        "agent_a_id": agent_a_id or None,
        "agent_b_id": agent_b_id or None,
        "shared_known_tile_ids": shared_known_tile_ids,
        "shared_known_tile_count": len(shared_known_tile_ids),
        "same_current_tile": same_current_tile,
        "shared_current_tile_id": shared_current_tile_id,
        "both_have_route_intent": both_have_route_intent,
        "both_route_to_same_destination": both_route_same,
        "shared_route_destination_tile_id": shared_route_destination_tile_id,
        "agent_a_route_destination_tile_id": a_route_dest or None,
        "agent_b_route_destination_tile_id": b_route_dest or None,
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_public_observation_contract(contract: dict) -> str:
    """Export a shared-public-observation contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_shared_observation_file(merge_json_path: Path | str) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a shared public observation contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_public_observation_contract(merge)
