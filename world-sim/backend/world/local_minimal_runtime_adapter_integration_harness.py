"""Phase 10DL - minimal authorized runtime adapter integration harness.

Consumes an already-built 10CJ dry-run decision and delegates inert
validation to the existing 10CV transform. It emits the exact 10CJ
decision shape so existing bounded consumers, including the separately
authorized 10CP writer, remain compatible.

This module performs no file I/O and has no daemon, scheduler, network,
provider, launcher, container, movement, map, route, event, or NPC
behavior. Every runtime gate remains hard-coded False.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.local_gate7_free_dry_run_adapter import (
    create_gate7_free_dry_run_adapter_decision,
)


_ADAPTER_SCHEMA_VERSION = "10CJ.1"
_ADAPTER_TYPE = "runtime_adapter_dry_run_decision"
_ADAPTER_SCOPE = "dry_run_only"
_REQUIRED_CONSUMER_SCOPE = "record_public_equality_signal_only"
_CLAIM_BOUNDARY = (
    "minimal in-process integration only; no runtime action, daemon, "
    "scheduler, network, provider, launcher, container, world-data "
    "access, movement, map lookup, route execution, event emission, NPC "
    "behavior, co-presence, awareness, relationship, interaction, timing, "
    "or coordination"
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _safe_errors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["10CV returned an invalid errors envelope"]
    return [f"10CV: {error}" for error in value if isinstance(error, str)]


def _fallback_adapter_decision_id(gate7_decision: dict[str, Any]) -> str:
    material = {
        "adapter_schema_version": _ADAPTER_SCHEMA_VERSION,
        "source_decision_id": gate7_decision.get("source_decision_id"),
        "source_consumer_scope": gate7_decision.get("source_consumer_scope"),
        "source_signal_seen": gate7_decision.get("source_signal_seen") is True,
        "recognized_signal_type": gate7_decision.get("recognized_signal_type"),
    }
    return "10DL-" + _hash_canonical(material)[:32]


def run_minimal_runtime_adapter_integration(
    adapter_decision: dict,
) -> dict[str, Any]:
    """Return an exact, inert 10CJ-shaped result from a 10CJ decision.

    10CV performs the established gate-7-free validation. 10DL adds the
    identity checks needed by the existing 10CP writer, but does not
    import or invoke the writer itself.
    """

    gate7_decision = create_gate7_free_dry_run_adapter_decision(
        adapter_decision
    )
    errors = _safe_errors(gate7_decision.get("errors"))

    source_adapter_decision_id = gate7_decision.get(
        "source_adapter_decision_id"
    )
    source_decision_id = gate7_decision.get("source_decision_id")
    source_consumer_scope = gate7_decision.get("source_consumer_scope")

    if gate7_decision.get("ok") is True:
        if not _is_nonempty_str(source_adapter_decision_id):
            errors.append("10CJ adapter_decision_id is missing or empty")
        if not _is_nonempty_str(source_decision_id):
            errors.append("10CJ source_decision_id is missing or empty")
        if source_consumer_scope != _REQUIRED_CONSUMER_SCOPE:
            errors.append(
                "10CJ source_consumer_scope is not "
                "record_public_equality_signal_only"
            )

    ok = gate7_decision.get("ok") is True and not errors
    planned_action = gate7_decision.get("planned_action") if ok else "none"
    adapter_decision_id = (
        source_adapter_decision_id
        if _is_nonempty_str(source_adapter_decision_id)
        else _fallback_adapter_decision_id(gate7_decision)
    )

    return {
        "ok": ok,
        "adapter_schema_version": _ADAPTER_SCHEMA_VERSION,
        "adapter_type": _ADAPTER_TYPE,
        "adapter_scope": _ADAPTER_SCOPE,
        "adapter_decision_id": adapter_decision_id,
        "source_decision_id": source_decision_id,
        "source_consumer_scope": source_consumer_scope,
        "source_signal_seen": gate7_decision.get("source_signal_seen") is True,
        "recognized_signal_type": gate7_decision.get("recognized_signal_type"),
        "planned_action": planned_action,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }


def export_minimal_runtime_adapter_integration_result(result: dict) -> str:
    """Export a 10DL integration result as deterministic JSON."""

    return json.dumps(result, sort_keys=True, ensure_ascii=False)
