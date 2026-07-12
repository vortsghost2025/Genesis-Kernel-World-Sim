"""Phase 10DR - minimal inert ledger write orchestrator.

Consumes an already-built 10BT decision and passes it through the existing
10CJ and 10DL public functions. 10DL performs the established 10CV
validation. Only a fully accepted inert result with two explicit ledger
paths is passed to the existing 10CP writer.

This module is caller-driven and performs no direct file I/O. It never
chooses a path, creates a directory, scans or reads a ledger, or starts any
runtime, daemon, scheduler, network, provider, launcher, or container work.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.local_minimal_runtime_adapter_integration_harness import (
    run_minimal_runtime_adapter_integration,
)
from backend.world.local_runtime_adapter_dry_run_harness import (
    create_runtime_adapter_dry_run_decision,
)
from backend.world.local_runtime_adapter_inert_ledger_writer import (
    append_inert_ledger_record,
)


_SCHEMA_VERSION = "10DR.1"
_ORCHESTRATOR_TYPE = "minimal_inert_ledger_write_orchestrator_result"
_ORCHESTRATOR_SCOPE = "inert_ledger_write_only"
_SOURCE_SCHEMA_VERSION = "10BT.1"
_SOURCE_TYPE = "shared_public_contract_consumer_decision"
_SOURCE_SCOPE = "record_public_equality_signal_only"

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

_SOURCE_GATE_FLAGS = (
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
)

_OPTIONAL_DENIED_FLAGS = (
    "world_sim_data_accessed",
    "gate7_activity_allowed",
    "provider_allowed",
    "launcher_allowed",
    "container_allowed",
    "docker_allowed",
)

_INTEGRATION_GATE_FLAGS = (
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
)

_10CJ_FIELDS = frozenset(
    {
        "ok",
        "adapter_schema_version",
        "adapter_type",
        "adapter_scope",
        "adapter_decision_id",
        "source_decision_id",
        "source_consumer_scope",
        "source_signal_seen",
        "recognized_signal_type",
        "planned_action",
        "executed",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "claim_boundary",
        "errors",
    }
)

_FORBIDDEN_SOURCE_FIELDS = frozenset(
    {
        "agent_id",
        "tile",
        "route",
        "path",
        "destination",
        "timing",
        "co_presence",
        "awareness",
        "relationship",
        "interaction",
        "movement",
        "map_lookup",
        "emit_event",
        "create_event",
        "npc_behavior",
        "daemon_output",
        "scheduler_output",
        "network_output",
    }
)

_CLAIM_BOUNDARY = (
    "inert audit-ledger orchestration only; no runtime action, daemon, "
    "scheduler, network, provider, launcher, container, movement, map "
    "lookup, route execution, event emission, NPC behavior, co-presence, "
    "awareness, relationship, interaction, timing, or coordination"
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
        try:
            value.encode("utf-8")
        except UnicodeError:
            return None
        return value
    return None


def _safe_errors(value: Any, source: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{source} returned an invalid errors envelope"]
    if any(_safe_str(error) is None for error in value):
        return [f"{source} returned an invalid errors envelope"]
    return [f"{source}: {error}" for error in value]


def _matches_expected(value: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return value is expected
    return value == expected


def _validate_source_decision(decision: object) -> list[str]:
    if not isinstance(decision, dict):
        return ["consumer_decision must be a dict"]

    errors: list[str] = []
    forbidden = sorted(_FORBIDDEN_SOURCE_FIELDS.intersection(decision))
    if forbidden:
        errors.append("forbidden consumer decision fields: " + ", ".join(forbidden))

    expected_fields = {
        "ok": True,
        "decision_schema_version": _SOURCE_SCHEMA_VERSION,
        "decision_type": _SOURCE_TYPE,
        "consumer_scope": _SOURCE_SCOPE,
        "equality_signal_present": True,
    }
    for field, expected in expected_fields.items():
        value = decision.get(field)
        if not _matches_expected(value, expected):
            errors.append(f"{field} is not {expected!r}")

    if _safe_str(decision.get("decision_id")) is None:
        errors.append("decision_id is missing or empty")

    if decision.get("equality_signal_type") not in _KNOWN_SIGNAL_TYPES:
        errors.append("equality_signal_type is not a known inert signal type")

    for flag in _SOURCE_GATE_FLAGS:
        if decision.get(flag) is not False:
            errors.append(f"{flag} is not False")

    for flag in _OPTIONAL_DENIED_FLAGS:
        if flag in decision and decision.get(flag) is not False:
            errors.append(f"{flag} is not False")

    return errors


def _validate_10cj_result(
    result: object,
    *,
    stage: str,
    expected_consumer_decision_id: str,
    expected_signal_type: str,
    expected_adapter_decision_id: str | None = None,
) -> list[str]:
    if not isinstance(result, dict):
        return [f"{stage} result must be a dict"]

    errors = _safe_errors(result.get("errors"), stage)
    actual_fields = set(result)
    missing_fields = sorted(_10CJ_FIELDS - actual_fields)
    unexpected_fields = sorted(actual_fields - _10CJ_FIELDS)
    if missing_fields:
        errors.append(f"{stage}: missing fields: " + ", ".join(missing_fields))
    if unexpected_fields:
        errors.append(f"{stage}: unexpected fields: " + ", ".join(unexpected_fields))

    expected_fields = {
        "ok": True,
        "adapter_schema_version": "10CJ.1",
        "adapter_type": "runtime_adapter_dry_run_decision",
        "adapter_scope": "dry_run_only",
        "source_consumer_scope": _SOURCE_SCOPE,
        "source_signal_seen": True,
        "planned_action": "log_only",
        "executed": False,
    }
    for field, expected in expected_fields.items():
        value = result.get(field)
        if not _matches_expected(value, expected):
            errors.append(f"{stage}: {field} is not {expected!r}")

    adapter_decision_id = _safe_str(result.get("adapter_decision_id"))
    if adapter_decision_id is None:
        errors.append(f"{stage}: adapter_decision_id is missing or empty")
    elif (
        expected_adapter_decision_id is not None
        and adapter_decision_id != expected_adapter_decision_id
    ):
        errors.append(f"{stage}: adapter_decision_id does not match 10CJ")

    if result.get("source_decision_id") != expected_consumer_decision_id:
        errors.append(f"{stage}: source_decision_id does not match 10BT")

    if result.get("recognized_signal_type") != expected_signal_type:
        errors.append(f"{stage}: recognized_signal_type does not match 10BT")

    for flag in _INTEGRATION_GATE_FLAGS:
        if result.get(flag) is not False:
            errors.append(f"{stage}: {flag} is not False")

    return errors


def _result(
    *,
    errors: list[str],
    source_consumer_decision_id: str | None = None,
    source_adapter_decision_id: str | None = None,
    recognized_signal_type: str | None = None,
    planned_action: str = "none",
    ledger_write_requested: bool = False,
    ledger_write_attempted: bool = False,
    ledger_record_written: bool = False,
    ledger_path_authorized: bool = False,
    ledger_record_hash: str | None = None,
) -> dict[str, Any]:
    ok = not errors and ledger_record_written
    material = {
        "orchestrator_schema_version": _SCHEMA_VERSION,
        "orchestrator_scope": _ORCHESTRATOR_SCOPE,
        "source_consumer_decision_id": source_consumer_decision_id,
        "source_adapter_decision_id": source_adapter_decision_id,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "ledger_write_requested": ledger_write_requested,
        "ledger_write_attempted": ledger_write_attempted,
        "ledger_record_written": ledger_record_written,
        "ledger_path_authorized": ledger_path_authorized,
        "ledger_record_hash": ledger_record_hash,
        "errors": errors,
    }
    orchestrator_decision_id = "10DR-" + _hash_canonical(material)[:32]

    return {
        "ok": ok,
        "orchestrator_schema_version": _SCHEMA_VERSION,
        "orchestrator_type": _ORCHESTRATOR_TYPE,
        "orchestrator_scope": _ORCHESTRATOR_SCOPE,
        "orchestrator_decision_id": orchestrator_decision_id,
        "source_consumer_decision_id": source_consumer_decision_id,
        "source_adapter_decision_id": source_adapter_decision_id,
        "recognized_signal_type": recognized_signal_type,
        "planned_action": planned_action,
        "ledger_write_requested": ledger_write_requested,
        "ledger_write_attempted": ledger_write_attempted,
        "ledger_record_written": ledger_record_written,
        "ledger_path_authorized": ledger_path_authorized,
        "ledger_record_hash": ledger_record_hash if ledger_record_written else None,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }


def run_minimal_inert_ledger_write_orchestration(
    consumer_decision: object,
    *,
    ledger_path: object = None,
    authorized_ledger_path: object = None,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    """Run the bounded 10BT -> 10CJ -> 10DL -> 10CP inert chain."""

    ledger_write_requested = (
        ledger_path is not None and authorized_ledger_path is not None
    )
    source_consumer_decision_id = (
        _safe_str(consumer_decision.get("decision_id"))
        if isinstance(consumer_decision, dict)
        else None
    )
    source_errors = _validate_source_decision(consumer_decision)
    if source_errors:
        return _result(
            errors=source_errors,
            source_consumer_decision_id=source_consumer_decision_id,
            ledger_write_requested=ledger_write_requested,
        )

    source_signal_type = _safe_str(consumer_decision.get("equality_signal_type"))
    if source_signal_type is None:
        return _result(
            errors=["equality_signal_type is missing or invalid"],
            source_consumer_decision_id=source_consumer_decision_id,
            ledger_write_requested=ledger_write_requested,
        )

    try:
        adapter_decision = create_runtime_adapter_dry_run_decision(
            consumer_decision
        )
    except (OSError, TypeError, ValueError, UnicodeError):
        return _result(
            errors=["10CJ processing failed"],
            source_consumer_decision_id=source_consumer_decision_id,
            ledger_write_requested=ledger_write_requested,
        )

    source_adapter_decision_id = (
        _safe_str(adapter_decision.get("adapter_decision_id"))
        if isinstance(adapter_decision, dict)
        else None
    )
    adapter_errors = _validate_10cj_result(
        adapter_decision,
        stage="10CJ",
        expected_consumer_decision_id=source_consumer_decision_id,
        expected_signal_type=source_signal_type,
    )
    if adapter_errors:
        return _result(
            errors=adapter_errors,
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=(
                _safe_str(adapter_decision.get("recognized_signal_type"))
                if isinstance(adapter_decision, dict)
                else None
            ),
            planned_action=(
                adapter_decision.get("planned_action")
                if isinstance(adapter_decision, dict)
                and adapter_decision.get("planned_action") in {"none", "log_only"}
                else "none"
            ),
            ledger_write_requested=ledger_write_requested,
        )

    try:
        integration_result = run_minimal_runtime_adapter_integration(
            adapter_decision
        )
    except (OSError, TypeError, ValueError, UnicodeError):
        return _result(
            errors=["10DL processing failed"],
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=source_signal_type,
            planned_action="log_only",
            ledger_write_requested=ledger_write_requested,
        )

    source_adapter_decision_id = (
        _safe_str(integration_result.get("adapter_decision_id"))
        if isinstance(integration_result, dict)
        else None
    )
    recognized_signal_type = (
        _safe_str(integration_result.get("recognized_signal_type"))
        if isinstance(integration_result, dict)
        else None
    )
    planned_action = (
        integration_result.get("planned_action")
        if isinstance(integration_result, dict)
        and integration_result.get("planned_action") in {"none", "log_only"}
        else "none"
    )
    integration_errors = _validate_10cj_result(
        integration_result,
        stage="10DL",
        expected_consumer_decision_id=source_consumer_decision_id,
        expected_signal_type=source_signal_type,
        expected_adapter_decision_id=_safe_str(
            adapter_decision.get("adapter_decision_id")
        ),
    )
    if integration_errors:
        return _result(
            errors=integration_errors,
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=recognized_signal_type,
            planned_action=planned_action,
            ledger_write_requested=ledger_write_requested,
        )

    if not ledger_write_requested:
        return _result(
            errors=["explicit ledger_path and authorized_ledger_path are required"],
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=recognized_signal_type,
            planned_action=planned_action,
        )

    try:
        writer_result = append_inert_ledger_record(
            integration_result,
            ledger_path,
            authorized_ledger_path,
            recorded_at_utc=recorded_at_utc,
        )
    except (OSError, TypeError, ValueError, UnicodeError):
        return _result(
            errors=["10CP processing failed"],
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=recognized_signal_type,
            planned_action=planned_action,
            ledger_write_requested=True,
            ledger_write_attempted=True,
        )
    if not isinstance(writer_result, dict):
        return _result(
            errors=["10CP result must be a dict"],
            source_consumer_decision_id=source_consumer_decision_id,
            source_adapter_decision_id=source_adapter_decision_id,
            recognized_signal_type=recognized_signal_type,
            planned_action=planned_action,
            ledger_write_requested=True,
            ledger_write_attempted=True,
        )

    ledger_record_written = writer_result.get("ledger_record_written") is True
    ledger_path_authorized = writer_result.get("ledger_path_authorized") is True
    ledger_record_hash = (
        _safe_str(writer_result.get("record_hash"))
        if ledger_record_written
        else None
    )
    writer_errors = _safe_errors(writer_result.get("errors"), "10CP")
    if writer_result.get("ok") is not True or not ledger_record_written:
        if not writer_errors:
            writer_errors.append("10CP rejected the inert ledger write")
    if ledger_record_written and ledger_record_hash is None:
        writer_errors.append("10CP returned a written record without a record hash")

    return _result(
        errors=writer_errors,
        source_consumer_decision_id=source_consumer_decision_id,
        source_adapter_decision_id=source_adapter_decision_id,
        recognized_signal_type=recognized_signal_type,
        planned_action=planned_action,
        ledger_write_requested=True,
        ledger_write_attempted=True,
        ledger_record_written=ledger_record_written,
        ledger_path_authorized=ledger_path_authorized,
        ledger_record_hash=ledger_record_hash,
    )


def export_minimal_inert_ledger_write_result(result: dict) -> str:
    """Export a 10DR orchestration result as deterministic JSON."""

    return json.dumps(result, sort_keys=True, ensure_ascii=False)
