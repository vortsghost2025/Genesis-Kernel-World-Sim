"""Phase 10BT - first shared public contract consumer harness.

This module is the first pure consumer layer in the shared-public
ladder.  It does not run an equality contract.  It does not see two
agents' public surfaces directly.  It consumes an already-built,
already-sanitized shared-public equality contract artifact (such as a
10BP snapshot_id equality contract) and emits a sanitized "consumer
decision" object describing exactly what a downstream runtime consumer
would do.

The decision object records:

    - whether a structurally valid contract was seen
    - whether the contract self-reported ``ok``
    - what the extracted equality signal looks like
    - that the harness is still read-only (no runtime, no daemon,
      no scheduler, no network action is ever performed)

The decision object explicitly forbids inference beyond the equality
contract's claim scope.  It never infers same map, same observation,
co-presence, awareness, communication, relationship, trust,
proximity, distance, ETA, route, or timing.

10BT consumes contract artifacts only.  It does not import 10AS, 10BP,
or any other contract creator.  It does not call any upstream helper.
It only imports the public egress sanitizer (the same helper every
shared-public rung already imports).

The module is pure.  It never mutates caller-owned input, never reads
secrets, never opens remote connections, never spawns processes, and
never writes files.  The only I/O happens in
:func:`consume_shared_public_contract_file`, which only reads JSON from
a caller-supplied path and then delegates to
:func:`create_shared_public_contract_consumer_decision`.

10BT may say:

    "10BT has seen a contract of type X."
    "10BT has read that the contract's ``ok`` flag is True."
    "10BT has recorded an equality signal when one is present."
    "No runtime action, daemon action, scheduler action, or network
     action is permitted by this decision."

10BT may not say:

    "Both agents are co-present." (co-presence inference)
    "Both agents used the same map." (map inference)
    "Both agents observed the same things." (observation inference)
    "The agents have a relationship." (relationship inference)
    Anything about awareness, communication, cooperation, conflict,
    trust, proximity, distance, ETA, route, timing, or active-at-the-
    same-time.

Core invariant:
    A consumer harness may record the existence and content of an
    equality contract; it may never promote that contract into any
    runtime action.  All runtime/daemon/scheduler/network flags are
    hard-coded False with no code path that can flip them to True.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_mapping


_DECISION_SCHEMA_VERSION = "10BT.1"
_DECISION_TYPE = "shared_public_contract_consumer_decision"
_CONSUMER_SCOPE = "record_public_equality_signal_only"

_CLAIM_BOUNDARY = (
    "public equality signal only; no runtime action, no co-presence, "
    "no awareness, no relationship, no timing inference"
)

_UNKNOWN_CONTRACT_SIGNAL = "unknown_contract_type"


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


def _runtime_flag_block() -> dict[str, Any]:
    """Hard-coded runtime/daemon/scheduler/network safety block.

    These flags are unconditionally False.  There is no code path in
    this module that can flip them to True.
    """

    return {
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
    }


def _decision_envelope(errors: list[str]) -> dict[str, Any]:
    """Construct the full 10BT decision envelope.

    The envelope has the complete expected shape regardless of whether
    the contract was valid.  Downstream consumers may rely on a
    consistent field set: on failure, the equality-signal fields are
    safe defaults and the runtime block is still hard-coded False.
    """

    runtime_block = _runtime_flag_block()

    return {
        "ok": not errors,
        "decision_schema_version": _DECISION_SCHEMA_VERSION,
        "decision_type": _DECISION_TYPE,
        "decision_id": None,
        "source_contract_id": None,
        "source_contract_type": None,
        "source_contract_schema_version": None,
        "source_claim_scope": None,
        "source_merge_hash": None,
        "consumer_scope": _CONSUMER_SCOPE,
        "contract_seen": False,
        "contract_ok": False,
        "equality_signal_present": False,
        "equality_signal_type": _UNKNOWN_CONTRACT_SIGNAL,
        "equality_signal_value": None,
        **runtime_block,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }


def _validate_contract(contract: dict) -> tuple[dict, list[str]]:
    """Read and validate the required contract fields.

    Returns a normalized copy of the contract plus a list of errors.
    On success, errors is empty and the contract kept all five required
    fields.  Required fields:

        - ok (must be True)
        - contract_id (non-empty string)
        - contract_type (non-empty string)
        - claim_scope (non-empty string)
        - source_merge_hash (non-empty string)
    """

    errors: list[str] = []

    if not isinstance(contract, dict):
        return {}, ["contract must be a dict"]

    ok_flag = contract.get("ok")
    if ok_flag is not True:
        errors.append("contract ok flag is not True")

    contract_id = _safe_str(contract.get("contract_id"))
    if not contract_id:
        errors.append("contract_id is missing or empty")

    contract_type = _safe_str(contract.get("contract_type"))
    if not contract_type:
        errors.append("contract_type is missing or empty")

    claim_scope = _safe_str(contract.get("claim_scope"))
    if not claim_scope:
        errors.append("claim_scope is missing or empty")

    source_merge_hash = _safe_str(contract.get("source_merge_hash"))
    if not source_merge_hash:
        errors.append("source_merge_hash is missing or empty")

    return (
        {
            "contract_id": contract_id or None,
            "contract_type": contract_type or None,
            "contract_schema_version": _safe_str(
                contract.get("contract_schema_version")
            ) or None,
            "claim_scope": claim_scope or None,
            "source_merge_hash": source_merge_hash or None,
        },
        errors,
    )


def _extract_equality_signal(contract_type: str, contract: dict) -> dict[str, Any]:
    """Map a known contract_type into the consumer decision's equality signal.

    For unknown contract types, the signal present flag is False, the
    signal type is ``unknown_contract_type``, and the value is None.
    The 10BP-specific branch reads the same_snapshot_id flag and the
    shared_snapshot_id field that 10BP publishes.
    """

    if contract_type == "shared_public_snapshot_id_equality_contract":
        same_snapshot_id = bool(contract.get("same_snapshot_id"))
        shared_snapshot_id = contract.get("shared_snapshot_id")
        if same_snapshot_id and isinstance(shared_snapshot_id, str):
            value: Any = sanitize_public_mapping(shared_snapshot_id)
            if not isinstance(value, str) or not value:
                value = None
        else:
            value = None
        return {
            "equality_signal_present": same_snapshot_id,
            "equality_signal_type": "snapshot_id_equality",
            "equality_signal_value": value,
        }

    if contract_type == "shared_snapshot_hash_equality_contract":
        same_snapshot_hash = bool(contract.get("same_snapshot_hash"))
        shared_snapshot_hash = contract.get("shared_snapshot_hash")
        if same_snapshot_hash and isinstance(shared_snapshot_hash, str):
            value: Any = sanitize_public_mapping(shared_snapshot_hash)
            if not isinstance(value, str) or not value:
                value = None
        else:
            value = None
        return {
            "equality_signal_present": same_snapshot_hash,
            "equality_signal_type": "snapshot_hash_equality",
            "equality_signal_value": value,
        }

    return {
        "equality_signal_present": False,
        "equality_signal_type": _UNKNOWN_CONTRACT_SIGNAL,
        "equality_signal_value": None,
    }


def create_shared_public_contract_consumer_decision(contract: dict) -> dict:
    """Create a deterministic sanitized shared-public-contract consumer decision.

    Accepts an already-built shared-public equality contract artifact
    (such as a 10BP snapshot_id equality contract).  Never mutates
    caller-owned input.  Reads the contract's five required fields
    (ok, contract_id, contract_type, claim_scope, source_merge_hash)
    and emits a sanitized decision object.

    The decision carries:

        - all five required output acceptance fields populated from
          the contract
        - a deterministic ``decision_id`` derived from the canonical
          decision material
        - an extracted equality signal (or ``unknown_contract_type``
          when the contract type is not yet wired up)
        - a hard-coded runtime/daemon/scheduler/network block where
          every flag is False

    Always returns a dict with the full expected envelope shape; on
    failure ``ok`` is False and ``errors`` carries the reasons.
    """

    errors: list[str] = []

    if not isinstance(contract, dict):
        envelope = _decision_envelope(["contract must be a dict"])
        envelope["contract_seen"] = False
        envelope["contract_ok"] = False
        return envelope

    sanitized_contract_raw = sanitize_public_mapping(contract)
    if not isinstance(sanitized_contract_raw, dict):
        envelope = _decision_envelope(["sanitized contract is not a dict"])
        envelope["contract_seen"] = False
        envelope["contract_ok"] = False
        return envelope

    local_contract = copy.deepcopy(sanitized_contract_raw)

    required, validation_errors = _validate_contract(local_contract)
    errors.extend(validation_errors)

    if errors:
        envelope = _decision_envelope(errors)
        envelope["contract_seen"] = False
        envelope["contract_ok"] = False
        return envelope

    contract_type = required["contract_type"] or ""
    signal = _extract_equality_signal(contract_type, local_contract)

    decision_material: dict[str, Any] = {
        "decision_schema_version": _DECISION_SCHEMA_VERSION,
        "consumer_scope": _CONSUMER_SCOPE,
        "source_contract_id": required["contract_id"],
        "source_contract_type": required["contract_type"],
        "source_claim_scope": required["claim_scope"],
        "source_merge_hash": required["source_merge_hash"],
        "equality_signal_present": signal["equality_signal_present"],
        "equality_signal_type": signal["equality_signal_type"],
        "equality_signal_value": signal["equality_signal_value"],
    }

    decision_id = "10BT-" + _hash_canonical(decision_material)[:32]

    decision: dict[str, Any] = {
        "ok": True,
        "decision_schema_version": _DECISION_SCHEMA_VERSION,
        "decision_type": _DECISION_TYPE,
        "decision_id": decision_id,
        "source_contract_id": required["contract_id"],
        "source_contract_type": required["contract_type"],
        "source_contract_schema_version": required[
            "contract_schema_version"
        ],
        "source_claim_scope": required["claim_scope"],
        "source_merge_hash": required["source_merge_hash"],
        "consumer_scope": _CONSUMER_SCOPE,
        "contract_seen": True,
        "contract_ok": True,
        "equality_signal_present": signal["equality_signal_present"],
        "equality_signal_type": signal["equality_signal_type"],
        "equality_signal_value": signal["equality_signal_value"],
        **_runtime_flag_block(),
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": [],
    }

    return decision


def export_shared_public_contract_consumer_decision(decision: dict) -> str:
    """Export a consumer decision artifact as stable sanitized JSON.

    Sanitizes the decision via the public egress sanitizer and serializes
    with stable key ordering and UTF-8 preservation.  Never raises.
    """

    sanitized = sanitize_public_mapping(decision)
    return json.dumps(sanitized, sort_keys=True, ensure_ascii=False)


def consume_shared_public_contract_file(
    contract_json_path: Path | str,
) -> dict:
    """Read an exported shared-public contract JSON file and consume it.

    The path is read with ``Path.read_text(encoding="utf-8")`` only.
    No other file I/O is performed.  The parsed JSON is delegated to
    :func:`create_shared_public_contract_consumer_decision`.
    """

    path = Path(contract_json_path)
    text = path.read_text(encoding="utf-8")
    contract = json.loads(text)
    return create_shared_public_contract_consumer_decision(contract)
