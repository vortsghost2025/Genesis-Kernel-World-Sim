"""Phase 10BG - shared public last event id equality contract.

Create a deterministic sanitized shared-public-last-event-id-equality
contract artifact from a Phase 10AS two-agent public merge.  10BG
formalizes whether two agents' public last event IDs are identical,
without ever inferring same event, same time, same sequence, same
interaction, or same relationship.

Last event IDs are supplied as optional caller arguments; 10BG does
not read them from 10AS bundles.  Caller-supplied last event IDs are
validated as non-empty strings; missing, non-string, or empty-after-
sanitize values are treated as ``None``.

10BG may say:

    "Agent A's public last_event_id is X."

    "Agent B's public last_event_id is Y."

    "Both agents report the same public last_event_id value."
    (public-surface equality only)

10BG may not say:

    "Both agents experienced the same event." (event-content inference)

    "Both agents were active at the same time." (temporal overlap inference)

    "The agents could have met or interacted." (meeting/interaction inference)

    "The agents have a temporal window in common." (window inference)

    "The agents' last event IDs imply a relationship." (relationship inference)

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, or route inference.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_last_event_id_equality_file`, which only reads JSON
from a caller-supplied path.

10BG consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10BG imports is
``sanitize_public_mapping`` from the public egress sanitizer (the same
helper 10AR, 10AS, 10AT, 10AU, 10AV, 10AW, 10AX, 10AY, 10AZ, 10BB,
10BC, 10BD, 10BE, and 10BF already import).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_CONTRACT_SCHEMA_VERSION = "10BG.1"
_CONTRACT_TYPE = "shared_public_last_event_id_equality_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_public_last_event_id_equality_only"

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
        "agent_a_last_event_id": None,
        "agent_b_last_event_id": None,
        "same_last_event_id": False,
        "shared_last_event_id": None,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


def _sanitize_event_id(raw: Any) -> str | None:
    """Sanitize a caller-supplied last event ID.

    Returns the sanitized non-empty string, or None if the input is not
    a non-empty string after sanitization.  Any sanitized value that
    contains a redaction marker is treated as None so that redacted
    private markers can never participate in equality comparisons.
    """
    if not isinstance(raw, str):
        return None
    sanitized = sanitize_public_mapping(raw)
    if not isinstance(sanitized, str) or not sanitized:
        return None
    if "[REDACTED" in sanitized:
        return None
    return sanitized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_last_event_id_equality_contract(
    merge: dict,
    *,
    agent_a_last_event_id: Any = None,
    agent_b_last_event_id: Any = None,
) -> dict:
    """Create a deterministic sanitized shared-public-last-event-id-equality contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    for provenance and agent identity only, plus optional caller-supplied
    last event IDs.  Emits a thin last-event-id-equality contract
    recording whether the two agents' supplied last event IDs are
    mechanically equal.  Caller-supplied last event IDs are validated
    as non-empty strings; missing, non-string, or empty-after-sanitize
    values are treated as ``None``.  Missing or None last event ID
    fields produce a contract with ok=True, id fields set to None, and
    all equality booleans set to False.  Never infers same event, same
    time, same sequence, same interaction, or same relationship.  Never
    raises; always returns a dict.
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

    # --- Caller-supplied last event IDs -----------------------------------
    # These are NOT read from 10AS bundles.  They are caller-supplied
    # optional arguments.  Validate as non-empty strings; missing,
    # non-string, or empty-after-sanitize values become None.

    a_event_id = _sanitize_event_id(agent_a_last_event_id)
    b_event_id = _sanitize_event_id(agent_b_last_event_id)

    # --- ID comparison ----------------------------------------------------
    # Pure string equality.  No semantic interpretation of ID meaning.
    # No ordering, no sequence inference, no temporal inference.

    same_last_event_id = bool(
        a_event_id is not None
        and b_event_id is not None
        and a_event_id == b_event_id
    )
    shared_last_event_id = a_event_id if same_last_event_id else None

    # Build the contract material — only contract-level public fields
    # feed the hash input so the id is stable across repeated calls
    # with the same inputs and across arbitrary input ordering.
    # agent_a_id and agent_b_id are preserved in A/B orientation;
    # they are NOT sorted.
    contract_material: dict[str, Any] = {
        "contract_schema_version": _CONTRACT_SCHEMA_VERSION,
        "claim_scope": _CLAIM_SCOPE,
        "source_merge_id": source_merge_id or "",
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "agent_a_last_event_id": a_event_id if a_event_id is not None else "",
        "agent_b_last_event_id": b_event_id if b_event_id is not None else "",
        "same_last_event_id": same_last_event_id,
        "shared_last_event_id": (
            shared_last_event_id
            if shared_last_event_id is not None
            else ""
        ),
    }
    contract_id = "10BG-" + _hash_canonical(contract_material)[:32]

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
        "agent_a_last_event_id": a_event_id,
        "agent_b_last_event_id": b_event_id,
        "same_last_event_id": same_last_event_id,
        "shared_last_event_id": shared_last_event_id,
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_last_event_id_equality_contract(contract: dict) -> str:
    """Export a last-event-id-equality contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_last_event_id_equality_file(
    merge_json_path: Path | str,
    *,
    agent_a_last_event_id: Any = None,
    agent_b_last_event_id: Any = None,
) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a last-event-id-equality contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_last_event_id_equality_contract(
        merge,
        agent_a_last_event_id=agent_a_last_event_id,
        agent_b_last_event_id=agent_b_last_event_id,
    )
