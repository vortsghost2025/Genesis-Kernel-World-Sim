"""Phase 10BB - shared public state hash equality contract.

Create a deterministic sanitized shared-public-state-hash-equality contract
artifact from a Phase 10AS two-agent public merge.  10BB formalizes
whether two agents' public state hash strings are identical, without ever
inferring same state, temporal overlap, co-presence, awareness, trust,
cooperation, conflict, communication, coordination, planning, proximity,
or any kind of relationship.

Public state hashes are supplied as optional caller arguments; 10BB does
not read them from 10AS bundles.  Caller-supplied public state hashes are
sanitized through `sanitize_public_mapping` first; empty strings and
non-string items are then dropped; redacted sanitizer output participates
in comparison if non-empty.

10BB may say:

    "Agent A's public state hash is X."

    "Agent B's public state hash is Y."

    "Both agents declare the same public state hash string."
    (public-surface equality only)

10BB may not say:

    "The agents' public state contents are identical." (state inference)

    "The agents were active at the same time." (co-presence inference)

    "The agents could have met or interacted." (meeting/interaction inference)

    "The agents have a temporal window in common." (window inference)

    "The agents' public state hashes imply a relationship." (relationship inference)

    Anything about awareness, communication, cooperation, conflict,
    relationship, trust, proximity, distance, ETA, or route inference.

Core invariant:
    No one gets to know more than they observed,
    and every observed claim has a replayable custody trail.

The module is pure: it never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`contract_public_state_hash_equality_file`, which only reads JSON
from a caller-supplied path.

10BB consumes 10AS only.  It never imports or calls 10AS, 10AR, 10AQ,
10AP, or any earlier phase creator; it never writes to a ledger, never
calls a projector, route planner, or movement helper; it never touches
``world-sim/data``.  The only upstream symbol 10BB imports is
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


_CONTRACT_SCHEMA_VERSION = "10BB.1"
_CONTRACT_TYPE = "shared_public_state_hash_equality_contract"
_SOURCE_PHASE = "10AS"
_CLAIM_SCOPE = "shared_public_state_hash_equality_only"

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
        "agent_a_public_state_hash": None,
        "agent_b_public_state_hash": None,
        "same_public_state_hash": False,
        "shared_public_state_hash": None,
        "claim_scope": _CLAIM_SCOPE,
        "errors": errors,
    }


def _sanitize_hash(raw: Any) -> str | None:
    """Sanitize a caller-supplied hash string.

    Returns the sanitized string, or None if the input is not a
    non-empty string after sanitization.
    """
    if not isinstance(raw, str):
        return None
    sanitized = _safe_str(sanitize_public_mapping(raw.strip()))
    if not sanitized:
        return None
    return sanitized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_shared_public_state_hash_equality_contract(
    merge: dict,
    *,
    agent_a_public_state_hash: Any = None,
    agent_b_public_state_hash: Any = None,
) -> dict:
    """Create a deterministic sanitized shared-public-state-hash-equality contract.

    Consumes an already-built Phase 10AS two-agent public merge artifact
    for provenance and agent identity only, plus optional caller-supplied
    public state hash strings.  Emits a thin state-hash-equality contract
    recording whether the two agents' supplied public state hash strings
    are mechanically equal.  Caller-supplied public state hashes are
    sanitized through `sanitize_public_mapping` first; empty strings and
    non-string items are then dropped; redacted sanitizer output
    participates in comparison if non-empty.  Missing or None public
    state hash fields produce a contract with ok=True, hash fields set to
    None, and all equality booleans set to False.  Never infers same
    state, temporal overlap, co-presence, awareness, trust, cooperation,
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

    # --- Caller-supplied public state hashes ------------------------------
    # These are NOT read from 10AS bundles.  They are caller-supplied
    # optional arguments.  Sanitize first, then drop non-string or
    # empty-after-sanitize.  Redacted sanitizer output participates in
    # comparison if non-empty.

    a_hash = _sanitize_hash(agent_a_public_state_hash)
    b_hash = _sanitize_hash(agent_b_public_state_hash)

    # --- Hash comparison --------------------------------------------------
    # Pure string equality.  No semantic interpretation of hash content.
    # No ordering, no sequence inference, no temporal inference.

    same_public_state_hash = bool(
        a_hash and b_hash and a_hash == b_hash
    )
    shared_public_state_hash = a_hash if same_public_state_hash else None

    # Build the contract material — only contract-level public fields
    # feed the hash input so the id is stable across repeated calls
    # with the same inputs and across arbitrary input ordering.
    # agent_a_id and agent_b_id are preserved in A/B orientation;
    # they are NOT sorted.
    contract_material: dict[str, Any] = {
        "source_merge_id": source_merge_id or "",
        "agent_a_id": agent_a_id,
        "agent_b_id": agent_b_id,
        "agent_a_public_state_hash": a_hash or "",
        "agent_b_public_state_hash": b_hash or "",
        "same_public_state_hash": same_public_state_hash,
        "shared_public_state_hash": shared_public_state_hash or "",
        "claim_scope": _CLAIM_SCOPE,
    }
    contract_id = "10BB-" + _hash_canonical(contract_material)[:32]

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
        "agent_a_public_state_hash": a_hash,
        "agent_b_public_state_hash": b_hash,
        "same_public_state_hash": same_public_state_hash,
        "shared_public_state_hash": shared_public_state_hash,
        "claim_scope": _CLAIM_SCOPE,
        "errors": [],
    }


def export_shared_public_state_hash_equality_contract(contract: dict) -> str:
    """Export a shared-public-state-hash-equality contract as stable sanitized JSON."""

    sanitized = sanitize_public_mapping(contract)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def contract_public_state_hash_equality_file(
    merge_json_path: Path | str,
    *,
    agent_a_public_state_hash: Any = None,
    agent_b_public_state_hash: Any = None,
) -> dict:
    """Read an exported Phase 10AS merge JSON file and create a shared-public-state-hash-equality contract.

    File loading is JSON-only at the caller's supplied path.  No other
    I/O or contract steps are performed.  The path must point to a
    single JSON file containing a 10AS merge artifact; the path is read
    with ``Path.read_text(encoding="utf-8")`` only.
    """

    path = Path(merge_json_path)
    text = path.read_text(encoding="utf-8")
    merge = json.loads(text)
    return create_shared_public_state_hash_equality_contract(
        merge,
        agent_a_public_state_hash=agent_a_public_state_hash,
        agent_b_public_state_hash=agent_b_public_state_hash,
    )
