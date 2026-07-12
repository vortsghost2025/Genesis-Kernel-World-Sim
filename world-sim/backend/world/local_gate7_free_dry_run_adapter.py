"""Phase 10CV - minimal gate-7-free dry-run adapter.

Consumes an already-built 10CJ dry-run adapter decision and emits one
deterministic inert decision in memory. It does not import or call 10BT
or 10CP, perform file I/O, or start runtime, background, scheduled, or
network activity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10CV.1"
_ADAPTER_TYPE = "gate7_free_dry_run_adapter_decision"
_ADAPTER_SCOPE = "gate7_free_dry_run_only"
_SOURCE_SCHEMA_VERSION = "10CJ.1"
_SOURCE_ADAPTER_TYPE = "runtime_adapter_dry_run_decision"
_SOURCE_ADAPTER_SCOPE = "dry_run_only"
_CANDIDATE_ACTION = "eligible_for_inert_ledger_log"

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
    "gate-7-free dry-run only; no runtime, daemon, scheduler, network, "
    "provider, launcher, container, ledger write, world-data access, "
    "movement, map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, timing, or "
    "coordination"
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


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _build_decision(
    *,
    errors: list[str],
    source_adapter_decision_id: str | None = None,
    source_decision_id: str | None = None,
    source_consumer_scope: str | None = None,
    source_signal_seen: bool = False,
    recognized_signal_type: str | None = None,
) -> dict[str, Any]:
    ok = not errors
    planned_action = "log_only" if ok else "none"
    candidate_action = _CANDIDATE_ACTION if ok else "none"

    decision_material = {
        "ok": ok,
        "gate7_adapter_schema_version": _SCHEMA_VERSION,
        "gate7_adapter_type": _ADAPTER_TYPE,
        "gate7_adapter_scope": _ADAPTER_SCOPE,
        "source_adapter_decision_id": source_adapter_decision_id,
        "source_decision_id": source_decision_id,
        "source_consumer_scope": source_consumer_scope,
        "source_signal_seen": source_signal_seen,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "candidate_action": candidate_action,
        "errors": errors,
    }
    gate7_adapter_decision_id = "10CV-" + _hash_canonical(decision_material)[:32]

    return {
        "ok": ok,
        "gate7_adapter_schema_version": _SCHEMA_VERSION,
        "gate7_adapter_type": _ADAPTER_TYPE,
        "gate7_adapter_scope": _ADAPTER_SCOPE,
        "gate7_adapter_decision_id": gate7_adapter_decision_id,
        "source_adapter_decision_id": source_adapter_decision_id,
        "source_decision_id": source_decision_id,
        "source_consumer_scope": source_consumer_scope,
        "source_signal_seen": source_signal_seen,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "candidate_action": candidate_action,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "ledger_write_attempted": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }


def create_gate7_free_dry_run_adapter_decision(
    adapter_decision: dict,
) -> dict:
    """Create an inert gate-7-free decision from an existing 10CJ decision."""

    if not isinstance(adapter_decision, dict):
        return _build_decision(errors=["adapter_decision must be a dict"])

    source_adapter_decision_id = _safe_str(
        adapter_decision.get("adapter_decision_id")
    )
    source_decision_id = _safe_str(adapter_decision.get("source_decision_id"))
    source_consumer_scope = _safe_str(
        adapter_decision.get("source_consumer_scope")
    )
    source_signal_seen = adapter_decision.get("source_signal_seen") is True
    recognized_signal_type = _safe_str(
        adapter_decision.get("recognized_signal_type")
    )

    errors: list[str] = []
    expected_fields = (
        ("ok", True),
        ("adapter_schema_version", _SOURCE_SCHEMA_VERSION),
        ("adapter_type", _SOURCE_ADAPTER_TYPE),
        ("adapter_scope", _SOURCE_ADAPTER_SCOPE),
        ("planned_action", "log_only"),
        ("executed", False),
        ("runtime_allowed", False),
        ("daemon_allowed", False),
        ("scheduler_allowed", False),
        ("network_allowed", False),
        ("world_sim_data_accessed", False),
        ("source_signal_seen", True),
    )
    for field, expected in expected_fields:
        value = adapter_decision.get(field)
        if value is not expected and value != expected:
            errors.append(f"{field} is not {expected!r}")

    if recognized_signal_type not in _KNOWN_SIGNAL_TYPES:
        errors.append("recognized_signal_type is not a known inert signal type")

    return _build_decision(
        errors=errors,
        source_adapter_decision_id=source_adapter_decision_id,
        source_decision_id=source_decision_id,
        source_consumer_scope=source_consumer_scope,
        source_signal_seen=source_signal_seen,
        recognized_signal_type=recognized_signal_type,
    )


def export_gate7_free_dry_run_adapter_decision(decision: dict) -> str:
    """Export an inert 10CV decision as deterministic JSON."""

    return json.dumps(decision, sort_keys=True, ensure_ascii=False)
