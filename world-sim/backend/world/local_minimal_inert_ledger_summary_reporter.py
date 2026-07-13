"""Phase 10ED - minimal inert ledger summary reporter.

Consumes one caller-supplied 10DX result and returns safe aggregate status.
This module is in-process and caller-driven. It performs no ledger access,
mutation, scanning, verification call, runtime action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10ED.1"
_REPORTER_TYPE = "minimal_inert_ledger_summary_report"
_REPORTER_SCOPE = "inert_ledger_summary_only"
_SOURCE_SCHEMA_VERSION = "10DX.1"
_SOURCE_TYPE = "minimal_inert_ledger_readback_result"
_SOURCE_SCOPE = "inert_ledger_readback_only"

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

_SOURCE_FIELDS = frozenset(
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

_OUTPUT_FIELDS = frozenset(
    {
        "ok",
        "reporter_schema_version",
        "reporter_type",
        "reporter_scope",
        "reporter_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_types_seen",
        "recognized_signal_type_count",
        "append_only_line_format_valid",
        "source_error_count",
        "summary_status",
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

_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_SOURCE_CLAIM_BOUNDARY = (
    "read-only inert ledger verification only; no write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, "
    "map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "aggregate 10DX result summary only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_INVALID_SOURCE_ERROR = "verification_result is not a valid 10DX result"
_SOURCE_FAILED_ERROR = "source 10DX verification did not pass"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_source_decision_id(value: object) -> bool:
    return (
        type(value) is str
        and value.startswith("10DX-")
        and _is_lower_hex(value[5:], 32)
    )


def _is_utf8_string(value: object) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _validated_source_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _SOURCE_FIELDS:
        return None
    for field in (
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "claim_boundary",
    ):
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["verifier_schema_version"] != _SOURCE_SCHEMA_VERSION
        or snapshot["verifier_type"] != _SOURCE_TYPE
        or snapshot["verifier_scope"] != _SOURCE_SCOPE
        or snapshot["claim_boundary"] != _SOURCE_CLAIM_BOUNDARY
        or not _is_source_decision_id(snapshot["verifier_decision_id"])
    ):
        return None

    for field in (
        "ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ):
        if type(snapshot.get(field)) is not bool:
            return None
    for field in _GATE_FLAGS:
        if snapshot.get(field) is not False:
            return None
    for field in ("records_seen", "records_valid", "invalid_record_count"):
        if not _is_nonnegative_int(snapshot.get(field)):
            return None

    verified_hashes = snapshot.get("verified_record_hashes")
    if type(verified_hashes) is not list:
        return None
    verified_hashes = list(verified_hashes)
    snapshot["verified_record_hashes"] = verified_hashes
    if any(
        not _is_lower_hex(record_hash, 64) for record_hash in verified_hashes
    ):
        return None

    signal_types = snapshot.get("recognized_signal_types_seen")
    if type(signal_types) is not list:
        return None
    signal_types = list(signal_types)
    snapshot["recognized_signal_types_seen"] = signal_types
    if (
        any(
            type(signal_type) is not str or signal_type not in _KNOWN_SIGNAL_TYPES
            for signal_type in signal_types
        )
        or signal_types != sorted(set(signal_types))
    ):
        return None

    source_errors = snapshot.get("errors")
    if type(source_errors) is not list:
        return None
    source_errors = list(source_errors)
    snapshot["errors"] = source_errors
    if any(not _is_utf8_string(error) for error in source_errors):
        return None

    records_seen = snapshot["records_seen"]
    records_valid = snapshot["records_valid"]
    invalid_record_count = snapshot["invalid_record_count"]
    if (
        records_valid + invalid_record_count != records_seen
        or len(verified_hashes) != records_valid
        or (snapshot["ledger_file_seen"] and not snapshot["ledger_path_supplied"])
        or (records_seen > 0 and not snapshot["ledger_file_seen"])
        or (
            snapshot["append_only_line_format_valid"]
            and not snapshot["ledger_file_seen"]
        )
        or (records_valid == 0 and bool(signal_types))
        or (
            records_valid > 0
            and (not signal_types or len(signal_types) > records_valid)
        )
    ):
        return None

    expected_ok = (
        not source_errors
        and snapshot["ledger_file_seen"]
        and records_seen > 0
        and records_valid == records_seen
        and invalid_record_count == 0
        and snapshot["append_only_line_format_valid"]
    )
    if snapshot["ok"] is not expected_ok:
        return None
    return snapshot


def _report(
    *,
    source_verifier_schema_version: str = "",
    source_verifier_decision_id: str = "",
    source_ok: bool = False,
    ledger_path_supplied: bool = False,
    ledger_file_seen: bool = False,
    records_seen: int = 0,
    records_valid: int = 0,
    invalid_record_count: int = 0,
    verified_record_hash_count: int = 0,
    recognized_signal_types_seen: list[str] | None = None,
    append_only_line_format_valid: bool = False,
    source_error_count: int = 0,
    summary_status: str = "invalid_source",
    errors: list[str] | None = None,
) -> dict[str, Any]:
    safe_signal_types = list(recognized_signal_types_seen or [])
    safe_errors = list(errors or [])
    ok = summary_status == "verified" and source_ok and not safe_errors
    decision_material = {
        "reporter_schema_version": _SCHEMA_VERSION,
        "reporter_scope": _REPORTER_SCOPE,
        "source_verifier_schema_version": source_verifier_schema_version,
        "source_verifier_decision_id": source_verifier_decision_id,
        "source_ok": source_ok,
        "ledger_path_supplied": ledger_path_supplied,
        "ledger_file_seen": ledger_file_seen,
        "records_seen": records_seen,
        "records_valid": records_valid,
        "invalid_record_count": invalid_record_count,
        "verified_record_hash_count": verified_record_hash_count,
        "recognized_signal_types_seen": safe_signal_types,
        "recognized_signal_type_count": len(safe_signal_types),
        "append_only_line_format_valid": append_only_line_format_valid,
        "source_error_count": source_error_count,
        "summary_status": summary_status,
        "errors": safe_errors,
    }
    reporter_decision_id = "10ED-" + _hash_canonical(decision_material)[:32]

    return {
        "ok": ok,
        "reporter_schema_version": _SCHEMA_VERSION,
        "reporter_type": _REPORTER_TYPE,
        "reporter_scope": _REPORTER_SCOPE,
        "reporter_decision_id": reporter_decision_id,
        "source_verifier_schema_version": source_verifier_schema_version,
        "source_verifier_decision_id": source_verifier_decision_id,
        "source_ok": source_ok,
        "ledger_path_supplied": ledger_path_supplied,
        "ledger_file_seen": ledger_file_seen,
        "records_seen": records_seen,
        "records_valid": records_valid,
        "invalid_record_count": invalid_record_count,
        "verified_record_hash_count": verified_record_hash_count,
        "recognized_signal_types_seen": safe_signal_types,
        "recognized_signal_type_count": len(safe_signal_types),
        "append_only_line_format_valid": append_only_line_format_valid,
        "source_error_count": source_error_count,
        "summary_status": summary_status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": safe_errors,
    }


def create_minimal_inert_ledger_summary_report(
    verification_result: dict | None,
) -> dict[str, Any]:
    """Summarize one caller-supplied 10DX result without ledger access."""

    try:
        source = _validated_source_snapshot(verification_result)
    except Exception:
        source = None
    if source is None:
        return _report(errors=[_INVALID_SOURCE_ERROR])

    source_ok = source["ok"]
    return _report(
        source_verifier_schema_version=source["verifier_schema_version"],
        source_verifier_decision_id=source["verifier_decision_id"],
        source_ok=source_ok,
        ledger_path_supplied=source["ledger_path_supplied"],
        ledger_file_seen=source["ledger_file_seen"],
        records_seen=source["records_seen"],
        records_valid=source["records_valid"],
        invalid_record_count=source["invalid_record_count"],
        verified_record_hash_count=len(source["verified_record_hashes"]),
        recognized_signal_types_seen=source["recognized_signal_types_seen"],
        append_only_line_format_valid=source["append_only_line_format_valid"],
        source_error_count=len(source["errors"]),
        summary_status="verified" if source_ok else "verification_failed",
        errors=[] if source_ok else [_SOURCE_FAILED_ERROR],
    )


def export_minimal_inert_ledger_summary_report(report: dict) -> str:
    """Export one validated 10ED report as deterministic JSON."""

    if type(report) is not dict or any(type(key) is not str for key in report):
        raise ValueError("report must have the exact 10ED report shape")
    report = dict(report)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError("report must have the exact 10ED report shape")
    for field in (
        "reporter_schema_version",
        "reporter_type",
        "reporter_scope",
        "reporter_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "summary_status",
        "claim_boundary",
    ):
        if type(report.get(field)) is not str:
            raise ValueError("report must have the exact 10ED report shape")
    if (
        report.get("reporter_schema_version") != _SCHEMA_VERSION
        or report.get("reporter_type") != _REPORTER_TYPE
        or report.get("reporter_scope") != _REPORTER_SCOPE
        or report.get("claim_boundary") != _CLAIM_BOUNDARY
    ):
        raise ValueError("report must have the exact 10ED report shape")
    for field in (
        "ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ):
        if type(report.get(field)) is not bool:
            raise ValueError("report must have the exact 10ED report shape")
    for field in _GATE_FLAGS:
        if report.get(field) is not False:
            raise ValueError("report must have the exact 10ED report shape")
    for field in (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ):
        if not _is_nonnegative_int(report.get(field)):
            raise ValueError("report must have the exact 10ED report shape")

    signal_types = report.get("recognized_signal_types_seen")
    if type(signal_types) is not list:
        raise ValueError("report must have the exact 10ED report shape")
    signal_types = list(signal_types)
    report["recognized_signal_types_seen"] = signal_types
    if (
        any(
            type(signal_type) is not str or signal_type not in _KNOWN_SIGNAL_TYPES
            for signal_type in signal_types
        )
        or signal_types != sorted(set(signal_types))
        or report["recognized_signal_type_count"] != len(signal_types)
    ):
        raise ValueError("report must have the exact 10ED report shape")

    report_errors = report.get("errors")
    if type(report_errors) is not list:
        raise ValueError("report must have the exact 10ED report shape")
    report_errors = list(report_errors)
    report["errors"] = report_errors
    if any(type(error) is not str for error in report_errors):
        raise ValueError("report must have the exact 10ED report shape")

    summary_status = report.get("summary_status")
    expected_errors: list[str]
    if summary_status == "invalid_source":
        expected_errors = [_INVALID_SOURCE_ERROR]
        if any(
            (
                report["source_verifier_schema_version"] != "",
                report["source_verifier_decision_id"] != "",
                report["source_ok"] is not False,
                report["ledger_path_supplied"] is not False,
                report["ledger_file_seen"] is not False,
                report["records_seen"] != 0,
                report["records_valid"] != 0,
                report["invalid_record_count"] != 0,
                report["verified_record_hash_count"] != 0,
                bool(signal_types),
                report["append_only_line_format_valid"] is not False,
                report["source_error_count"] != 0,
            )
        ):
            raise ValueError("report must have the exact 10ED report shape")
    elif summary_status in {"verified", "verification_failed"}:
        if (
            report["source_verifier_schema_version"] != _SOURCE_SCHEMA_VERSION
            or not _is_source_decision_id(report["source_verifier_decision_id"])
            or report["records_valid"] + report["invalid_record_count"]
            != report["records_seen"]
            or report["verified_record_hash_count"] != report["records_valid"]
            or (
                report["ledger_file_seen"]
                and not report["ledger_path_supplied"]
            )
            or (report["records_seen"] > 0 and not report["ledger_file_seen"])
            or (
                report["append_only_line_format_valid"]
                and not report["ledger_file_seen"]
            )
            or (report["records_valid"] == 0 and bool(signal_types))
            or (
                report["records_valid"] > 0
                and (
                    not signal_types
                    or len(signal_types) > report["records_valid"]
                )
            )
        ):
            raise ValueError("report must have the exact 10ED report shape")
        expected_source_ok = (
            report["source_error_count"] == 0
            and report["ledger_file_seen"]
            and report["records_seen"] > 0
            and report["records_valid"] == report["records_seen"]
            and report["invalid_record_count"] == 0
            and report["append_only_line_format_valid"]
        )
        if report["source_ok"] is not expected_source_ok:
            raise ValueError("report must have the exact 10ED report shape")
        if summary_status == "verified":
            expected_errors = []
            if report["source_ok"] is not True:
                raise ValueError("report must have the exact 10ED report shape")
        else:
            expected_errors = [_SOURCE_FAILED_ERROR]
            if report["source_ok"] is not False:
                raise ValueError("report must have the exact 10ED report shape")
    else:
        raise ValueError("report must have the exact 10ED report shape")

    if report_errors != expected_errors:
        raise ValueError("report must have the exact 10ED report shape")
    expected_ok = summary_status == "verified" and report["source_ok"]
    if report["ok"] is not expected_ok:
        raise ValueError("report must have the exact 10ED report shape")

    decision_material = {
        "reporter_schema_version": _SCHEMA_VERSION,
        "reporter_scope": _REPORTER_SCOPE,
        "source_verifier_schema_version": report[
            "source_verifier_schema_version"
        ],
        "source_verifier_decision_id": report["source_verifier_decision_id"],
        "source_ok": report["source_ok"],
        "ledger_path_supplied": report["ledger_path_supplied"],
        "ledger_file_seen": report["ledger_file_seen"],
        "records_seen": report["records_seen"],
        "records_valid": report["records_valid"],
        "invalid_record_count": report["invalid_record_count"],
        "verified_record_hash_count": report["verified_record_hash_count"],
        "recognized_signal_types_seen": signal_types,
        "recognized_signal_type_count": report["recognized_signal_type_count"],
        "append_only_line_format_valid": report[
            "append_only_line_format_valid"
        ],
        "source_error_count": report["source_error_count"],
        "summary_status": summary_status,
        "errors": expected_errors,
    }
    expected_decision_id = "10ED-" + _hash_canonical(decision_material)[:32]
    if report.get("reporter_decision_id") != expected_decision_id:
        raise ValueError("report must have the exact 10ED report shape")

    return json.dumps(report, sort_keys=True, ensure_ascii=False)
