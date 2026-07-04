"""Phase 10AX - shared public territory ref contract.

Create a deterministic sanitized shared-territory-ref contract artifact
from a Phase 10AS two-agent public merge.  10AX formalizes which public
territory references two agents have each declared in their
already-public surfaces, without ever inferring private knowledge,
co-presence, awareness, trust, cooperation, conflict, communication,
temporal overlap, coordination, planning, proximity, or any kind of
relationship.

Territory reference data is not present in the 10AS agent bundles.  The
caller supplies it directly as optional arguments — no 10AS update is
required.  Caller-supplied territory refs are treated as known public
declarations for that side when the sanitized territory ref is
non-empty.

10AX is the next rung in the public-observation contract stack.  It does
not infer shared private knowledge, co-presence, awareness, trust,
cooperation, conflict, communication, temporal overlap, coordination,
planning, proximity, or any kind of relationship.

10AX may say:

    "Both agents publicly cite territory ref T."

    "Both agents' public surfaces reference the same territory ref T."
    (a public-surface match; no claim of shared private knowledge,
    coordination, or awareness)

    "Both agents declare the same public territory ref."
    (a public-surface match; no claim of proximity, co-presence,
    travel timing, or relationship)

10AX may not say:

    "The agents are in the same territory."

    "The agents are aware of each other's territory refs."

    "The agents are coordinating or planning jointly."

    "The agents are or were co-present, nearby, or in the same
    location."

    "The agents' shared territory ref implies they have a
    relationship."

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_territory_ref_file`, which only reads JSON from a
caller-supplied path.

10AX consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10AX imports is
``sanitize_public_mapping`` from the public egress sanitizer (the same
helper 10AR, 10AS, 10AT, 10AU, 10AV, and 10AW already import).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10AX.1"
_CONTRACT_TYPE = "shared_territory_ref_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_territory_refs_only"

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
        "agent_a_territory_ref": None,
        "agent_b_territory_ref": None,
        "same_territory_ref": False,
        "shared_territory_ref": None,
        "agent_a_only_territory_ref": None,
        "agent_b_only_territory_ref": None,
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


def _resolve_territory_ref(
    bundle: dict[str, Any],
    caller_supplied: str | None,
) -> str | None:
    if caller_supplied is not None:
        sanitized = _safe_str(sanitize_public_mapping(caller_supplied))
        if sanitized:
            return sanitized
        return None
    return _safe_str(bundle.get("territory_ref")) or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_territory_ref_contract(
    merge: dict,
    agent_a_territory_ref: str | None = None,
    agent_b_territory_ref: str | None = None,
) -> dict:
    """Create a deterministic sanitized shared-territory-ref contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    and emits a thin shared-territory-ref contract recording which public
    territory references the two agents demonstrably share.  Territory
    reference data comes from the optional ``agent_a_territory_ref`` /
    ``agent_b_territory_ref`` arguments, falling back to the agent
    bundles' ``territory_ref`` fields if present.  Caller-supplied
    territory refs are treated as known public declarations for that
    side when the sanitized territory ref is non-empty.  Never infers
    private knowledge, co-presence, awareness, trust, cooperation,
    conflict, communication, temporal overlap, coordination, planning,
    proximity, or any kind of relationship.  Never raises; always
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

    shared_known_tile_ids = _sorted_unique_strings(
        sanitized_merge.get("shared_known_tile_ids")
    )

    same_current_tile = bool(sanitized_merge.get("same_current_tile"))

    # Resolve territory refs: caller-supplied overrides take
    # precedence. Caller-supplied territory refs are treated as known
    # public declarations for that side when the sanitized territory
    # ref is non-empty. Otherwise the bundle field is read if present.
    a_territory_ref = _resolve_territory_ref(
        sanitized_agent_a, agent_a_territory_ref
    )
    b_territory_ref = _resolve_territory_ref(
        sanitized_agent_b, agent_b_territory_ref
    )

    same_territory_ref = bool(
        a_territory_ref and b_territory_ref and a_territory_ref == b_territory_ref
    )
    shared_territory_ref = a_territory_ref if same_territory_ref else None
    a_only_territory_ref = (
        a_territory_ref if (a_territory_ref and not b_territory_ref) else None
    )
    b_only_territory_ref = (
        b_territory_ref if (b_territory_ref and not a_territory_ref) else None
    )

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
        "agent_a_territory_ref": a_territory_ref or "",
        "agent_b_territory_ref": b_territory_ref or "",
        "same_territory_ref": same_territory_ref,
        "shared_territory_ref": shared_territory_ref or "",
        "agent_a_only_territory_ref": a_only_territory_ref or "",
        "agent_b_only_territory_ref": b_only_territory_ref or "",
        "claim_scope": _CLAIM_SCOPE,
    }
    contract_id = "10AX-" + _hash_canonical(contract_material)[:32]

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
        "agent_a_territory_ref": a_territory_ref,
        "agent_b_territory_ref": b_territory_ref,
        "same_territory_ref": same_territory_ref,
        "shared_territory_ref": shared_territory_ref,
        "agent_a_only_territory_ref": a_only_territory_ref,
        "agent_b_only_territory_ref": b_only_territory_ref,
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_territory_ref_contract(contract: dict) -> str:
    """Export a shared-territory-ref contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_territory_ref_file(merge_json_path: Path | str) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a shared-territory-ref contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_territory_ref_contract(merge)
