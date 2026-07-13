"""Phase 10EV - minimal inert ledger status digest verifier.

Consumes one caller-supplied 10EP dictionary and returns a safe aggregate
integrity result. This module performs no source calls, file access, mutation,
scanning, runtime action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10EV.1"
_VERIFIER_TYPE = "minimal_inert_ledger_status_digest_verifier"
_VERIFIER_SCOPE = "inert_ledger_status_digest_verification_only"
_DIGEST_SCHEMA_VERSION = "10EP.1"
_DIGEST_TYPE = "minimal_inert_ledger_status_digest_report"
_DIGEST_SCOPE = "inert_ledger_status_digest_only"
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

_DIGEST_FIELDS = frozenset(
    {
        "ok",
        "digest_schema_version",
        "digest_type",
        "digest_scope",
        "digest_decision_id",
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
        "digest_status",
        "digest_text",
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

_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_DIGEST_CLAIM_BOUNDARY = (
    "aggregate 10EJ status digest only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "verify one 10EP status digest only; no ledger access, digest text, raw "
    "hashes, raw source errors, write, repair, runtime action, daemon, "
    "scheduler, network, world-data promotion, movement, map lookup, route "
    "execution, event emission, NPC behavior, co-presence, awareness, "
    "relationship, interaction, or timing"
)

_INVALID_DIGEST_ERROR = "digest_report is not a valid 10EP digest"
_INVALID_10EJ_ERROR = "bundle_report is not a valid 10EJ bundle"
_NON_VERIFIED_ERROR = "source 10EJ bundle did not report verified"

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


def _format_digest_text(value: dict[str, Any]) -> str:
    signal_types = ",".join(value["recognized_signal_types_seen"]) or "none"
    source_ok = "true" if value["source_ok"] else "false"
    line_format = (
        "true" if value["append_only_line_format_valid"] else "false"
    )
    return (
        "10EP status digest"
        f" | source_bundle={value['source_bundle_decision_id']}"
        f" | status={value['source_bundle_status']}"
        f" | ok={source_ok}"
        f" | source_summary_status={value['source_summary_status']}"
        f" | records_seen={value['records_seen']}"
        f" | records_valid={value['records_valid']}"
        f" | invalid_record_count={value['invalid_record_count']}"
        " | verified_record_hash_count="
        f"{value['verified_record_hash_count']}"
        " | recognized_signal_type_count="
        f"{value['recognized_signal_type_count']}"
        f" | recognized_signal_types={signal_types}"
        f" | append_only_line_format_valid={line_format}"
        f" | source_error_count={value['source_error_count']}"
        " | gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def _digest_decision_material(digest: dict[str, Any]) -> dict[str, Any]:
    return {
        "digest_schema_version": digest["digest_schema_version"],
        "digest_scope": digest["digest_scope"],
        "source_bundle_schema_version": digest[
            "source_bundle_schema_version"
        ],
        "source_bundle_decision_id": digest["source_bundle_decision_id"],
        "source_bundle_status": digest["source_bundle_status"],
        "source_ok": digest["source_ok"],
        "source_summary_status": digest["source_summary_status"],
        "ledger_path_supplied": digest["ledger_path_supplied"],
        "ledger_file_seen": digest["ledger_file_seen"],
        "records_seen": digest["records_seen"],
        "records_valid": digest["records_valid"],
        "invalid_record_count": digest["invalid_record_count"],
        "verified_record_hash_count": digest["verified_record_hash_count"],
        "recognized_signal_types_seen": digest[
            "recognized_signal_types_seen"
        ],
        "recognized_signal_type_count": digest[
            "recognized_signal_type_count"
        ],
        "append_only_line_format_valid": digest[
            "append_only_line_format_valid"
        ],
        "source_error_count": digest["source_error_count"],
        "digest_status": digest["digest_status"],
        "digest_text": digest["digest_text"],
        "errors": digest["errors"],
    }


def _validated_digest_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _DIGEST_FIELDS:
        return None

    for field in (
        "digest_schema_version",
        "digest_type",
        "digest_scope",
        "digest_decision_id",
        "source_bundle_schema_version",
        "source_bundle_decision_id",
        "source_bundle_status",
        "source_summary_status",
        "digest_status",
        "digest_text",
        "claim_boundary",
    ):
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["digest_schema_version"] != _DIGEST_SCHEMA_VERSION
        or snapshot["digest_type"] != _DIGEST_TYPE
        or snapshot["digest_scope"] != _DIGEST_SCOPE
        or snapshot["claim_boundary"] != _DIGEST_CLAIM_BOUNDARY
        or not _is_decision_id(snapshot["digest_decision_id"], "10EP-")
    ):
        return None

    for field in (
        "ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
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

    digest_errors = snapshot.get("errors")
    if type(digest_errors) is not list:
        return None
    digest_errors = list(digest_errors)
    snapshot["errors"] = digest_errors
    if any(type(error) is not str for error in digest_errors):
        return None

    status = snapshot["digest_status"]
    if status == "invalid_10ej_source":
        expected_errors = [_INVALID_10EJ_ERROR]
        if any(
            (
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
    elif status in {"verified_digest", "non_verified_digest"}:
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
                or snapshot["source_summary_status"] != "verification_failed"
            ):
                return None

        if status == "verified_digest":
            expected_errors = []
            if source_status != "verified_bundle":
                return None
        else:
            expected_errors = [_NON_VERIFIED_ERROR]
            if source_status == "verified_bundle":
                return None
    else:
        return None

    if digest_errors != expected_errors:
        return None
    expected_ok = status == "verified_digest" and snapshot["source_ok"]
    if snapshot["ok"] is not expected_ok:
        return None
    if snapshot["digest_text"] != _format_digest_text(snapshot):
        return None

    expected_decision_id = "10EP-" + _hash_canonical(
        _digest_decision_material(snapshot)
    )[:32]
    if snapshot["digest_decision_id"] != expected_decision_id:
        return None
    return snapshot


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


def _verification(
    *,
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
    digest_text_valid: bool = False,
    verification_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_signal_types = list(recognized_signal_types_seen or [])
    safe_errors = list(errors)
    result = {
        "ok": verification_status == "digest_intact",
        "verifier_schema_version": _SCHEMA_VERSION,
        "verifier_type": _VERIFIER_TYPE,
        "verifier_scope": _VERIFIER_SCOPE,
        "verifier_decision_id": "",
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
        "digest_text_valid": digest_text_valid,
        "verification_status": verification_status,
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
    result["verifier_decision_id"] = "10EV-" + _hash_canonical(
        _verification_decision_material(result)
    )[:32]
    return result


def verify_minimal_inert_ledger_status_digest_report(
    digest_report: dict | None,
) -> dict[str, Any]:
    """Verify one safe caller-supplied 10EP digest dictionary."""

    try:
        digest = _validated_digest_snapshot(digest_report)
    except Exception:
        digest = None
    if digest is None:
        return _verification(
            verification_status="invalid_digest",
            errors=[_INVALID_DIGEST_ERROR],
        )

    return _verification(
        source_digest_schema_version=digest["digest_schema_version"],
        source_digest_decision_id=digest["digest_decision_id"],
        source_digest_status=digest["digest_status"],
        source_digest_ok=digest["ok"],
        source_bundle_schema_version=digest["source_bundle_schema_version"],
        source_bundle_decision_id=digest["source_bundle_decision_id"],
        source_bundle_status=digest["source_bundle_status"],
        source_ok=digest["source_ok"],
        source_summary_status=digest["source_summary_status"],
        ledger_path_supplied=digest["ledger_path_supplied"],
        ledger_file_seen=digest["ledger_file_seen"],
        records_seen=digest["records_seen"],
        records_valid=digest["records_valid"],
        invalid_record_count=digest["invalid_record_count"],
        verified_record_hash_count=digest["verified_record_hash_count"],
        recognized_signal_types_seen=digest["recognized_signal_types_seen"],
        append_only_line_format_valid=digest[
            "append_only_line_format_valid"
        ],
        source_error_count=digest["source_error_count"],
        digest_text_valid=True,
        verification_status="digest_intact",
        errors=[],
    )


def export_minimal_inert_ledger_status_digest_verification_report(
    verification_report: dict,
) -> str:
    """Export one validated 10EV verification report as deterministic JSON."""

    error = "verification report must have the exact 10EV verification shape"
    if type(verification_report) is not dict or any(
        type(key) is not str for key in verification_report
    ):
        raise ValueError(error)
    report = dict(verification_report)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError(error)

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
        if type(report.get(field)) is not str:
            raise ValueError(error)
    if (
        report["verifier_schema_version"] != _SCHEMA_VERSION
        or report["verifier_type"] != _VERIFIER_TYPE
        or report["verifier_scope"] != _VERIFIER_SCOPE
        or report["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(report["verifier_decision_id"], "10EV-")
    ):
        raise ValueError(error)

    for field in (
        "ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "digest_text_valid",
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

    status = report["verification_status"]
    if status == "invalid_digest":
        expected_errors = [_INVALID_DIGEST_ERROR]
        if any(
            (
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
                report["digest_text_valid"] is not False,
            )
        ):
            raise ValueError(error)
    elif status == "digest_intact":
        expected_errors = []
        digest_status = report["source_digest_status"]
        if (
            report["source_digest_schema_version"] != _DIGEST_SCHEMA_VERSION
            or not _is_decision_id(
                report["source_digest_decision_id"], "10EP-"
            )
            or digest_status
            not in {
                "verified_digest",
                "non_verified_digest",
                "invalid_10ej_source",
            }
            or report["digest_text_valid"] is not True
        ):
            raise ValueError(error)

        if digest_status == "invalid_10ej_source":
            if any(
                (
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
                )
            ):
                raise ValueError(error)
        else:
            source_status = report["source_bundle_status"]
            if (
                report["source_bundle_schema_version"]
                != _BUNDLE_SCHEMA_VERSION
                or not _is_decision_id(
                    report["source_bundle_decision_id"], "10EJ-"
                )
                or source_status
                not in {
                    "verified_bundle",
                    "verification_failed_bundle",
                    *_INVALID_BUNDLE_STATUSES,
                }
            ):
                raise ValueError(error)

            if source_status in _INVALID_BUNDLE_STATUSES:
                if any(
                    (
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
                    )
                ):
                    raise ValueError(error)
            else:
                if (
                    not _valid_common_aggregate(report)
                    or report["verified_record_hash_count"]
                    != report["records_valid"]
                ):
                    raise ValueError(error)
                expected_source_ok = (
                    report["source_error_count"] == 0
                    and report["ledger_file_seen"]
                    and report["records_seen"] > 0
                    and report["records_valid"] == report["records_seen"]
                    and report["invalid_record_count"] == 0
                    and report["append_only_line_format_valid"]
                )
                if report["source_ok"] is not expected_source_ok:
                    raise ValueError(error)
                if source_status == "verified_bundle":
                    if (
                        report["source_ok"] is not True
                        or report["source_summary_status"] != "verified"
                    ):
                        raise ValueError(error)
                elif (
                    report["source_ok"] is not False
                    or report["source_summary_status"]
                    != "verification_failed"
                ):
                    raise ValueError(error)

            expected_source_digest_ok = digest_status == "verified_digest"
            if report["source_digest_ok"] is not expected_source_digest_ok:
                raise ValueError(error)
            if digest_status == "verified_digest":
                if source_status != "verified_bundle":
                    raise ValueError(error)
            elif source_status == "verified_bundle":
                raise ValueError(error)
    else:
        raise ValueError(error)

    if report_errors != expected_errors:
        raise ValueError(error)
    expected_ok = status == "digest_intact"
    if report["ok"] is not expected_ok:
        raise ValueError(error)

    expected_decision_id = "10EV-" + _hash_canonical(
        _verification_decision_material(report)
    )[:32]
    if report["verifier_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
