"""Phase 10EP - minimal inert ledger status digest reporter.

Consumes one caller-supplied 10EJ dictionary and returns a safe aggregate
digest. This module performs no source calls, mutation, scanning, runtime
action, or world-state change.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10EP.1"
_DIGEST_TYPE = "minimal_inert_ledger_status_digest_report"
_DIGEST_SCOPE = "inert_ledger_status_digest_only"
_BUNDLE_SCHEMA_VERSION = "10EJ.1"
_BUNDLE_TYPE = "minimal_inert_ledger_status_bundle_report"
_BUNDLE_SCOPE = "inert_ledger_status_bundle_only"
_VERIFIER_SCHEMA_VERSION = "10DX.1"
_REPORTER_SCHEMA_VERSION = "10ED.1"

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

_BUNDLE_FIELDS = frozenset(
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

_OUTPUT_FIELDS = frozenset(
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

_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_BUNDLE_CLAIM_BOUNDARY = (
    "aggregate 10DX and 10ED status bundle only; no ledger access, raw hashes, "
    "raw source errors, write, repair, runtime action, daemon, scheduler, "
    "network, world-data promotion, movement, map lookup, route execution, "
    "event emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_CLAIM_BOUNDARY = (
    "aggregate 10EJ status digest only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

_INVALID_SOURCE_ERROR = "bundle_report is not a valid 10EJ bundle"
_NON_VERIFIED_ERROR = "source 10EJ bundle did not report verified"
_SOURCE_FAILED_ERROR = "source 10DX verification did not pass"
_INVALID_10DX_ERROR = "verification_result is not a valid 10DX result"
_INVALID_10ED_ERROR = "summary_report is not a valid 10ED report"
_MISMATCH_ERROR = "10DX and 10ED sources do not match"

_INVALID_STATUS_ERRORS = {
    "invalid_10dx_source": [_INVALID_10DX_ERROR],
    "invalid_10ed_source": [_INVALID_10ED_ERROR],
    "mismatched_sources": [_MISMATCH_ERROR],
}


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


def _validated_bundle_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict or any(type(key) is not str for key in source):
        return None
    snapshot = dict(source)
    if set(snapshot) != _BUNDLE_FIELDS:
        return None

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
        if type(snapshot.get(field)) is not str:
            return None
    if (
        snapshot["bundle_schema_version"] != _BUNDLE_SCHEMA_VERSION
        or snapshot["bundle_type"] != _BUNDLE_TYPE
        or snapshot["bundle_scope"] != _BUNDLE_SCOPE
        or snapshot["claim_boundary"] != _BUNDLE_CLAIM_BOUNDARY
        or not _is_decision_id(snapshot["bundle_decision_id"], "10EJ-")
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

    bundle_errors = snapshot.get("errors")
    if type(bundle_errors) is not list:
        return None
    bundle_errors = list(bundle_errors)
    snapshot["errors"] = bundle_errors
    if any(type(error) is not str for error in bundle_errors):
        return None

    status = snapshot["bundle_status"]
    if status in _INVALID_STATUS_ERRORS:
        expected_errors = _INVALID_STATUS_ERRORS[status]
        if any(
            (
                snapshot["source_verifier_schema_version"] != "",
                snapshot["source_verifier_decision_id"] != "",
                snapshot["source_reporter_schema_version"] != "",
                snapshot["source_reporter_decision_id"] != "",
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
    elif status in {"verified_bundle", "verification_failed_bundle"}:
        if (
            snapshot["source_verifier_schema_version"]
            != _VERIFIER_SCHEMA_VERSION
            or not _is_decision_id(
                snapshot["source_verifier_decision_id"], "10DX-"
            )
            or snapshot["source_reporter_schema_version"]
            != _REPORTER_SCHEMA_VERSION
            or not _is_decision_id(
                snapshot["source_reporter_decision_id"], "10ED-"
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
        if status == "verified_bundle":
            expected_errors = []
            if (
                snapshot["source_ok"] is not True
                or snapshot["source_summary_status"] != "verified"
            ):
                return None
        else:
            expected_errors = [_SOURCE_FAILED_ERROR]
            if (
                snapshot["source_ok"] is not False
                or snapshot["source_summary_status"] != "verification_failed"
            ):
                return None
    else:
        return None

    if bundle_errors != expected_errors:
        return None
    expected_ok = status == "verified_bundle" and snapshot["source_ok"]
    if snapshot["ok"] is not expected_ok:
        return None
    return snapshot


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


def _digest(
    *,
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
    digest_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_signal_types = list(recognized_signal_types_seen or [])
    safe_errors = list(errors)
    result = {
        "ok": digest_status == "verified_digest" and source_ok,
        "digest_schema_version": _SCHEMA_VERSION,
        "digest_type": _DIGEST_TYPE,
        "digest_scope": _DIGEST_SCOPE,
        "digest_decision_id": "",
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
        "digest_status": digest_status,
        "digest_text": "",
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
    result["digest_text"] = _format_digest_text(result)
    result["digest_decision_id"] = "10EP-" + _hash_canonical(
        _digest_decision_material(result)
    )[:32]
    return result


def create_minimal_inert_ledger_status_digest_report(
    bundle_report: dict | None,
) -> dict[str, Any]:
    """Create one safe digest from one caller-supplied 10EJ dictionary."""

    try:
        bundle = _validated_bundle_snapshot(bundle_report)
    except Exception:
        bundle = None
    if bundle is None:
        return _digest(
            digest_status="invalid_10ej_source",
            errors=[_INVALID_SOURCE_ERROR],
        )

    verified = bundle["bundle_status"] == "verified_bundle"
    return _digest(
        source_bundle_schema_version=bundle["bundle_schema_version"],
        source_bundle_decision_id=bundle["bundle_decision_id"],
        source_bundle_status=bundle["bundle_status"],
        source_ok=bundle["source_ok"],
        source_summary_status=bundle["source_summary_status"],
        ledger_path_supplied=bundle["ledger_path_supplied"],
        ledger_file_seen=bundle["ledger_file_seen"],
        records_seen=bundle["records_seen"],
        records_valid=bundle["records_valid"],
        invalid_record_count=bundle["invalid_record_count"],
        verified_record_hash_count=bundle["verified_record_hash_count"],
        recognized_signal_types_seen=bundle["recognized_signal_types_seen"],
        append_only_line_format_valid=bundle[
            "append_only_line_format_valid"
        ],
        source_error_count=bundle["source_error_count"],
        digest_status="verified_digest" if verified else "non_verified_digest",
        errors=[] if verified else [_NON_VERIFIED_ERROR],
    )


def export_minimal_inert_ledger_status_digest_report(digest: dict) -> str:
    """Export one validated 10EP digest as deterministic JSON."""

    error = "digest must have the exact 10EP digest shape"
    if type(digest) is not dict or any(type(key) is not str for key in digest):
        raise ValueError(error)
    digest = dict(digest)
    if set(digest) != _OUTPUT_FIELDS:
        raise ValueError(error)

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
        if type(digest.get(field)) is not str:
            raise ValueError(error)
    if (
        digest["digest_schema_version"] != _SCHEMA_VERSION
        or digest["digest_type"] != _DIGEST_TYPE
        or digest["digest_scope"] != _DIGEST_SCOPE
        or digest["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(digest["digest_decision_id"], "10EP-")
    ):
        raise ValueError(error)

    for field in (
        "ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ):
        if type(digest.get(field)) is not bool:
            raise ValueError(error)
    for field in _GATE_FLAGS:
        if digest.get(field) is not False:
            raise ValueError(error)
    for field in (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ):
        if not _is_nonnegative_int(digest.get(field)):
            raise ValueError(error)

    signal_types = digest.get("recognized_signal_types_seen")
    if type(signal_types) is not list:
        raise ValueError(error)
    signal_types = list(signal_types)
    digest["recognized_signal_types_seen"] = signal_types
    if (
        any(
            type(signal_type) is not str or signal_type not in _KNOWN_SIGNAL_TYPES
            for signal_type in signal_types
        )
        or signal_types != sorted(set(signal_types))
        or digest["recognized_signal_type_count"] != len(signal_types)
    ):
        raise ValueError(error)

    digest_errors = digest.get("errors")
    if type(digest_errors) is not list:
        raise ValueError(error)
    digest_errors = list(digest_errors)
    digest["errors"] = digest_errors
    if any(type(item) is not str for item in digest_errors):
        raise ValueError(error)

    status = digest["digest_status"]
    if status == "invalid_10ej_source":
        expected_errors = [_INVALID_SOURCE_ERROR]
        if any(
            (
                digest["source_bundle_schema_version"] != "",
                digest["source_bundle_decision_id"] != "",
                digest["source_bundle_status"] != "",
                digest["source_ok"] is not False,
                digest["source_summary_status"] != "",
                digest["ledger_path_supplied"] is not False,
                digest["ledger_file_seen"] is not False,
                digest["records_seen"] != 0,
                digest["records_valid"] != 0,
                digest["invalid_record_count"] != 0,
                digest["verified_record_hash_count"] != 0,
                bool(signal_types),
                digest["append_only_line_format_valid"] is not False,
                digest["source_error_count"] != 0,
            )
        ):
            raise ValueError(error)
    elif status in {"verified_digest", "non_verified_digest"}:
        source_status = digest["source_bundle_status"]
        if (
            digest["source_bundle_schema_version"] != _BUNDLE_SCHEMA_VERSION
            or not _is_decision_id(
                digest["source_bundle_decision_id"], "10EJ-"
            )
            or source_status
            not in {
                "verified_bundle",
                "verification_failed_bundle",
                *_INVALID_STATUS_ERRORS,
            }
        ):
            raise ValueError(error)

        if source_status in _INVALID_STATUS_ERRORS:
            if any(
                (
                    digest["source_ok"] is not False,
                    digest["source_summary_status"] != "",
                    digest["ledger_path_supplied"] is not False,
                    digest["ledger_file_seen"] is not False,
                    digest["records_seen"] != 0,
                    digest["records_valid"] != 0,
                    digest["invalid_record_count"] != 0,
                    digest["verified_record_hash_count"] != 0,
                    bool(signal_types),
                    digest["append_only_line_format_valid"] is not False,
                    digest["source_error_count"] != 0,
                )
            ):
                raise ValueError(error)
        else:
            if (
                not _valid_common_aggregate(digest)
                or digest["verified_record_hash_count"]
                != digest["records_valid"]
            ):
                raise ValueError(error)
            expected_source_ok = (
                digest["source_error_count"] == 0
                and digest["ledger_file_seen"]
                and digest["records_seen"] > 0
                and digest["records_valid"] == digest["records_seen"]
                and digest["invalid_record_count"] == 0
                and digest["append_only_line_format_valid"]
            )
            if digest["source_ok"] is not expected_source_ok:
                raise ValueError(error)
            if source_status == "verified_bundle":
                if (
                    digest["source_ok"] is not True
                    or digest["source_summary_status"] != "verified"
                ):
                    raise ValueError(error)
            elif (
                digest["source_ok"] is not False
                or digest["source_summary_status"] != "verification_failed"
            ):
                raise ValueError(error)

        if status == "verified_digest":
            expected_errors = []
            if source_status != "verified_bundle":
                raise ValueError(error)
        else:
            expected_errors = [_NON_VERIFIED_ERROR]
            if source_status == "verified_bundle":
                raise ValueError(error)
    else:
        raise ValueError(error)

    if digest_errors != expected_errors:
        raise ValueError(error)
    expected_ok = status == "verified_digest" and digest["source_ok"]
    if digest["ok"] is not expected_ok:
        raise ValueError(error)
    if digest["digest_text"] != _format_digest_text(digest):
        raise ValueError(error)

    expected_decision_id = "10EP-" + _hash_canonical(
        _digest_decision_material(digest)
    )[:32]
    if digest["digest_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(digest, sort_keys=True, ensure_ascii=False)
