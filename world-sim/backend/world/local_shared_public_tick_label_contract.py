"""Phase 10BA - shared public tick label contract.

Create a deterministic sanitized shared-tick-label contract artifact from
a Phase 10AS two-agent public merge.  10BA formalizes whether two agents'
supplied tick label sets are mechanically equal, without ever inferring
temporal overlap, co-presence, awareness, trust, cooperation, conflict,
communication, coordination, planning, proximity, or any kind of
relationship.

Tick labels are supplied as optional caller arguments; 10BA does not
read them from 10AS bundles.  Caller-supplied tick labels are sanitized
through `sanitize_public_mapping` first; empty strings and non-string
items are then dropped; remaining labels are deduplicated; the resulting
sanitized label sets are what 10BA compares.

10BA may say:

    "Agent A's public tick label is X."

    "Agent B's public tick label is Y."

    "Both agents declare the same tick label." (public-surface equality
    only)

    "Agent A declares tick labels X and Y." (public-surface enumeration
    only)

    "Agent B declares tick labels X and Y." (public-surface enumeration
    only)

    "Both agents declare the same set of tick labels." (public-surface
    set equality only)

10BA may not say:

    "The agents' ticks overlap in time."

    "The agents were active at the same time."

    "The agents could have met or interacted."

    "The agents share a temporal window."

    "The agents' tick sequences are synchronized."

    "The agents' tick labels imply a relationship."

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, or route inference.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_tick_label_file`, which only reads JSON
from a caller-supplied path.

10BA consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10BA imports is
``sanitize_public_mapping`` from the public egress sanitizer (the same
helper 10AR, 10AS, 10AT, 10AU, 10AV, 10AW, 10AX, 10AY, and 10AZ
already import).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10BA.1"
_CONTRACT_TYPE = "shared_public_tick_label_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_tick_label_equality_only"

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
        "agent_a_tick_labels": [],
        "agent_b_tick_labels": [],
        "agent_a_tick_label_count": 0,
        "agent_b_tick_label_count": 0,
        "same_tick_labels": False,
        "shared_tick_labels": [],
        "shared_tick_label_count": 0,
        "agent_a_only_tick_labels": [],
        "agent_a_only_tick_label_count": 0,
        "agent_b_only_tick_labels": [],
        "agent_b_only_tick_label_count": 0,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


def _sanitize_and_clean_labels(
    raw_labels: Any,
) -> list[str]:
    """Sanitize, drop empty/non-string, deduplicate a tick-label list.

    Returns a sorted list of unique sanitized string labels.
    """
    if not isinstance(raw_labels, list):
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in raw_labels:
        if not isinstance(item, str):
            continue
        sanitized = _safe_str(sanitize_public_mapping(item))
        if not sanitized:
            continue
        if sanitized not in seen:
            seen.add(sanitized)
            cleaned.append(sanitized)
    return sorted(cleaned)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_tick_label_contract(
    merge: dict,
    *,
    agent_a_tick_labels: Any = None,
    agent_b_tick_labels: Any = None,
) -> dict:
    """Create a deterministic sanitized shared-tick-label contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    for provenance and agent identity only, plus optional caller-supplied
    tick label lists.  Emits a thin tick-label contract recording whether
    the two agents' supplied tick label sets are mechanically equal.
    Caller-supplied tick labels are sanitized through
    `sanitize_public_mapping` first; empty strings and non-string items
    are then dropped; remaining labels are deduplicated; the resulting
    sanitized label sets are what 10BA compares.  Missing or None tick
    label lists produce a contract with ok=True, empty label lists, and
    all equality/set booleans set to False.  Never infers temporal
    overlap, co-presence, awareness, trust, cooperation, conflict,
    communication, coordination, planning, proximity, or any kind of
    relationship.  Never raises; always returns a dict.
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

    # --- Caller-supplied tick labels --------------------------------------
    # These are NOT read from 10AS bundles.  They are caller-supplied
    # optional arguments.  Sanitize first, then drop empty/non-string,
    # then deduplicate.  The resulting sanitized label sets are what
    # 10BA compares.

    a_labels = _sanitize_and_clean_labels(agent_a_tick_labels)
    b_labels = _sanitize_and_clean_labels(agent_b_tick_labels)

    # --- Set operations ---------------------------------------------------
    # Pure set equality and set algebra.  No ordering, no sequence
    # inference, no temporal inference of any kind.

    a_set = set(a_labels)
    b_set = set(b_labels)

    same_tick_labels = bool(a_set == b_set and a_set)
    shared_tick_labels = sorted(a_set & b_set)
    agent_a_only_tick_labels = sorted(a_set - b_set)
    agent_b_only_tick_labels = sorted(b_set - a_set)

    # Build the contract material — only contract-level public fields
    # feed the hash input so the id is stable across repeated calls
    # with the same inputs and across arbitrary input ordering.
    # agent_a_id and agent_b_id are preserved in A/B orientation;
    # they are NOT sorted.
    contract_material: dict[str, Any] = {
        "source_merge_id": source_merge_id or "",
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "agent_a_tick_labels": a_labels,
        "agent_b_tick_labels": b_labels,
        "same_tick_labels": same_tick_labels,
        "shared_tick_labels": shared_tick_labels,
        "agent_a_only_tick_labels": agent_a_only_tick_labels,
        "agent_b_only_tick_labels": agent_b_only_tick_labels,
        "claim_scope": _CLAIM_SCOPE,
    }
    contract_id = "10BA-" + _hash_canonical(contract_material)[:32]

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
        "agent_a_tick_labels": a_labels,
        "agent_b_tick_labels": b_labels,
        "agent_a_tick_label_count": len(a_labels),
        "agent_b_tick_label_count": len(b_labels),
        "same_tick_labels": same_tick_labels,
        "shared_tick_labels": shared_tick_labels,
        "shared_tick_label_count": len(shared_tick_labels),
        "agent_a_only_tick_labels": agent_a_only_tick_labels,
        "agent_a_only_tick_label_count": len(agent_a_only_tick_labels),
        "agent_b_only_tick_labels": agent_b_only_tick_labels,
        "agent_b_only_tick_label_count": len(agent_b_only_tick_labels),
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_tick_label_contract(contract: dict) -> str:
    """Export a shared-tick-label contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_tick_label_file(
    merge_json_path: Path | str,
    *,
    agent_a_tick_labels: Any = None,
    agent_b_tick_labels: Any = None,
) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a shared-tick-label contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_tick_label_contract(
        merge,
        agent_a_tick_labels=agent_a_tick_labels,
        agent_b_tick_labels=agent_b_tick_labels,
    )
