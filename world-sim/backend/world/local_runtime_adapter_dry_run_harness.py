"""Phase 10CJ - pure dry-run adapter seam.

First adapter after the 10CH readiness boundary audit. Sibling module to
10BT: 10BT is a pure consumer; 10CJ is a pure adapter that consumes
10BT decision objects and emits an inert dry-run adapter decision.

10CJ does not:

    - run any equality contract;
    - call the 10BT consumer creator;
    - import any equality contract creator;
    - import, read, or write the world data store;
    - import or touch background service / periodic job / network /
      container runtime code;
    - execute anything.

10CJ may read exactly five fields from a 10BT decision object:

    - ``ok``
    - ``decision_id``
    - ``consumer_scope``
    - ``equality_signal_type``
    - ``equality_signal_present``

It must never read the signal value field or any other field. The
signal value is an opaque public identifier; 10CJ does not copy,
transform, log, or expose it.

The adapter emits only an inert dry-run decision. ``executed`` is
hard-coded False. ``planned_action`` can only be ``"none"`` or
``"log_only"``; the "log_only" action is an in-memory record intent
only and is never performed. Every gate flag is hard-coded False with
no code path that can flip it to True.

10CJ may say:

    "10CJ has seen a 10BT decision."
    "10CJ has read that the decision ``ok`` flag is True."
    "10CJ has recorded an equality signal type when one is present."
    "No runtime action, background-service action, periodic-job
     action, network action, or world-data access is permitted."

10CJ may not say:

    "Two agents are shared-present." (shared-presence inference)
    "Two agents should relocate." (relocation)
    "A route should be planned or executed." (route)
    "A map should be inspected." (map inspection)
    Anything about perception, social link, timing, periodic work,
    event publish, NPC behavior, or coordination.

Core invariant:
    An adapter may record the existence and type of a 10BT equality
    signal; it may never promote that signal into any runtime action.
    All runtime / background-service / periodic-job / network /
    world-data flags are hard-coded False with no code path that can
    flip them to True.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_ADAPTER_SCHEMA_VERSION = "10CJ.1"
_ADAPTER_TYPE = "runtime_adapter_dry_run_decision"
_ADAPTER_SCOPE = "dry_run_only"
_REQUIRED_CONSUMER_SCOPE = "record_public_equality_signal_only"

_KNOWN_SIGNAL_TYPES = frozenset(
    {
        "snapshot_id_equality",
        "snapshot_hash_equality",
        "current_tile_id_equality",
        "route_intent_id_equality",
        "known_tile_ids_set_equality",
        "route_destination_tile_id_equality",
    }
)

_CLAIM_BOUNDARY = (
    "dry-run adapter only; no runtime action, no background-service "
    "action, no periodic-job action, no network action, no world-data "
    "access, no relocation, no map inspection, no shared-presence, "
    "no perception, no social link, no timing inference"
)


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


def _gate_block() -> dict[str, Any]:
    """Hard-coded safety gate block.

    These flags are unconditionally False. There is no code path in
    this module that can flip them to True. ``daemon_allowed`` and
    ``scheduler_allowed`` are mandated inert False outputs, not
    background-service or periodic-job behavior.
    """

    return {
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
    }


def _build_adapter_decision(
    errors: list[str],
    source_decision_id: Any,
    source_consumer_scope: Any,
    source_signal_seen: bool,
    recognized_signal_type: Any,
    planned_action: str,
) -> dict[str, Any]:
    """Construct the full 10CJ dry-run adapter decision envelope.

    The envelope has the complete expected shape regardless of whether
    the input was valid. On failure, ``ok`` is False, ``executed`` is
    still False, and the gate block is still hard-coded False.
    """

    ok = not errors
    executed = False

    decision_material: dict[str, Any] = {
        "adapter_schema_version": _ADAPTER_SCHEMA_VERSION,
        "adapter_scope": _ADAPTER_SCOPE,
        "source_decision_id": source_decision_id,
        "source_consumer_scope": source_consumer_scope,
        "source_signal_seen": source_signal_seen,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "executed": executed,
    }

    adapter_decision_id = "10CJ-" + _hash_canonical(decision_material)[:32]

    return {
        "ok": ok,
        "adapter_schema_version": _ADAPTER_SCHEMA_VERSION,
        "adapter_type": _ADAPTER_TYPE,
        "adapter_scope": _ADAPTER_SCOPE,
        "adapter_decision_id": adapter_decision_id,
        "source_decision_id": source_decision_id,
        "source_consumer_scope": source_consumer_scope,
        "source_signal_seen": source_signal_seen,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "executed": executed,
        **_gate_block(),
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }


def create_runtime_adapter_dry_run_decision(decision: dict) -> dict:
    """Create a deterministic inert dry-run adapter decision from a 10BT decision.

    Accepts an already-built 10BT consumer decision object. Reads only
    the allowlisted five fields (``ok``, ``decision_id``,
    ``consumer_scope``, ``equality_signal_type``,
    ``equality_signal_present``). Never reads the signal value field
    or any other field. Never mutates caller-owned input. Never
    executes anything.

    Always returns a dict with the full expected envelope shape; on
    failure ``ok`` is False and ``errors`` carries the reasons.
    """

    if not isinstance(decision, dict):
        return _build_adapter_decision(
            errors=["decision must be a dict"],
            source_decision_id=None,
            source_consumer_scope=None,
            source_signal_seen=False,
            recognized_signal_type=None,
            planned_action="none",
        )

    ok_flag = decision.get("ok")
    if ok_flag is not True:
        return _build_adapter_decision(
            errors=["decision ok flag is not True"],
            source_decision_id=decision.get("decision_id"),
            source_consumer_scope=decision.get("consumer_scope"),
            source_signal_seen=False,
            recognized_signal_type=None,
            planned_action="none",
        )

    consumer_scope = _safe_str(decision.get("consumer_scope"))
    if consumer_scope != _REQUIRED_CONSUMER_SCOPE:
        return _build_adapter_decision(
            errors=["decision consumer_scope is not record_public_equality_signal_only"],
            source_decision_id=decision.get("decision_id"),
            source_consumer_scope=consumer_scope or None,
            source_signal_seen=False,
            recognized_signal_type=None,
            planned_action="none",
        )

    signal_present = decision.get("equality_signal_present")
    if signal_present is not True:
        return _build_adapter_decision(
            errors=[],
            source_decision_id=decision.get("decision_id"),
            source_consumer_scope=_REQUIRED_CONSUMER_SCOPE,
            source_signal_seen=False,
            recognized_signal_type=None,
            planned_action="none",
        )

    signal_type = _safe_str(decision.get("equality_signal_type"))

    if signal_type in _KNOWN_SIGNAL_TYPES:
        return _build_adapter_decision(
            errors=[],
            source_decision_id=decision.get("decision_id"),
            source_consumer_scope=_REQUIRED_CONSUMER_SCOPE,
            source_signal_seen=True,
            recognized_signal_type=signal_type,
            planned_action="log_only",
        )

    return _build_adapter_decision(
        errors=[],
        source_decision_id=decision.get("decision_id"),
        source_consumer_scope=_REQUIRED_CONSUMER_SCOPE,
        source_signal_seen=True,
        recognized_signal_type=None,
        planned_action="none",
    )


def export_runtime_adapter_dry_run_decision(adapter_decision: dict) -> str:
    """Export a dry-run adapter decision artifact as stable JSON.

    Serializes with stable key ordering and UTF-8 preservation. Never
    raises.
    """

    return json.dumps(
        adapter_decision,
        sort_keys=True,
        ensure_ascii=False,
    )
