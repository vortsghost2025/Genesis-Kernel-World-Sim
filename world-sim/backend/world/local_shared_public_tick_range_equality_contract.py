"""Phase 10AZ - shared public tick-range equality contract.

Create a deterministic sanitized shared-tick-range-equality contract
artifact from a Phase 10AS two-agent public merge.  10AZ formalizes
whether two agents' publicly declared tick ranges are mechanically
equal, without ever inferring temporal overlap, co-presence, awareness,
trust, cooperation, conflict, communication, coordination, planning,
proximity, or any kind of relationship.

Tick ranges are supplied as optional caller arguments; 10AZ does not
read them from 10AS bundles.  Missing or None tick fields produce a
contract with ok=True, tick fields set to None, and all equality
booleans set to False.

10AZ may say:

    "Agent A's public tick range is [X, Y]."

    "Agent B's public tick range is [X, Y]."

    "Both agents declare the same first tick." (public-surface equality
    only)

    "Both agents declare the same last tick." (public-surface equality
    only)

    "Both agents declare identical public tick ranges." (public-surface
    equality only)

10AZ may not say:

    "The agents' tick ranges overlap."

    "The agents were active at the same time."

    "The agents could have met or interacted."

    "The agents share a temporal window."

    "The agents' activity periods coincide."

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, or route inference.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_tick_range_equality_file`, which only reads JSON
from a caller-supplied path.

10AZ consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10AZ imports is
``sanitize_public_mapping`` from the public egress sanitizer (the same
helper 10AR, 10AS, 10AT, 10AU, 10AV, 10AW, 10AX, and 10AY already
import).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10AZ.1"
_CONTRACT_TYPE = "shared_public_tick_range_equality_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_tick_range_equality_only"

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
        "agent_a_first_tick": None,
        "agent_a_last_tick": None,
        "agent_b_first_tick": None,
        "agent_b_last_tick": None,
        "same_first_tick": False,
        "same_last_tick": False,
        "same_tick_range": False,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_tick_range_equality_contract(
    merge: dict,
    *,
    agent_a_first_tick: int | None = None,
    agent_a_last_tick: int | None = None,
    agent_b_first_tick: int | None = None,
    agent_b_last_tick: int | None = None,
) -> dict:
    """Create a deterministic sanitized shared-tick-range-equality contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    for provenance and agent identity only, plus optional caller-supplied
    tick fields.  Emits a thin tick-range-equality contract recording
    whether the two agents' supplied tick ranges are mechanically equal.
    Missing or None tick fields produce a contract with ok=True, tick
    fields set to None, and all equality booleans set to False.  Never
    infers temporal overlap, co-presence, awareness, trust, cooperation,
    conflict, communication, coordination, planning, proximity, or any
    kind of relationship.  Never raises; always returns a dict.
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

    # --- Caller-supplied tick fields --------------------------------------
    # These are NOT read from 10AS bundles.  They are caller-supplied
    # optional arguments.  Missing/None values are propagated as None.

    a_first = agent_a_first_tick if isinstance(agent_a_first_tick, int) else None
    a_last = agent_a_last_tick if isinstance(agent_a_last_tick, int) else None
    b_first = agent_b_first_tick if isinstance(agent_b_first_tick, int) else None
    b_last = agent_b_last_tick if isinstance(agent_b_last_tick, int) else None

    # --- Equality booleans -------------------------------------------------
    # Pure mechanical equality.  No overlap, no ordering, no range
    # containment, no temporal inference of any kind.

    same_first_tick = bool(
        a_first is not None
        and b_first is not None
        and a_first == b_first
    )
    same_last_tick = bool(
        a_last is not None
        and b_last is not None
        and a_last == b_last
    )
    same_tick_range = bool(
        same_first_tick
        and same_last_tick
        and a_first is not None
        and a_last is not None
        and b_first is not None
        and b_last is not None
    )

    # Build the contract material — only contract-level public fields
    # feed the hash input so the id is stable across repeated calls
    # with the same inputs and across arbitrary input ordering.
    # agent_a_id and agent_b_id are preserved in A/B orientation;
    # they are NOT sorted.
    contract_material: dict[str, Any] = {
        "source_merge_id": source_merge_id or "",
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "agent_a_first_tick": a_first if a_first is not None else "",
        "agent_a_last_tick": a_last if a_last is not None else "",
        "agent_b_first_tick": b_first if b_first is not None else "",
        "agent_b_last_tick": b_last if b_last is not None else "",
        "same_first_tick": same_first_tick,
        "same_last_tick": same_last_tick,
        "same_tick_range": same_tick_range,
        "claim_scope": _CLAIM_SCOPE,
    }
    contract_id = "10AZ-" + _hash_canonical(contract_material)[:32]

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
        "agent_a_first_tick": a_first,
        "agent_a_last_tick": a_last,
        "agent_b_first_tick": b_first,
        "agent_b_last_tick": b_last,
        "same_first_tick": same_first_tick,
        "same_last_tick": same_last_tick,
        "same_tick_range": same_tick_range,
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_tick_range_equality_contract(contract: dict) -> str:
    """Export a shared-tick-range-equality contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_tick_range_equality_file(
    merge_json_path: Path | str,
    *,
    agent_a_first_tick: int | None = None,
    agent_a_last_tick: int | None = None,
    agent_b_first_tick: int | None = None,
    agent_b_last_tick: int | None = None,
) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a shared-tick-range-equality contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_tick_range_equality_contract(
        merge,
        agent_a_first_tick=agent_a_first_tick,
        agent_a_last_tick=agent_a_last_tick,
        agent_b_first_tick=agent_b_first_tick,
        agent_b_last_tick=agent_b_last_tick,
    )
