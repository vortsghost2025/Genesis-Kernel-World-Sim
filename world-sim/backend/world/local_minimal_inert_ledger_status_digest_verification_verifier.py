"""Phase 10FH - minimal inert ledger verification digest verifier.

Consumes one caller-supplied 10FB dictionary and returns a safe aggregate
integrity verification. This module performs no source calls, file access,
mutation, scanning, runtime action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10FH.1"
_VERIFIER_TYPE = "minimal_inert_ledger_status_digest_verification_verifier"
_VERIFIER_SCOPE = (
    "inert_ledger_status_digest_verification_verification_only"
)
_DIGEST_SCHEMA_VERSION = "10FB.1"
_DIGEST_TYPE = "minimal_inert_ledger_status_digest_verification_report"
_DIGEST_SCOPE = "inert_ledger_status_digest_verification_report_only"
_SOURCE_VERIFIER_SCHEMA_VERSION = "10EV.1"
_SOURCE_DIGEST_SCHEMA_VERSION = "10EP.1"
_SOURCE_BUNDLE_SCHEMA_VERSION = "10EJ.1"

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

_OUTPUT_FIELDS = frozenset(
    {
        "ok",
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "source_verification_digest_schema_version",
        "source_verification_digest_decision_id",
        "source_verification_digest_status",
        "source_verification_digest_ok",
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
        "source_verification_digest_text_valid",
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

_REPORTER_CLAIM_BOUNDARY = (
    "report one 10EV status digest verification only; no ledger access, "
    "digest text, raw hashes, raw source errors, write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, map "
    "lookup, route execution, event emission, NPC behavior, co-presence, "
    "awareness, relationship, interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "verify one 10FB status digest verification report only; no ledger "
    "access, verification digest text, digest text, raw hashes, raw source "
    "errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_INVALID_DIGEST_ERROR = (
    "verification_digest_report is not a valid 10FB verification digest report"
)
_SOURCE_INVALID_ERROR = (
    "verification_report is not a valid 10EV verification report"
)
_SOURCE_NON_VERIFIED_ERROR = (
    "source 10EV verification did not report digest_intact"
)

_VALID_DIGEST_STATUSES = frozenset(
    {
        "verified_verification_digest",
        "non_verified_verification_digest",
        "invalid_10ev_source",
    }
)
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


def _source_fields_are_sanitized(snapshot: dict[str, Any]) -> bool:
    return not any(
        (
            snapshot["source_verifier_schema_version"] != "",
            snapshot["source_verifier_decision_id"] != "",
            snapshot["source_verifier_status"] != "",
            snapshot["source_verifier_ok"] is not False,
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
            bool(snapshot["recognized_signal_types_seen"]),
            snapshot["append_only_line_format_valid"] is not False,
            snapshot["source_error_count"] != 0,
            snapshot["source_digest_text_valid"] is not False,
        )
    )


def _valid_source_aggregate(
    snapshot: dict[str, Any],
    verification_digest_status: str,
) -> bool:
    if verification_digest_status == "invalid_10ev_source":
        return _source_fields_are_sanitized(snapshot)

    if (
        snapshot["source_verifier_schema_version"]
        != _SOURCE_VERIFIER_SCHEMA_VERSION
        or not _is_decision_id(
            snapshot["source_verifier_decision_id"], "10EV-"
        )
    ):
        return False

    if verification_digest_status == "non_verified_verification_digest":
        return not any(
            (
                snapshot["source_verifier_status"] != "invalid_digest",
                snapshot["source_verifier_ok"] is not False,
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
                bool(snapshot["recognized_signal_types_seen"]),
                snapshot["append_only_line_format_valid"] is not False,
                snapshot["source_error_count"] != 0,
                snapshot["source_digest_text_valid"] is not False,
            )
        )

    if verification_digest_status != "verified_verification_digest":
        return False
    source_digest_status = snapshot["source_digest_status"]
    if any(
        (
            snapshot["source_verifier_status"] != "digest_intact",
            snapshot["source_verifier_ok"] is not True,
            snapshot["source_digest_schema_version"]
            != _SOURCE_DIGEST_SCHEMA_VERSION,
            not _is_decision_id(
                snapshot["source_digest_decision_id"], "10EP-"
            ),
            source_digest_status
            not in {
                "verified_digest",
                "non_verified_digest",
                "invalid_10ej_source",
            },
            snapshot["source_digest_text_valid"] is not True,
        )
    ):
        return False

    if source_digest_status == "invalid_10ej_source":
        return not any(
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
                bool(snapshot["recognized_signal_types_seen"]),
                snapshot["append_only_line_format_valid"] is not False,
                snapshot["source_error_count"] != 0,
            )
        )

    source_bundle_status = snapshot["source_bundle_status"]
    if any(
        (
            snapshot["source_bundle_schema_version"]
            != _SOURCE_BUNDLE_SCHEMA_VERSION,
            not _is_decision_id(
                snapshot["source_bundle_decision_id"], "10EJ-"
            ),
            source_bundle_status
            not in {
                "verified_bundle",
                "verification_failed_bundle",
                *_INVALID_BUNDLE_STATUSES,
            },
        )
    ):
        return False

    if source_bundle_status in _INVALID_BUNDLE_STATUSES:
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
                bool(snapshot["recognized_signal_types_seen"]),
                snapshot["append_only_line_format_valid"] is not False,
                snapshot["source_error_count"] != 0,
            )
        ):
            return False
    else:
        if (
            not _valid_common_aggregate(snapshot)
            or snapshot["verified_record_hash_count"]
            != snapshot["records_valid"]
        ):
            return False
        expected_source_ok = (
            snapshot["source_error_count"] == 0
            and snapshot["ledger_file_seen"]
            and snapshot["records_seen"] > 0
            and snapshot["records_valid"] == snapshot["records_seen"]
            and snapshot["invalid_record_count"] == 0
            and snapshot["append_only_line_format_valid"]
        )
        if snapshot["source_ok"] is not expected_source_ok:
            return False
        if source_bundle_status == "verified_bundle":
            if (
                snapshot["source_ok"] is not True
                or snapshot["source_summary_status"] != "verified"
            ):
                return False
        elif (
            snapshot["source_ok"] is not False
            or snapshot["source_summary_status"] != "verification_failed"
        ):
            return False

    expected_source_digest_ok = source_digest_status == "verified_digest"
    if snapshot["source_digest_ok"] is not expected_source_digest_ok:
        return False
    if source_digest_status == "verified_digest":
        return source_bundle_status == "verified_bundle"
    return source_bundle_status != "verified_bundle"


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


def _validated_digest_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict:
        return None
    snapshot = dict(source)
    if any(type(key) is not str for key in snapshot):
        return None
    if set(snapshot) != _DIGEST_FIELDS:
        return None

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
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["verification_digest_schema_version"] != _DIGEST_SCHEMA_VERSION
        or snapshot["verification_digest_type"] != _DIGEST_TYPE
        or snapshot["verification_digest_scope"] != _DIGEST_SCOPE
        or snapshot["claim_boundary"] != _REPORTER_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["verification_digest_decision_id"], "10FB-"
        )
    ):
        return None

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

    status = snapshot["verification_digest_status"]
    if status == "verified_verification_digest":
        expected_errors: list[str] = []
    elif status == "non_verified_verification_digest":
        expected_errors = [_SOURCE_NON_VERIFIED_ERROR]
    elif status == "invalid_10ev_source":
        expected_errors = [_SOURCE_INVALID_ERROR]
    else:
        return None

    if (
        source_errors != expected_errors
        or snapshot["ok"] is not (status == "verified_verification_digest")
        or not _valid_source_aggregate(snapshot, status)
        or snapshot["verification_digest_text"]
        != _format_verification_digest_text(snapshot)
    ):
        return None

    expected_decision_id = "10FB-" + _hash_canonical(
        _digest_decision_material(snapshot)
    )[:32]
    if snapshot["verification_digest_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _verifier_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "verifier_schema_version": report["verifier_schema_version"],
        "verifier_scope": report["verifier_scope"],
        "source_verification_digest_schema_version": report[
            "source_verification_digest_schema_version"
        ],
        "source_verification_digest_decision_id": report[
            "source_verification_digest_decision_id"
        ],
        "source_verification_digest_status": report[
            "source_verification_digest_status"
        ],
        "source_verification_digest_ok": report[
            "source_verification_digest_ok"
        ],
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
        "source_verification_digest_text_valid": report[
            "source_verification_digest_text_valid"
        ],
        "verification_status": report["verification_status"],
        "errors": report["errors"],
    }


def _verification(
    *,
    source_verification_digest_schema_version: str = "",
    source_verification_digest_decision_id: str = "",
    source_verification_digest_status: str = "",
    source_verification_digest_ok: bool = False,
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
    source_verification_digest_text_valid: bool = False,
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
        "source_verification_digest_schema_version": (
            source_verification_digest_schema_version
        ),
        "source_verification_digest_decision_id": (
            source_verification_digest_decision_id
        ),
        "source_verification_digest_status": source_verification_digest_status,
        "source_verification_digest_ok": source_verification_digest_ok,
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
        "source_verification_digest_text_valid": (
            source_verification_digest_text_valid
        ),
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
    result["verifier_decision_id"] = "10FH-" + _hash_canonical(
        _verifier_decision_material(result)
    )[:32]
    return result


def verify_minimal_inert_ledger_status_digest_verification_report(
    verification_digest_report: dict | None,
) -> dict[str, Any]:
    """Verify one caller-supplied 10FB dictionary without source access."""

    try:
        source = _validated_digest_snapshot(verification_digest_report)
    except Exception:
        source = None
    if source is None:
        return _verification(
            verification_status="invalid_digest",
            errors=[_INVALID_DIGEST_ERROR],
        )

    return _verification(
        source_verification_digest_schema_version=source[
            "verification_digest_schema_version"
        ],
        source_verification_digest_decision_id=source[
            "verification_digest_decision_id"
        ],
        source_verification_digest_status=source[
            "verification_digest_status"
        ],
        source_verification_digest_ok=source["ok"],
        source_verifier_schema_version=source[
            "source_verifier_schema_version"
        ],
        source_verifier_decision_id=source["source_verifier_decision_id"],
        source_verifier_status=source["source_verifier_status"],
        source_verifier_ok=source["source_verifier_ok"],
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
        source_digest_text_valid=source["source_digest_text_valid"],
        source_verification_digest_text_valid=True,
        verification_status="digest_intact",
        errors=[],
    )


def _output_source_is_sanitized(report: dict[str, Any]) -> bool:
    return not any(
        (
            report["source_verification_digest_schema_version"] != "",
            report["source_verification_digest_decision_id"] != "",
            report["source_verification_digest_status"] != "",
            report["source_verification_digest_ok"] is not False,
            not _source_fields_are_sanitized(report),
            report["source_verification_digest_text_valid"] is not False,
        )
    )


def export_minimal_inert_ledger_status_digest_verification_verifier_report(
    verification_report: dict,
) -> str:
    """Export one validated 10FH report as deterministic sorted JSON."""

    error = "verification report must have the exact 10FH verifier shape"
    if type(verification_report) is not dict:
        raise ValueError(error)
    report = dict(verification_report)
    if any(type(key) is not str for key in report):
        raise ValueError(error)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError(error)

    for field in (
        "verifier_schema_version",
        "verifier_type",
        "verifier_scope",
        "verifier_decision_id",
        "source_verification_digest_schema_version",
        "source_verification_digest_decision_id",
        "source_verification_digest_status",
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
        or not _is_decision_id(report["verifier_decision_id"], "10FH-")
    ):
        raise ValueError(error)

    for field in (
        "ok",
        "source_verification_digest_ok",
        "source_verifier_ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "source_digest_text_valid",
        "source_verification_digest_text_valid",
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
        source_is_valid = _output_source_is_sanitized(report)
    elif status == "digest_intact":
        expected_errors = []
        source_status = report["source_verification_digest_status"]
        source_is_valid = not any(
            (
                report["source_verification_digest_schema_version"]
                != _DIGEST_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_verification_digest_decision_id"], "10FB-"
                ),
                source_status not in _VALID_DIGEST_STATUSES,
                report["source_verification_digest_ok"]
                is not (source_status == "verified_verification_digest"),
                report["source_verification_digest_text_valid"] is not True,
                not _valid_source_aggregate(report, source_status),
            )
        )
    else:
        raise ValueError(error)

    if (
        not source_is_valid
        or report_errors != expected_errors
        or report["ok"] is not (status == "digest_intact")
    ):
        raise ValueError(error)

    expected_decision_id = "10FH-" + _hash_canonical(
        _verifier_decision_material(report)
    )[:32]
    if report["verifier_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
