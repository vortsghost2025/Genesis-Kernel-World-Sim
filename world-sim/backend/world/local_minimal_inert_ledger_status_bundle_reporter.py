"""Phase 10EJ - minimal inert ledger status bundle reporter.

Consumes caller-supplied 10DX and 10ED dictionaries and returns one safe
aggregate status bundle. This module performs no file access, source calls,
mutation, scanning, runtime action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10EJ.1"
_BUNDLE_TYPE = "minimal_inert_ledger_status_bundle_report"
_BUNDLE_SCOPE = "inert_ledger_status_bundle_only"
_VERIFIER_SCHEMA_VERSION = "10DX.1"
_VERIFIER_TYPE = "minimal_inert_ledger_readback_result"
_VERIFIER_SCOPE = "inert_ledger_readback_only"
_REPORTER_SCHEMA_VERSION = "10ED.1"
_REPORTER_TYPE = "minimal_inert_ledger_summary_report"
_REPORTER_SCOPE = "inert_ledger_summary_only"

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

_VERIFIER_FIELDS = frozenset(
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

_REPORTER_FIELDS = frozenset(
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

_OUTPUT_FIELDS = frozenset(
    {
        "ok",
        "bundle_schema_version",
        "bundle_type",
        "bundle_scope",
        "bundle_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "source_reporter_schema_version",
        "source_reporter_decision_id",
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
        "bundle_status",
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
    "read-only inert ledger verification only; no write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, "
    "map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, or timing"
)

_REPORTER_CLAIM_BOUNDARY = (
    "aggregate 10DX result summary only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "aggregate 10DX and 10ED status bundle only; no ledger access, raw hashes, "
    "raw source errors, write, repair, runtime action, daemon, scheduler, "
    "network, world-data promotion, movement, map lookup, route execution, "
    "event emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_INVALID_10DX_ERROR = "verification_result is not a valid 10DX result"
_INVALID_10ED_ERROR = "summary_report is not a valid 10ED report"
_MISMATCH_ERROR = "10DX and 10ED sources do not match"
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


def _is_decision_id(value: object, prefix: str) -> bool:
    return (
        type(value) is str
        and value.startswith(prefix)
        and _is_lower_hex(value[len(prefix) :], 32)
    )


def _is_utf8_string(value: object) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


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


def _validated_verifier_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _VERIFIER_FIELDS:
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
        snapshot["verifier_schema_version"] != _VERIFIER_SCHEMA_VERSION
        or snapshot["verifier_type"] != _VERIFIER_TYPE
        or snapshot["verifier_scope"] != _VERIFIER_SCOPE
        or snapshot["claim_boundary"] != _VERIFIER_CLAIM_BOUNDARY
        or not _is_decision_id(snapshot["verifier_decision_id"], "10DX-")
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

    if (
        not _valid_common_aggregate(snapshot)
        or len(verified_hashes) != snapshot["records_valid"]
    ):
        return None
    expected_ok = (
        not source_errors
        and snapshot["ledger_file_seen"]
        and snapshot["records_seen"] > 0
        and snapshot["records_valid"] == snapshot["records_seen"]
        and snapshot["invalid_record_count"] == 0
        and snapshot["append_only_line_format_valid"]
    )
    if snapshot["ok"] is not expected_ok:
        return None
    return snapshot


def _reporter_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "reporter_schema_version": report["reporter_schema_version"],
        "reporter_scope": report["reporter_scope"],
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
        "summary_status": report["summary_status"],
        "errors": report["errors"],
    }


def _validated_reporter_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _REPORTER_FIELDS:
        return None

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
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["reporter_schema_version"] != _REPORTER_SCHEMA_VERSION
        or snapshot["reporter_type"] != _REPORTER_TYPE
        or snapshot["reporter_scope"] != _REPORTER_SCOPE
        or snapshot["claim_boundary"] != _REPORTER_CLAIM_BOUNDARY
        or not _is_decision_id(snapshot["reporter_decision_id"], "10ED-")
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

    report_errors = snapshot.get("errors")
    if type(report_errors) is not list:
        return None
    report_errors = list(report_errors)
    snapshot["errors"] = report_errors
    if any(type(error) is not str for error in report_errors):
        return None

    summary_status = snapshot["summary_status"]
    if summary_status == "invalid_source":
        expected_errors = [_INVALID_10DX_ERROR]
        if any(
            (
                snapshot["source_verifier_schema_version"] != "",
                snapshot["source_verifier_decision_id"] != "",
                snapshot["source_ok"] is not False,
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
    elif summary_status in {"verified", "verification_failed"}:
        if (
            snapshot["source_verifier_schema_version"]
            != _VERIFIER_SCHEMA_VERSION
            or not _is_decision_id(
                snapshot["source_verifier_decision_id"], "10DX-"
            )
            or not _valid_common_aggregate(snapshot)
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
        if summary_status == "verified":
            expected_errors = []
            if snapshot["source_ok"] is not True:
                return None
        else:
            expected_errors = [_SOURCE_FAILED_ERROR]
            if snapshot["source_ok"] is not False:
                return None
    else:
        return None

    if report_errors != expected_errors:
        return None
    expected_ok = summary_status == "verified" and snapshot["source_ok"]
    if snapshot["ok"] is not expected_ok:
        return None

    expected_decision_id = "10ED-" + _hash_canonical(
        _reporter_decision_material(snapshot)
    )[:32]
    if snapshot["reporter_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _sources_match(
    verifier: dict[str, Any],
    reporter: dict[str, Any],
) -> bool:
    return all(
        (
            reporter["source_verifier_decision_id"]
            == verifier["verifier_decision_id"],
            reporter["source_verifier_schema_version"]
            == verifier["verifier_schema_version"],
            reporter["source_ok"] is verifier["ok"],
            reporter["ledger_path_supplied"]
            is verifier["ledger_path_supplied"],
            reporter["ledger_file_seen"] is verifier["ledger_file_seen"],
            reporter["records_seen"] == verifier["records_seen"],
            reporter["records_valid"] == verifier["records_valid"],
            reporter["invalid_record_count"]
            == verifier["invalid_record_count"],
            reporter["verified_record_hash_count"]
            == len(verifier["verified_record_hashes"]),
            reporter["recognized_signal_types_seen"]
            == verifier["recognized_signal_types_seen"],
            reporter["recognized_signal_type_count"]
            == len(verifier["recognized_signal_types_seen"]),
            reporter["append_only_line_format_valid"]
            is verifier["append_only_line_format_valid"],
            reporter["source_error_count"] == len(verifier["errors"]),
        )
    )


def _bundle_decision_material(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_schema_version": bundle["bundle_schema_version"],
        "bundle_scope": bundle["bundle_scope"],
        "source_verifier_schema_version": bundle[
            "source_verifier_schema_version"
        ],
        "source_verifier_decision_id": bundle[
            "source_verifier_decision_id"
        ],
        "source_reporter_schema_version": bundle[
            "source_reporter_schema_version"
        ],
        "source_reporter_decision_id": bundle[
            "source_reporter_decision_id"
        ],
        "source_ok": bundle["source_ok"],
        "source_summary_status": bundle["source_summary_status"],
        "ledger_path_supplied": bundle["ledger_path_supplied"],
        "ledger_file_seen": bundle["ledger_file_seen"],
        "records_seen": bundle["records_seen"],
        "records_valid": bundle["records_valid"],
        "invalid_record_count": bundle["invalid_record_count"],
        "verified_record_hash_count": bundle["verified_record_hash_count"],
        "recognized_signal_types_seen": bundle[
            "recognized_signal_types_seen"
        ],
        "recognized_signal_type_count": bundle[
            "recognized_signal_type_count"
        ],
        "append_only_line_format_valid": bundle[
            "append_only_line_format_valid"
        ],
        "source_error_count": bundle["source_error_count"],
        "bundle_status": bundle["bundle_status"],
        "errors": bundle["errors"],
    }


def _bundle(
    *,
    source_verifier_schema_version: str = "",
    source_verifier_decision_id: str = "",
    source_reporter_schema_version: str = "",
    source_reporter_decision_id: str = "",
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
    bundle_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_signal_types = list(recognized_signal_types_seen or [])
    safe_errors = list(errors)
    ok = bundle_status == "verified_bundle" and source_ok and not safe_errors
    result = {
        "ok": ok,
        "bundle_schema_version": _SCHEMA_VERSION,
        "bundle_type": _BUNDLE_TYPE,
        "bundle_scope": _BUNDLE_SCOPE,
        "bundle_decision_id": "",
        "source_verifier_schema_version": source_verifier_schema_version,
        "source_verifier_decision_id": source_verifier_decision_id,
        "source_reporter_schema_version": source_reporter_schema_version,
        "source_reporter_decision_id": source_reporter_decision_id,
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
        "bundle_status": bundle_status,
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
    result["bundle_decision_id"] = "10EJ-" + _hash_canonical(
        _bundle_decision_material(result)
    )[:32]
    return result


def create_minimal_inert_ledger_status_bundle_report(
    verification_result: dict | None,
    summary_report: dict | None,
) -> dict[str, Any]:
    """Bundle one supplied 10DX result and matching 10ED report."""

    try:
        verifier = _validated_verifier_snapshot(verification_result)
    except Exception:
        verifier = None
    if verifier is None:
        return _bundle(
            bundle_status="invalid_10dx_source",
            errors=[_INVALID_10DX_ERROR],
        )

    try:
        reporter = _validated_reporter_snapshot(summary_report)
    except Exception:
        reporter = None
    if reporter is None:
        return _bundle(
            bundle_status="invalid_10ed_source",
            errors=[_INVALID_10ED_ERROR],
        )

    if not _sources_match(verifier, reporter):
        return _bundle(
            bundle_status="mismatched_sources",
            errors=[_MISMATCH_ERROR],
        )

    source_ok = verifier["ok"]
    return _bundle(
        source_verifier_schema_version=verifier["verifier_schema_version"],
        source_verifier_decision_id=verifier["verifier_decision_id"],
        source_reporter_schema_version=reporter["reporter_schema_version"],
        source_reporter_decision_id=reporter["reporter_decision_id"],
        source_ok=source_ok,
        source_summary_status=reporter["summary_status"],
        ledger_path_supplied=verifier["ledger_path_supplied"],
        ledger_file_seen=verifier["ledger_file_seen"],
        records_seen=verifier["records_seen"],
        records_valid=verifier["records_valid"],
        invalid_record_count=verifier["invalid_record_count"],
        verified_record_hash_count=len(verifier["verified_record_hashes"]),
        recognized_signal_types_seen=verifier[
            "recognized_signal_types_seen"
        ],
        append_only_line_format_valid=verifier[
            "append_only_line_format_valid"
        ],
        source_error_count=len(verifier["errors"]),
        bundle_status=(
            "verified_bundle" if source_ok else "verification_failed_bundle"
        ),
        errors=[] if source_ok else [_SOURCE_FAILED_ERROR],
    )


def export_minimal_inert_ledger_status_bundle_report(bundle: dict) -> str:
    """Export one validated 10EJ bundle as deterministic JSON."""

    error = "bundle must have the exact 10EJ bundle shape"
    if type(bundle) is not dict or any(type(key) is not str for key in bundle):
        raise ValueError(error)
    bundle = dict(bundle)
    if set(bundle) != _OUTPUT_FIELDS:
        raise ValueError(error)

    for field in (
        "bundle_schema_version",
        "bundle_type",
        "bundle_scope",
        "bundle_decision_id",
        "source_verifier_schema_version",
        "source_verifier_decision_id",
        "source_reporter_schema_version",
        "source_reporter_decision_id",
        "source_summary_status",
        "bundle_status",
        "claim_boundary",
    ):
        if type(bundle.get(field)) is not str:
            raise ValueError(error)
    if (
        bundle["bundle_schema_version"] != _SCHEMA_VERSION
        or bundle["bundle_type"] != _BUNDLE_TYPE
        or bundle["bundle_scope"] != _BUNDLE_SCOPE
        or bundle["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(bundle["bundle_decision_id"], "10EJ-")
    ):
        raise ValueError(error)

    for field in (
        "ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ):
        if type(bundle.get(field)) is not bool:
            raise ValueError(error)
    for field in _GATE_FLAGS:
        if bundle.get(field) is not False:
            raise ValueError(error)
    for field in (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ):
        if not _is_nonnegative_int(bundle.get(field)):
            raise ValueError(error)

    signal_types = bundle.get("recognized_signal_types_seen")
    if type(signal_types) is not list:
        raise ValueError(error)
    signal_types = list(signal_types)
    bundle["recognized_signal_types_seen"] = signal_types
    if (
        any(
            type(signal_type) is not str or signal_type not in _KNOWN_SIGNAL_TYPES
            for signal_type in signal_types
        )
        or signal_types != sorted(set(signal_types))
        or bundle["recognized_signal_type_count"] != len(signal_types)
    ):
        raise ValueError(error)

    bundle_errors = bundle.get("errors")
    if type(bundle_errors) is not list:
        raise ValueError(error)
    bundle_errors = list(bundle_errors)
    bundle["errors"] = bundle_errors
    if any(type(error) is not str for error in bundle_errors):
        raise ValueError(error)

    status = bundle["bundle_status"]
    invalid_status_errors = {
        "invalid_10dx_source": [_INVALID_10DX_ERROR],
        "invalid_10ed_source": [_INVALID_10ED_ERROR],
        "mismatched_sources": [_MISMATCH_ERROR],
    }
    if status in invalid_status_errors:
        expected_errors = invalid_status_errors[status]
        if any(
            (
                bundle["source_verifier_schema_version"] != "",
                bundle["source_verifier_decision_id"] != "",
                bundle["source_reporter_schema_version"] != "",
                bundle["source_reporter_decision_id"] != "",
                bundle["source_ok"] is not False,
                bundle["source_summary_status"] != "",
                bundle["ledger_path_supplied"] is not False,
                bundle["ledger_file_seen"] is not False,
                bundle["records_seen"] != 0,
                bundle["records_valid"] != 0,
                bundle["invalid_record_count"] != 0,
                bundle["verified_record_hash_count"] != 0,
                bool(signal_types),
                bundle["append_only_line_format_valid"] is not False,
                bundle["source_error_count"] != 0,
            )
        ):
            raise ValueError(error)
    elif status in {"verified_bundle", "verification_failed_bundle"}:
        if (
            bundle["source_verifier_schema_version"]
            != _VERIFIER_SCHEMA_VERSION
            or not _is_decision_id(
                bundle["source_verifier_decision_id"], "10DX-"
            )
            or bundle["source_reporter_schema_version"]
            != _REPORTER_SCHEMA_VERSION
            or not _is_decision_id(
                bundle["source_reporter_decision_id"], "10ED-"
            )
            or not _valid_common_aggregate(bundle)
            or bundle["verified_record_hash_count"] != bundle["records_valid"]
        ):
            raise ValueError(error)
        expected_source_ok = (
            bundle["source_error_count"] == 0
            and bundle["ledger_file_seen"]
            and bundle["records_seen"] > 0
            and bundle["records_valid"] == bundle["records_seen"]
            and bundle["invalid_record_count"] == 0
            and bundle["append_only_line_format_valid"]
        )
        if bundle["source_ok"] is not expected_source_ok:
            raise ValueError(error)
        if status == "verified_bundle":
            expected_errors = []
            if (
                bundle["source_ok"] is not True
                or bundle["source_summary_status"] != "verified"
            ):
                raise ValueError(error)
        else:
            expected_errors = [_SOURCE_FAILED_ERROR]
            if (
                bundle["source_ok"] is not False
                or bundle["source_summary_status"] != "verification_failed"
            ):
                raise ValueError(error)
        reporter_material = {
            "reporter_schema_version": bundle[
                "source_reporter_schema_version"
            ],
            "reporter_scope": _REPORTER_SCOPE,
            "source_verifier_schema_version": bundle[
                "source_verifier_schema_version"
            ],
            "source_verifier_decision_id": bundle[
                "source_verifier_decision_id"
            ],
            "source_ok": bundle["source_ok"],
            "ledger_path_supplied": bundle["ledger_path_supplied"],
            "ledger_file_seen": bundle["ledger_file_seen"],
            "records_seen": bundle["records_seen"],
            "records_valid": bundle["records_valid"],
            "invalid_record_count": bundle["invalid_record_count"],
            "verified_record_hash_count": bundle[
                "verified_record_hash_count"
            ],
            "recognized_signal_types_seen": signal_types,
            "recognized_signal_type_count": bundle[
                "recognized_signal_type_count"
            ],
            "append_only_line_format_valid": bundle[
                "append_only_line_format_valid"
            ],
            "source_error_count": bundle["source_error_count"],
            "summary_status": bundle["source_summary_status"],
            "errors": expected_errors,
        }
        expected_reporter_decision_id = "10ED-" + _hash_canonical(
            reporter_material
        )[:32]
        if (
            bundle["source_reporter_decision_id"]
            != expected_reporter_decision_id
        ):
            raise ValueError(error)
    else:
        raise ValueError(error)

    if bundle_errors != expected_errors:
        raise ValueError(error)
    expected_ok = status == "verified_bundle" and bundle["source_ok"]
    if bundle["ok"] is not expected_ok:
        raise ValueError(error)

    expected_decision_id = "10EJ-" + _hash_canonical(
        _bundle_decision_material(bundle)
    )[:32]
    if bundle["bundle_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(bundle, sort_keys=True, ensure_ascii=False)
