"""Phase 10FB - minimal inert ledger digest verification reporter.

Consumes one caller-supplied 10EV dictionary and returns a safe aggregate
digest report. This module performs no source calls, file access, mutation,
scanning, runtime action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10FB.1"
_REPORT_TYPE = "minimal_inert_ledger_status_digest_verification_report"
_REPORT_SCOPE = "inert_ledger_status_digest_verification_report_only"
_VERIFIER_SCHEMA_VERSION = "10EV.1"
_VERIFIER_TYPE = "minimal_inert_ledger_status_digest_verifier"
_VERIFIER_SCOPE = "inert_ledger_status_digest_verification_only"
_DIGEST_SCHEMA_VERSION = "10EP.1"
_BUNDLE_SCHEMA_VERSION = "10EJ.1"

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

_VERIFICATION_FIELDS = frozenset(
    {
        "ok",
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "source_digest_schema_version",
        "source_digest_decision_id",
        "source_digest_status",
        "source_digest_ok",
        "source_bundle_schema_version",
        "source_bundle_decision_id",
        "source_bundle_status",
        "source_ok",
        "source_summary_status",
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
        "digest_text_valid",
        "verification_status",
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
        "verification_digest_schema_version",
        "verification_digest_type",
        "verification_digest_scope",
        "verification_digest_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "source_verifier_status",
        "source_verifier_ok",
        "source_digest_schema_version",
        "source_digest_decision_id",
        "source_digest_status",
        "source_digest_ok",
        "source_bundle_schema_version",
        "source_bundle_decision_id",
        "source_bundle_status",
        "source_ok",
        "source_summary_status",
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
        "source_digest_text_valid",
        "verification_digest_status",
        "verification_digest_text",
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

_VERIFIER_CLAIM_BOUNDARY = (
    "verify one 10EP status digest only; no ledger access, digest text, raw "
    "hashes, raw source errors, write, repair, runtime action, daemon, "
    "scheduler, network, world-data promotion, movement, map lookup, route "
    "execution, event emission, NPC behavior, co-presence, awareness, "
    "relationship, interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "report one 10EV status digest verification only; no ledger access, "
    "digest text, raw hashes, raw source errors, write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, map "
    "lookup, route execution, event emission, NPC behavior, co-presence, "
    "awareness, relationship, interaction, or timing"
)

_INVALID_SOURCE_ERROR = (
    "verification_report is not a valid 10EV verification report"
)
_NON_VERIFIED_ERROR = "source 10EV verification did not report digest_intact"
_SOURCE_INVALID_DIGEST_ERROR = "digest_report is not a valid 10EP digest"

_INVALID_BUNDLE_STATUSES = frozenset(
    {
        "invalid_10dx_source",
        "invalid_10ed_source",
        "mismatched_sources",
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


def _is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_decision_id(value: object, prefix: str) -> bool:
    return (
        type(value) is str
        and value.startswith(prefix)
        and _is_lower_hex(value[len(prefix) :], 32)
    )


def _valid_common_aggregate(snapshot: dict[str, Any]) -> bool:
    records_seen = snapshot["records_seen"]
    records_valid = snapshot["records_valid"]
    invalid_record_count = snapshot["invalid_record_count"]
    signal_types = snapshot["recognized_signal_types_seen"]
    return not any(
        (
            records_valid + invalid_record_count != records_seen,
            snapshot["ledger_file_seen"] and not snapshot["ledger_path_supplied"],
            records_seen > 0 and not snapshot["ledger_file_seen"],
            snapshot["append_only_line_format_valid"]
            and not snapshot["ledger_file_seen"],
            records_valid == 0 and bool(signal_types),
            records_valid > 0
            and (not signal_types or len(signal_types) > records_valid),
        )
    )


def _verification_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "verifier_schema_version": report["verifier_schema_version"],
        "verifier_scope": report["verifier_scope"],
        "source_digest_schema_version": report[
            "source_digest_schema_version"
        ],
        "source_digest_decision_id": report["source_digest_decision_id"],
        "source_digest_status": report["source_digest_status"],
        "source_digest_ok": report["source_digest_ok"],
        "source_bundle_schema_version": report[
            "source_bundle_schema_version"
        ],
        "source_bundle_decision_id": report["source_bundle_decision_id"],
        "source_bundle_status": report["source_bundle_status"],
        "source_ok": report["source_ok"],
        "source_summary_status": report["source_summary_status"],
        "ledger_path_supplied": report["ledger_path_supplied"],
        "ledger_file_seen": report["ledger_file_seen"],
        "records_seen": report["records_seen"],
        "records_valid": report["records_valid"],
        "invalid_record_count": report["invalid_record_count"],
        "verified_record_hash_count": report[
            "verified_record_hash_count"
        ],
        "recognized_signal_types_seen": report[
            "recognized_signal_types_seen"
        ],
        "recognized_signal_type_count": report[
            "recognized_signal_type_count"
        ],
        "append_only_line_format_valid": report[
            "append_only_line_format_valid"
        ],
        "source_error_count": report["source_error_count"],
        "digest_text_valid": report["digest_text_valid"],
        "verification_status": report["verification_status"],
        "errors": report["errors"],
    }


def _validated_verification_snapshot(
    source: object,
) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _VERIFICATION_FIELDS:
        return None

    for field in (
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "source_digest_schema_version",
        "source_digest_decision_id",
        "source_digest_status",
        "source_bundle_schema_version",
        "source_bundle_decision_id",
        "source_bundle_status",
        "source_summary_status",
        "verification_status",
        "claim_boundary",
    ):
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["verifier_schema_version"] != _VERIFIER_SCHEMA_VERSION
        or snapshot["verifier_type"] != _VERIFIER_TYPE
        or snapshot["verifier_scope"] != _VERIFIER_SCOPE
        or snapshot["claim_boundary"] != _VERIFIER_CLAIM_BOUNDARY
        or not _is_decision_id(snapshot["verifier_decision_id"], "10EV-")
    ):
        return None

    for field in (
        "ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "digest_text_valid",
    ):
        if type(snapshot.get(field)) is not bool:
            return None
    for field in _GATE_FLAGS:
        if snapshot.get(field) is not False:
            return None
    for field in (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ):
        if not _is_nonnegative_int(snapshot.get(field)):
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
        or snapshot["recognized_signal_type_count"] != len(signal_types)
    ):
        return None

    source_errors = snapshot.get("errors")
    if type(source_errors) is not list:
        return None
    source_errors = list(source_errors)
    snapshot["errors"] = source_errors
    if any(type(error) is not str for error in source_errors):
        return None

    status = snapshot["verification_status"]
    if status == "invalid_digest":
        expected_errors = [_SOURCE_INVALID_DIGEST_ERROR]
        if any(
            (
                snapshot["source_digest_schema_version"] != "",
                snapshot["source_digest_decision_id"] != "",
                snapshot["source_digest_status"] != "",
                snapshot["source_digest_ok"] is not False,
                snapshot["source_bundle_schema_version"] != "",
                snapshot["source_bundle_decision_id"] != "",
                snapshot["source_bundle_status"] != "",
                snapshot["source_ok"] is not False,
                snapshot["source_summary_status"] != "",
                snapshot["ledger_path_supplied"] is not False,
                snapshot["ledger_file_seen"] is not False,
                snapshot["records_seen"] != 0,
                snapshot["records_valid"] != 0,
                snapshot["invalid_record_count"] != 0,
                snapshot["verified_record_hash_count"] != 0,
                bool(signal_types),
                snapshot["append_only_line_format_valid"] is not False,
                snapshot["source_error_count"] != 0,
                snapshot["digest_text_valid"] is not False,
            )
        ):
            return None
    elif status == "digest_intact":
        expected_errors = []
        digest_status = snapshot["source_digest_status"]
        if (
            snapshot["source_digest_schema_version"]
            != _DIGEST_SCHEMA_VERSION
            or not _is_decision_id(
                snapshot["source_digest_decision_id"], "10EP-"
            )
            or digest_status
            not in {
                "verified_digest",
                "non_verified_digest",
                "invalid_10ej_source",
            }
            or snapshot["digest_text_valid"] is not True
        ):
            return None

        if digest_status == "invalid_10ej_source":
            if any(
                (
                    snapshot["source_digest_ok"] is not False,
                    snapshot["source_bundle_schema_version"] != "",
                    snapshot["source_bundle_decision_id"] != "",
                    snapshot["source_bundle_status"] != "",
                    snapshot["source_ok"] is not False,
                    snapshot["source_summary_status"] != "",
                    snapshot["ledger_path_supplied"] is not False,
                    snapshot["ledger_file_seen"] is not False,
                    snapshot["records_seen"] != 0,
                    snapshot["records_valid"] != 0,
                    snapshot["invalid_record_count"] != 0,
                    snapshot["verified_record_hash_count"] != 0,
                    bool(signal_types),
                    snapshot["append_only_line_format_valid"] is not False,
                    snapshot["source_error_count"] != 0,
                )
            ):
                return None
        else:
            source_status = snapshot["source_bundle_status"]
            if (
                snapshot["source_bundle_schema_version"]
                != _BUNDLE_SCHEMA_VERSION
                or not _is_decision_id(
                    snapshot["source_bundle_decision_id"], "10EJ-"
                )
                or source_status
                not in {
                    "verified_bundle",
                    "verification_failed_bundle",
                    *_INVALID_BUNDLE_STATUSES,
                }
            ):
                return None

            if source_status in _INVALID_BUNDLE_STATUSES:
                if any(
                    (
                        snapshot["source_ok"] is not False,
                        snapshot["source_summary_status"] != "",
                        snapshot["ledger_path_supplied"] is not False,
                        snapshot["ledger_file_seen"] is not False,
                        snapshot["records_seen"] != 0,
                        snapshot["records_valid"] != 0,
                        snapshot["invalid_record_count"] != 0,
                        snapshot["verified_record_hash_count"] != 0,
                        bool(signal_types),
                        snapshot["append_only_line_format_valid"] is not False,
                        snapshot["source_error_count"] != 0,
                    )
                ):
                    return None
            else:
                if (
                    not _valid_common_aggregate(snapshot)
                    or snapshot["verified_record_hash_count"]
                    != snapshot["records_valid"]
                ):
                    return None
                expected_source_ok = (
                    snapshot["source_error_count"] == 0
                    and snapshot["ledger_file_seen"]
                    and snapshot["records_seen"] > 0
                    and snapshot["records_valid"] == snapshot["records_seen"]
                    and snapshot["invalid_record_count"] == 0
                    and snapshot["append_only_line_format_valid"]
                )
                if snapshot["source_ok"] is not expected_source_ok:
                    return None
                if source_status == "verified_bundle":
                    if (
                        snapshot["source_ok"] is not True
                        or snapshot["source_summary_status"] != "verified"
                    ):
                        return None
                elif (
                    snapshot["source_ok"] is not False
                    or snapshot["source_summary_status"]
                    != "verification_failed"
                ):
                    return None

            expected_source_digest_ok = digest_status == "verified_digest"
            if snapshot["source_digest_ok"] is not expected_source_digest_ok:
                return None
            if digest_status == "verified_digest":
                if source_status != "verified_bundle":
                    return None
            elif source_status == "verified_bundle":
                return None
    else:
        return None

    if source_errors != expected_errors:
        return None
    expected_ok = status == "digest_intact"
    if snapshot["ok"] is not expected_ok:
        return None

    expected_decision_id = "10EV-" + _hash_canonical(
        _verification_decision_material(snapshot)
    )[:32]
    if snapshot["verifier_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _format_verification_digest_text(report: dict[str, Any]) -> str:
    return (
        "10FB verification digest"
        f" | status={report['verification_digest_status']}"
        f" | source_verifier_status={report['source_verifier_status'] or 'none'}"
        f" | source_verifier_ok={_bool_text(report['source_verifier_ok'])}"
        f" | source_digest_status={report['source_digest_status'] or 'none'}"
        f" | source_digest_ok={_bool_text(report['source_digest_ok'])}"
        f" | source_bundle_status={report['source_bundle_status'] or 'none'}"
        f" | source_ok={_bool_text(report['source_ok'])}"
        f" | source_summary_status={report['source_summary_status'] or 'none'}"
        f" | records_seen={report['records_seen']}"
        f" | records_valid={report['records_valid']}"
        f" | invalid_record_count={report['invalid_record_count']}"
        " | verified_record_hash_count="
        f"{report['verified_record_hash_count']}"
        " | recognized_signal_type_count="
        f"{report['recognized_signal_type_count']}"
        " | append_only_line_format_valid="
        f"{_bool_text(report['append_only_line_format_valid'])}"
        f" | source_error_count={report['source_error_count']}"
        " | source_digest_text_valid="
        f"{_bool_text(report['source_digest_text_valid'])}"
        " | gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def _digest_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "verification_digest_schema_version": report[
            "verification_digest_schema_version"
        ],
        "verification_digest_scope": report["verification_digest_scope"],
        "source_verifier_schema_version": report[
            "source_verifier_schema_version"
        ],
        "source_verifier_decision_id": report[
            "source_verifier_decision_id"
        ],
        "source_verifier_status": report["source_verifier_status"],
        "source_verifier_ok": report["source_verifier_ok"],
        "source_digest_schema_version": report[
            "source_digest_schema_version"
        ],
        "source_digest_decision_id": report["source_digest_decision_id"],
        "source_digest_status": report["source_digest_status"],
        "source_digest_ok": report["source_digest_ok"],
        "source_bundle_schema_version": report[
            "source_bundle_schema_version"
        ],
        "source_bundle_decision_id": report["source_bundle_decision_id"],
        "source_bundle_status": report["source_bundle_status"],
        "source_ok": report["source_ok"],
        "source_summary_status": report["source_summary_status"],
        "ledger_path_supplied": report["ledger_path_supplied"],
        "ledger_file_seen": report["ledger_file_seen"],
        "records_seen": report["records_seen"],
        "records_valid": report["records_valid"],
        "invalid_record_count": report["invalid_record_count"],
        "verified_record_hash_count": report[
            "verified_record_hash_count"
        ],
        "recognized_signal_types_seen": report[
            "recognized_signal_types_seen"
        ],
        "recognized_signal_type_count": report[
            "recognized_signal_type_count"
        ],
        "append_only_line_format_valid": report[
            "append_only_line_format_valid"
        ],
        "source_error_count": report["source_error_count"],
        "source_digest_text_valid": report["source_digest_text_valid"],
        "verification_digest_status": report[
            "verification_digest_status"
        ],
        "verification_digest_text": report["verification_digest_text"],
        "errors": report["errors"],
    }


def _digest(
    *,
    source_verifier_schema_version: str = "",
    source_verifier_decision_id: str = "",
    source_verifier_status: str = "",
    source_verifier_ok: bool = False,
    source_digest_schema_version: str = "",
    source_digest_decision_id: str = "",
    source_digest_status: str = "",
    source_digest_ok: bool = False,
    source_bundle_schema_version: str = "",
    source_bundle_decision_id: str = "",
    source_bundle_status: str = "",
    source_ok: bool = False,
    source_summary_status: str = "",
    ledger_path_supplied: bool = False,
    ledger_file_seen: bool = False,
    records_seen: int = 0,
    records_valid: int = 0,
    invalid_record_count: int = 0,
    verified_record_hash_count: int = 0,
    recognized_signal_types_seen: list[str] | None = None,
    append_only_line_format_valid: bool = False,
    source_error_count: int = 0,
    source_digest_text_valid: bool = False,
    verification_digest_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_signal_types = list(recognized_signal_types_seen or [])
    safe_errors = list(errors)
    result = {
        "ok": verification_digest_status == "verified_verification_digest",
        "verification_digest_schema_version": _SCHEMA_VERSION,
        "verification_digest_type": _REPORT_TYPE,
        "verification_digest_scope": _REPORT_SCOPE,
        "verification_digest_decision_id": "",
        "source_verifier_schema_version": source_verifier_schema_version,
        "source_verifier_decision_id": source_verifier_decision_id,
        "source_verifier_status": source_verifier_status,
        "source_verifier_ok": source_verifier_ok,
        "source_digest_schema_version": source_digest_schema_version,
        "source_digest_decision_id": source_digest_decision_id,
        "source_digest_status": source_digest_status,
        "source_digest_ok": source_digest_ok,
        "source_bundle_schema_version": source_bundle_schema_version,
        "source_bundle_decision_id": source_bundle_decision_id,
        "source_bundle_status": source_bundle_status,
        "source_ok": source_ok,
        "source_summary_status": source_summary_status,
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
        "source_digest_text_valid": source_digest_text_valid,
        "verification_digest_status": verification_digest_status,
        "verification_digest_text": "",
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
    result["verification_digest_text"] = _format_verification_digest_text(
        result
    )
    result["verification_digest_decision_id"] = "10FB-" + _hash_canonical(
        _digest_decision_material(result)
    )[:32]
    return result


def create_minimal_inert_ledger_status_digest_verification_report(
    verification_report: dict | None,
) -> dict[str, Any]:
    """Create one safe digest from a caller-supplied 10EV dictionary."""

    try:
        source = _validated_verification_snapshot(verification_report)
    except Exception:
        source = None
    if source is None:
        return _digest(
            verification_digest_status="invalid_10ev_source",
            errors=[_INVALID_SOURCE_ERROR],
        )

    source_status = source["verification_status"]
    if source_status == "digest_intact":
        digest_status = "verified_verification_digest"
        errors: list[str] = []
    else:
        digest_status = "non_verified_verification_digest"
        errors = [_NON_VERIFIED_ERROR]

    return _digest(
        source_verifier_schema_version=source["verifier_schema_version"],
        source_verifier_decision_id=source["verifier_decision_id"],
        source_verifier_status=source_status,
        source_verifier_ok=source["ok"],
        source_digest_schema_version=source["source_digest_schema_version"],
        source_digest_decision_id=source["source_digest_decision_id"],
        source_digest_status=source["source_digest_status"],
        source_digest_ok=source["source_digest_ok"],
        source_bundle_schema_version=source["source_bundle_schema_version"],
        source_bundle_decision_id=source["source_bundle_decision_id"],
        source_bundle_status=source["source_bundle_status"],
        source_ok=source["source_ok"],
        source_summary_status=source["source_summary_status"],
        ledger_path_supplied=source["ledger_path_supplied"],
        ledger_file_seen=source["ledger_file_seen"],
        records_seen=source["records_seen"],
        records_valid=source["records_valid"],
        invalid_record_count=source["invalid_record_count"],
        verified_record_hash_count=source["verified_record_hash_count"],
        recognized_signal_types_seen=source["recognized_signal_types_seen"],
        append_only_line_format_valid=source[
            "append_only_line_format_valid"
        ],
        source_error_count=source["source_error_count"],
        source_digest_text_valid=source["digest_text_valid"],
        verification_digest_status=digest_status,
        errors=errors,
    )


def _source_snapshot_from_digest(report: dict[str, Any]) -> dict[str, Any]:
    source_status = report["source_verifier_status"]
    source_errors = (
        []
        if source_status == "digest_intact"
        else [_SOURCE_INVALID_DIGEST_ERROR]
    )
    return {
        "ok": report["source_verifier_ok"],
        "verifier_schema_version": report["source_verifier_schema_version"],
        "verifier_type": _VERIFIER_TYPE,
        "verifier_scope": _VERIFIER_SCOPE,
        "verifier_decision_id": report["source_verifier_decision_id"],
        "source_digest_schema_version": report[
            "source_digest_schema_version"
        ],
        "source_digest_decision_id": report["source_digest_decision_id"],
        "source_digest_status": report["source_digest_status"],
        "source_digest_ok": report["source_digest_ok"],
        "source_bundle_schema_version": report[
            "source_bundle_schema_version"
        ],
        "source_bundle_decision_id": report["source_bundle_decision_id"],
        "source_bundle_status": report["source_bundle_status"],
        "source_ok": report["source_ok"],
        "source_summary_status": report["source_summary_status"],
        "ledger_path_supplied": report["ledger_path_supplied"],
        "ledger_file_seen": report["ledger_file_seen"],
        "records_seen": report["records_seen"],
        "records_valid": report["records_valid"],
        "invalid_record_count": report["invalid_record_count"],
        "verified_record_hash_count": report[
            "verified_record_hash_count"
        ],
        "recognized_signal_types_seen": report[
            "recognized_signal_types_seen"
        ],
        "recognized_signal_type_count": report[
            "recognized_signal_type_count"
        ],
        "append_only_line_format_valid": report[
            "append_only_line_format_valid"
        ],
        "source_error_count": report["source_error_count"],
        "digest_text_valid": report["source_digest_text_valid"],
        "verification_status": source_status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _VERIFIER_CLAIM_BOUNDARY,
        "errors": source_errors,
    }


def export_minimal_inert_ledger_status_digest_verification_report(
    digest_report: dict,
) -> str:
    """Export one validated 10FB digest report as deterministic JSON."""

    error = "digest report must have the exact 10FB digest shape"
    if type(digest_report) is not dict or any(
        type(key) is not str for key in digest_report
    ):
        raise ValueError(error)
    report = dict(digest_report)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError(error)

    for field in (
        "verification_digest_schema_version",
        "verification_digest_type",
        "verification_digest_scope",
        "verification_digest_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "source_verifier_status",
        "source_digest_schema_version",
        "source_digest_decision_id",
        "source_digest_status",
        "source_bundle_schema_version",
        "source_bundle_decision_id",
        "source_bundle_status",
        "source_summary_status",
        "verification_digest_status",
        "verification_digest_text",
        "claim_boundary",
    ):
        if type(report.get(field)) is not str:
            raise ValueError(error)
    if (
        report["verification_digest_schema_version"] != _SCHEMA_VERSION
        or report["verification_digest_type"] != _REPORT_TYPE
        or report["verification_digest_scope"] != _REPORT_SCOPE
        or report["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(
            report["verification_digest_decision_id"], "10FB-"
        )
    ):
        raise ValueError(error)

    for field in (
        "ok",
        "source_verifier_ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "source_digest_text_valid",
    ):
        if type(report.get(field)) is not bool:
            raise ValueError(error)
    for field in _GATE_FLAGS:
        if report.get(field) is not False:
            raise ValueError(error)
    for field in (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ):
        if not _is_nonnegative_int(report.get(field)):
            raise ValueError(error)

    signal_types = report.get("recognized_signal_types_seen")
    if type(signal_types) is not list:
        raise ValueError(error)
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
        raise ValueError(error)

    report_errors = report.get("errors")
    if type(report_errors) is not list:
        raise ValueError(error)
    report_errors = list(report_errors)
    report["errors"] = report_errors
    if any(type(item) is not str for item in report_errors):
        raise ValueError(error)

    status = report["verification_digest_status"]
    if status == "invalid_10ev_source":
        expected_errors = [_INVALID_SOURCE_ERROR]
        if any(
            (
                report["source_verifier_schema_version"] != "",
                report["source_verifier_decision_id"] != "",
                report["source_verifier_status"] != "",
                report["source_verifier_ok"] is not False,
                report["source_digest_schema_version"] != "",
                report["source_digest_decision_id"] != "",
                report["source_digest_status"] != "",
                report["source_digest_ok"] is not False,
                report["source_bundle_schema_version"] != "",
                report["source_bundle_decision_id"] != "",
                report["source_bundle_status"] != "",
                report["source_ok"] is not False,
                report["source_summary_status"] != "",
                report["ledger_path_supplied"] is not False,
                report["ledger_file_seen"] is not False,
                report["records_seen"] != 0,
                report["records_valid"] != 0,
                report["invalid_record_count"] != 0,
                report["verified_record_hash_count"] != 0,
                bool(signal_types),
                report["append_only_line_format_valid"] is not False,
                report["source_error_count"] != 0,
                report["source_digest_text_valid"] is not False,
            )
        ):
            raise ValueError(error)
    elif status in {
        "verified_verification_digest",
        "non_verified_verification_digest",
    }:
        expected_errors = (
            []
            if status == "verified_verification_digest"
            else [_NON_VERIFIED_ERROR]
        )
        source = _source_snapshot_from_digest(report)
        validated_source = _validated_verification_snapshot(source)
        expected_source_status = (
            "digest_intact"
            if status == "verified_verification_digest"
            else "invalid_digest"
        )
        if (
            validated_source is None
            or report["source_verifier_status"] != expected_source_status
        ):
            raise ValueError(error)
    else:
        raise ValueError(error)

    if report_errors != expected_errors:
        raise ValueError(error)
    expected_ok = status == "verified_verification_digest"
    if report["ok"] is not expected_ok:
        raise ValueError(error)
    if report["verification_digest_text"] != _format_verification_digest_text(
        report
    ):
        raise ValueError(error)

    expected_decision_id = "10FB-" + _hash_canonical(
        _digest_decision_material(report)
    )[:32]
    if report["verification_digest_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
