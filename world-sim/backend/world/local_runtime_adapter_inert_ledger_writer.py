"""Phase 10CP - minimal inert ledger adapter writer.

Consumes an already-built 10CJ dry-run adapter decision and appends one
verified NDJSON audit record to an explicitly authorized ledger path.
The writer never imports or calls 10BT or 10CJ creators, never reads the
ledger, never scans directories, and never creates parent directories.

This module records an inert audit artifact only. It does not add
runtime behavior, relocation, map inspection, route execution, event
publication, NPC behavior, background-service work, periodic jobs, or
network activity.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


_WRITER_SCHEMA_VERSION = "10CP.1"
_WRITER_TYPE = "runtime_adapter_inert_ledger_writer_result"
_SOURCE_ADAPTER_SCHEMA_VERSION = "10CJ.1"
_SOURCE_ADAPTER_TYPE = "runtime_adapter_dry_run_decision"
_SOURCE_ADAPTER_SCOPE = "dry_run_only"

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

_GATE_FLAGS = (
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
)

_FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "equality_signal_value",
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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_nonempty_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _result(
    *,
    errors: list[str],
    ledger_path_authorized: bool = False,
    source_adapter_decision_id: str | None = None,
    record_hash: str | None = None,
    bytes_appended: int = 0,
) -> dict[str, Any]:
    written = not errors and bytes_appended > 0
    return {
        "ok": written,
        "writer_schema_version": _WRITER_SCHEMA_VERSION,
        "writer_type": _WRITER_TYPE,
        "ledger_record_written": written,
        "ledger_path_authorized": ledger_path_authorized,
        "source_adapter_decision_id": source_adapter_decision_id,
        "record_hash": record_hash if written else None,
        "bytes_appended": bytes_appended if written else 0,
        "errors": errors,
    }


def _validate_adapter_decision(adapter_decision: dict) -> list[str]:
    errors: list[str] = []

    forbidden = sorted(_FORBIDDEN_INPUT_FIELDS.intersection(adapter_decision))
    if forbidden:
        errors.append("forbidden adapter decision fields: " + ", ".join(forbidden))

    expected_fields = {
        "ok": True,
        "adapter_schema_version": _SOURCE_ADAPTER_SCHEMA_VERSION,
        "adapter_type": _SOURCE_ADAPTER_TYPE,
        "adapter_scope": _SOURCE_ADAPTER_SCOPE,
        "planned_action": "log_only",
        "executed": False,
    }
    for field, expected in expected_fields.items():
        value = adapter_decision.get(field)
        if value is not expected and value != expected:
            errors.append(f"{field} is not {expected!r}")

    if adapter_decision.get("executed") is not False:
        if "executed is not False" not in errors:
            errors.append("executed is not False")

    for flag in _GATE_FLAGS:
        if adapter_decision.get(flag) is not False:
            errors.append(f"{flag} is not False")

    signal_type = adapter_decision.get("recognized_signal_type")
    if signal_type not in _KNOWN_SIGNAL_TYPES:
        errors.append("recognized_signal_type is not a known inert signal type")

    required_strings = (
        "adapter_decision_id",
        "source_decision_id",
        "source_consumer_scope",
    )
    for field in required_strings:
        if _safe_nonempty_str(adapter_decision.get(field)) is None:
            errors.append(f"{field} is missing or empty")

    if adapter_decision.get("source_signal_seen") is not True:
        errors.append("source_signal_seen is not True")

    return errors


def append_inert_ledger_record(
    adapter_decision: dict,
    ledger_path: str | Path,
    authorized_ledger_path: str | Path,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    """Append one inert 10CP record from an accepted 10CJ decision.

    The two paths must resolve to the same exact path and the parent
    directory must already exist. The file is opened once in append
    mode and is never read. Any malformed or rejected input returns a
    fail-closed result without writing.
    """

    if not isinstance(adapter_decision, dict):
        return _result(errors=["adapter_decision must be a dict"])

    source_adapter_decision_id = _safe_nonempty_str(
        adapter_decision.get("adapter_decision_id")
    )
    errors = _validate_adapter_decision(adapter_decision)
    if errors:
        return _result(
            errors=errors,
            source_adapter_decision_id=source_adapter_decision_id,
        )

    try:
        resolved_ledger_path = Path(ledger_path).resolve()
        resolved_authorized_path = Path(authorized_ledger_path).resolve()
    except (OSError, TypeError, ValueError) as exc:
        return _result(
            errors=[f"ledger path resolution failed: {exc}"],
            source_adapter_decision_id=source_adapter_decision_id,
        )

    ledger_path_authorized = resolved_ledger_path == resolved_authorized_path
    if not ledger_path_authorized:
        return _result(
            errors=["ledger path is not the explicitly authorized path"],
            source_adapter_decision_id=source_adapter_decision_id,
        )

    if not resolved_ledger_path.parent.is_dir():
        return _result(
            errors=["ledger parent directory does not exist"],
            ledger_path_authorized=True,
            source_adapter_decision_id=source_adapter_decision_id,
        )

    if recorded_at_utc is None:
        recorded_at_utc = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    if _safe_nonempty_str(recorded_at_utc) is None:
        return _result(
            errors=["recorded_at_utc must be a non-empty string or None"],
            ledger_path_authorized=True,
            source_adapter_decision_id=source_adapter_decision_id,
        )

    record: dict[str, Any] = {
        "ledger_schema_version": _WRITER_SCHEMA_VERSION,
        "source_adapter_schema_version": adapter_decision.get(
            "adapter_schema_version"
        ),
        "adapter_decision_id": source_adapter_decision_id,
        "source_decision_id": adapter_decision.get("source_decision_id"),
        "source_consumer_scope": adapter_decision.get("source_consumer_scope"),
        "source_signal_seen": adapter_decision.get("source_signal_seen"),
        "recognized_signal_type": adapter_decision.get("recognized_signal_type"),
        "planned_action": adapter_decision.get("planned_action"),
        "recorded_at_utc": recorded_at_utc,
    }
    record_hash = _hash_canonical(record)
    record["record_hash"] = record_hash
    line = _canonical_json(record) + "\n"

    try:
        with resolved_ledger_path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as ledger:
            ledger.write(line)
    except (OSError, UnicodeError) as exc:
        return _result(
            errors=[f"ledger append failed: {exc}"],
            ledger_path_authorized=True,
            source_adapter_decision_id=source_adapter_decision_id,
        )

    bytes_appended = len(line.encode("utf-8"))
    return _result(
        errors=[],
        ledger_path_authorized=True,
        source_adapter_decision_id=source_adapter_decision_id,
        record_hash=record_hash,
        bytes_appended=bytes_appended,
    )
