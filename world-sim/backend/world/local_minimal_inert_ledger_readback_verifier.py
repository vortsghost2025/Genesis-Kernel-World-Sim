"""Phase 10DX - minimal inert ledger read-back verifier.

Reads one caller-supplied NDJSON ledger file and verifies existing 10CP inert
records. This module is caller-driven and read-only: it has no default path,
does not scan directories, does not call the 10CP writer, and never promotes
ledger contents into runtime or world state.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


_SCHEMA_VERSION = "10DX.1"
_VERIFIER_TYPE = "minimal_inert_ledger_readback_result"
_VERIFIER_SCOPE = "inert_ledger_readback_only"
_LEDGER_SCHEMA_VERSION = "10CP.1"
_SOURCE_ADAPTER_SCHEMA_VERSION = "10CJ.1"
_SOURCE_CONSUMER_SCOPE = "record_public_equality_signal_only"

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

_RECORD_FIELDS = frozenset(
    {
        "ledger_schema_version",
        "source_adapter_schema_version",
        "adapter_decision_id",
        "source_decision_id",
        "source_consumer_scope",
        "source_signal_seen",
        "recognized_signal_type",
        "planned_action",
        "recorded_at_utc",
        "record_hash",
    }
)

_FORBIDDEN_RECORD_FIELDS = frozenset(
    {
        "equality_signal_value",
        "equality_signal_type",
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

_OUTPUT_FIELDS = frozenset(
    {
        "ok",
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "ledger_path_supplied",
        "ledger_file_seen",
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hashes",
        "recognized_signal_types_seen",
        "append_only_line_format_valid",
        "executed",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
        "claim_boundary",
        "errors",
    }
)

_CLAIM_BOUNDARY = (
    "read-only inert ledger verification only; no write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, "
    "map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, or timing"
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
    if not isinstance(value, str) or not value:
        return None
    try:
        value.encode("utf-8")
    except UnicodeError:
        return None
    return value


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _validate_record(record: object, line_number: int) -> list[str]:
    prefix = f"record {line_number}"
    if not isinstance(record, dict):
        return [f"{prefix} is not a JSON object"]

    errors: list[str] = []
    actual_fields = set(record)
    if _FORBIDDEN_RECORD_FIELDS.intersection(actual_fields):
        return [f"{prefix} contains forbidden fields"]
    if actual_fields != _RECORD_FIELDS:
        return [f"{prefix} does not have the exact 10CP record shape"]

    if record.get("ledger_schema_version") != _LEDGER_SCHEMA_VERSION:
        errors.append(f"{prefix} has an invalid ledger schema version")
    if record.get("source_adapter_schema_version") != _SOURCE_ADAPTER_SCHEMA_VERSION:
        errors.append(f"{prefix} has an invalid source adapter schema version")
    if record.get("source_consumer_scope") != _SOURCE_CONSUMER_SCOPE:
        errors.append(f"{prefix} has an invalid source consumer scope")
    if record.get("source_signal_seen") is not True:
        errors.append(f"{prefix} source signal flag is not strictly True")
    signal_type = _safe_nonempty_str(record.get("recognized_signal_type"))
    if signal_type not in _KNOWN_SIGNAL_TYPES:
        errors.append(f"{prefix} has an unknown inert signal type")
    if record.get("planned_action") != "log_only":
        errors.append(f"{prefix} planned action is not log_only")

    for field in (
        "adapter_decision_id",
        "source_decision_id",
        "recorded_at_utc",
        "record_hash",
    ):
        if _safe_nonempty_str(record.get(field)) is None:
            errors.append(f"{prefix} has an invalid required string")

    if errors:
        return errors

    record_hash = record.get("record_hash")
    if isinstance(record_hash, str):
        hash_material = {
            key: value for key, value in record.items() if key != "record_hash"
        }
        try:
            expected_hash = _hash_canonical(hash_material)
        except (TypeError, ValueError, UnicodeError):
            errors.append(f"{prefix} cannot be canonically hashed")
        else:
            if record_hash != expected_hash:
                errors.append(f"{prefix} record hash does not match")

    return errors


def _result(
    *,
    errors: list[str],
    ledger_path_supplied: bool,
    ledger_file_seen: bool = False,
    records_seen: int = 0,
    records_valid: int = 0,
    invalid_record_count: int = 0,
    verified_record_hashes: list[str] | None = None,
    recognized_signal_types_seen: list[str] | None = None,
    append_only_line_format_valid: bool = False,
) -> dict[str, Any]:
    verified_hashes = list(verified_record_hashes or [])
    signal_types = sorted(set(recognized_signal_types_seen or []))
    ok = (
        not errors
        and ledger_file_seen
        and records_seen > 0
        and records_valid == records_seen
        and invalid_record_count == 0
        and append_only_line_format_valid
    )
    decision_material = {
        "verifier_schema_version": _SCHEMA_VERSION,
        "verifier_scope": _VERIFIER_SCOPE,
        "ledger_path_supplied": ledger_path_supplied,
        "ledger_file_seen": ledger_file_seen,
        "records_seen": records_seen,
        "records_valid": records_valid,
        "invalid_record_count": invalid_record_count,
        "verified_record_hashes": verified_hashes,
        "recognized_signal_types_seen": signal_types,
        "append_only_line_format_valid": append_only_line_format_valid,
        "errors": errors,
    }
    verifier_decision_id = "10DX-" + _hash_canonical(decision_material)[:32]

    return {
        "ok": ok,
        "verifier_schema_version": _SCHEMA_VERSION,
        "verifier_type": _VERIFIER_TYPE,
        "verifier_scope": _VERIFIER_SCOPE,
        "verifier_decision_id": verifier_decision_id,
        "ledger_path_supplied": ledger_path_supplied,
        "ledger_file_seen": ledger_file_seen,
        "records_seen": records_seen,
        "records_valid": records_valid,
        "invalid_record_count": invalid_record_count,
        "verified_record_hashes": verified_hashes,
        "recognized_signal_types_seen": signal_types,
        "append_only_line_format_valid": append_only_line_format_valid,
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


def verify_minimal_inert_ledger_readback(
    ledger_path: object = None,
    *,
    max_records: int | None = None,
) -> dict[str, Any]:
    """Verify one explicit 10CP NDJSON ledger without modifying it."""

    ledger_path_supplied = ledger_path is not None
    if max_records is not None and (
        isinstance(max_records, bool)
        or not isinstance(max_records, int)
        or max_records <= 0
    ):
        return _result(
            errors=["max_records must be a positive integer or None"],
            ledger_path_supplied=ledger_path_supplied,
        )
    if not ledger_path_supplied:
        return _result(
            errors=["an explicit ledger path is required"],
            ledger_path_supplied=False,
        )

    try:
        raw_path = os.fspath(ledger_path)
    except Exception:
        return _result(
            errors=["ledger path inspection failed"],
            ledger_path_supplied=True,
        )
    if not isinstance(raw_path, str):
        return _result(
            errors=["ledger path must resolve to a string"],
            ledger_path_supplied=True,
        )
    if raw_path.startswith(("\\\\", "//")):
        return _result(
            errors=["network ledger paths are not allowed"],
            ledger_path_supplied=True,
        )

    try:
        explicit_path = Path(raw_path)
        path_exists = explicit_path.exists()
        path_is_file = explicit_path.is_file() if path_exists else False
    except (OSError, TypeError, ValueError, UnicodeError):
        return _result(
            errors=["ledger path inspection failed"],
            ledger_path_supplied=True,
        )
    if not path_exists:
        return _result(
            errors=["ledger file does not exist"],
            ledger_path_supplied=True,
        )
    if not path_is_file:
        return _result(
            errors=["ledger path is not a file"],
            ledger_path_supplied=True,
        )

    errors: list[str] = []
    records_seen = 0
    records_valid = 0
    invalid_record_count = 0
    verified_record_hashes: list[str] = []
    recognized_signal_types_seen: list[str] = []
    append_only_line_format_valid = True

    try:
        with explicit_path.open("rb") as ledger:
            for line_number, raw_line in enumerate(ledger, start=1):
                records_seen += 1
                if max_records is not None and records_seen > max_records:
                    errors.append("ledger record limit exceeded")
                    invalid_record_count += 1
                    append_only_line_format_valid = False
                    break

                if not raw_line.endswith(b"\n") or raw_line.endswith(b"\r\n"):
                    errors.append(f"record {line_number} is not LF-terminated")
                    invalid_record_count += 1
                    append_only_line_format_valid = False
                    continue

                encoded_record = raw_line[:-1]
                if not encoded_record:
                    errors.append(f"record {line_number} is blank")
                    invalid_record_count += 1
                    append_only_line_format_valid = False
                    continue

                try:
                    decoded_record = encoded_record.decode("utf-8")
                    record = json.loads(
                        decoded_record,
                        object_pairs_hook=_object_without_duplicate_keys,
                    )
                except (
                    UnicodeError,
                    json.JSONDecodeError,
                    ValueError,
                    RecursionError,
                ):
                    errors.append(f"record {line_number} is not valid JSON")
                    invalid_record_count += 1
                    append_only_line_format_valid = False
                    continue

                if not isinstance(record, dict):
                    errors.append(f"record {line_number} is not a JSON object")
                    invalid_record_count += 1
                    append_only_line_format_valid = False
                    continue

                record_errors = _validate_record(record, line_number)
                if record_errors:
                    errors.extend(record_errors)
                    invalid_record_count += 1
                    continue

                records_valid += 1
                verified_record_hashes.append(record["record_hash"])
                recognized_signal_types_seen.append(
                    record["recognized_signal_type"]
                )
    except (OSError, UnicodeError):
        errors.append("ledger read failed")
        append_only_line_format_valid = False

    if records_seen == 0:
        errors.append("ledger file is empty")
        append_only_line_format_valid = False

    return _result(
        errors=errors,
        ledger_path_supplied=True,
        ledger_file_seen=True,
        records_seen=records_seen,
        records_valid=records_valid,
        invalid_record_count=invalid_record_count,
        verified_record_hashes=verified_record_hashes,
        recognized_signal_types_seen=recognized_signal_types_seen,
        append_only_line_format_valid=append_only_line_format_valid,
    )


def export_minimal_inert_ledger_readback_result(result: dict) -> str:
    """Export a 10DX verification result as deterministic JSON."""

    if not isinstance(result, dict) or set(result) != _OUTPUT_FIELDS:
        raise ValueError("result must have the exact 10DX result shape")
    if (
        result.get("verifier_schema_version") != _SCHEMA_VERSION
        or result.get("verifier_type") != _VERIFIER_TYPE
        or result.get("verifier_scope") != _VERIFIER_SCOPE
        or result.get("claim_boundary") != _CLAIM_BOUNDARY
    ):
        raise ValueError("result must have the exact 10DX result shape")
    for field in (
        "executed",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
    ):
        if result.get(field) is not False:
            raise ValueError("result must have the exact 10DX result shape")

    for field in (
        "ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ):
        if not isinstance(result.get(field), bool):
            raise ValueError("result must have the exact 10DX result shape")
    for field in ("records_seen", "records_valid", "invalid_record_count"):
        value = result.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("result must have the exact 10DX result shape")

    verified_hashes = result.get("verified_record_hashes")
    if not isinstance(verified_hashes, list) or any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in verified_hashes
    ):
        raise ValueError("result must have the exact 10DX result shape")
    signal_types = result.get("recognized_signal_types_seen")
    if (
        not isinstance(signal_types, list)
        or any(value not in _KNOWN_SIGNAL_TYPES for value in signal_types)
        or signal_types != sorted(set(signal_types))
    ):
        raise ValueError("result must have the exact 10DX result shape")
    errors = result.get("errors")
    if not isinstance(errors, list) or any(
        _safe_nonempty_str(value) is None for value in errors
    ):
        raise ValueError("result must have the exact 10DX result shape")

    records_seen = result["records_seen"]
    records_valid = result["records_valid"]
    invalid_record_count = result["invalid_record_count"]
    expected_ok = (
        not errors
        and result["ledger_file_seen"]
        and records_seen > 0
        and records_valid == records_seen
        and invalid_record_count == 0
        and result["append_only_line_format_valid"]
    )
    if result["ok"] is not expected_ok or len(verified_hashes) != records_valid:
        raise ValueError("result must have the exact 10DX result shape")

    decision_material = {
        "verifier_schema_version": _SCHEMA_VERSION,
        "verifier_scope": _VERIFIER_SCOPE,
        "ledger_path_supplied": result["ledger_path_supplied"],
        "ledger_file_seen": result["ledger_file_seen"],
        "records_seen": records_seen,
        "records_valid": records_valid,
        "invalid_record_count": invalid_record_count,
        "verified_record_hashes": verified_hashes,
        "recognized_signal_types_seen": signal_types,
        "append_only_line_format_valid": result[
            "append_only_line_format_valid"
        ],
        "errors": errors,
    }
    try:
        expected_decision_id = "10DX-" + _hash_canonical(decision_material)[:32]
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("result must have the exact 10DX result shape") from None
    if result.get("verifier_decision_id") != expected_decision_id:
        raise ValueError("result must have the exact 10DX result shape")

    return json.dumps(result, sort_keys=True, ensure_ascii=False)
