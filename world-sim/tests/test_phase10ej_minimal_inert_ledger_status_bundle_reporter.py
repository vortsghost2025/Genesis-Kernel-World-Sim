"""Phase 10EJ - minimal inert ledger status bundle reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_status_bundle_reporter import (
    create_minimal_inert_ledger_status_bundle_report,
    export_minimal_inert_ledger_status_bundle_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_bundle_reporter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

VERIFIER_FIELDS = {
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

REPORTER_FIELDS = {
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

BUNDLE_FIELDS = {
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

GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

FORBIDDEN_BUNDLE_FIELDS = {
    "verified_record_hashes",
    "source_errors",
    "raw_10dx_errors",
    "raw_10ed_errors",
    "ledger_path",
    "path",
    "record_hash",
    "record",
    "records",
    "equality_signal_value",
    "equality_signal_type",
    "agent_id",
    "tile",
    "route",
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
    "event",
    "npc_behavior",
}

VERIFIER_CLAIM_BOUNDARY = (
    "read-only inert ledger verification only; no write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, "
    "map lookup, route execution, event emission, NPC behavior, "
    "co-presence, awareness, relationship, interaction, or timing"
)

REPORTER_CLAIM_BOUNDARY = (
    "aggregate 10DX result summary only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

INVALID_10DX_ERROR = "verification_result is not a valid 10DX result"
INVALID_10ED_ERROR = "summary_report is not a valid 10ED report"
MISMATCH_ERROR = "10DX and 10ED sources do not match"
SOURCE_FAILED_ERROR = "source 10DX verification did not pass"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _reporter_decision_id(report: dict) -> str:
    material = {
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
    return "10ED-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _bundle_decision_id(bundle: dict) -> str:
    material = {
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
    return "10EJ-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_verifier_success() -> dict:
    return {
        "ok": True,
        "verifier_schema_version": "10DX.1",
        "verifier_type": "minimal_inert_ledger_readback_result",
        "verifier_scope": "inert_ledger_readback_only",
        "verifier_decision_id": "10DX-" + "a" * 32,
        "ledger_path_supplied": True,
        "ledger_file_seen": True,
        "records_seen": 2,
        "records_valid": 2,
        "invalid_record_count": 0,
        "verified_record_hashes": ["1" * 64, "2" * 64],
        "recognized_signal_types_seen": [
            "snapshot_hash_equality",
            "snapshot_id_equality",
        ],
        "append_only_line_format_valid": True,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": VERIFIER_CLAIM_BOUNDARY,
        "errors": [],
    }


def _valid_verifier_failure() -> dict:
    verifier = _valid_verifier_success()
    verifier.update(
        {
            "ok": False,
            "verifier_decision_id": "10DX-" + "b" * 32,
            "ledger_file_seen": False,
            "records_seen": 0,
            "records_valid": 0,
            "invalid_record_count": 0,
            "verified_record_hashes": [],
            "recognized_signal_types_seen": [],
            "append_only_line_format_valid": False,
            "errors": [
                "source verification failed at C:\\private\\ledger.ndjson",
                "equality_signal_value=opaque-source-value",
            ],
        }
    )
    return verifier


def _matching_report(verifier: dict) -> dict:
    source_ok = verifier["ok"]
    summary_status = "verified" if source_ok else "verification_failed"
    errors = [] if source_ok else [SOURCE_FAILED_ERROR]
    report = {
        "ok": source_ok,
        "reporter_schema_version": "10ED.1",
        "reporter_type": "minimal_inert_ledger_summary_report",
        "reporter_scope": "inert_ledger_summary_only",
        "reporter_decision_id": "",
        "source_verifier_schema_version": verifier["verifier_schema_version"],
        "source_verifier_decision_id": verifier["verifier_decision_id"],
        "source_ok": source_ok,
        "ledger_path_supplied": verifier["ledger_path_supplied"],
        "ledger_file_seen": verifier["ledger_file_seen"],
        "records_seen": verifier["records_seen"],
        "records_valid": verifier["records_valid"],
        "invalid_record_count": verifier["invalid_record_count"],
        "verified_record_hash_count": len(verifier["verified_record_hashes"]),
        "recognized_signal_types_seen": list(
            verifier["recognized_signal_types_seen"]
        ),
        "recognized_signal_type_count": len(
            verifier["recognized_signal_types_seen"]
        ),
        "append_only_line_format_valid": verifier[
            "append_only_line_format_valid"
        ],
        "source_error_count": len(verifier["errors"]),
        "summary_status": summary_status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": REPORTER_CLAIM_BOUNDARY,
        "errors": errors,
    }
    report["reporter_decision_id"] = _reporter_decision_id(report)
    return report


def _assert_inert(bundle: dict) -> None:
    for field in GATE_FLAGS:
        assert bundle[field] is False, field


def _assert_sanitized_status(
    bundle: dict,
    status: str,
    error: str,
) -> None:
    assert bundle["ok"] is False
    assert bundle["bundle_status"] == status
    assert bundle["errors"] == [error]
    assert bundle["source_verifier_schema_version"] == ""
    assert bundle["source_verifier_decision_id"] == ""
    assert bundle["source_reporter_schema_version"] == ""
    assert bundle["source_reporter_decision_id"] == ""
    assert bundle["source_ok"] is False
    assert bundle["source_summary_status"] == ""
    assert bundle["ledger_path_supplied"] is False
    assert bundle["ledger_file_seen"] is False
    assert bundle["records_seen"] == 0
    assert bundle["records_valid"] == 0
    assert bundle["invalid_record_count"] == 0
    assert bundle["verified_record_hash_count"] == 0
    assert bundle["recognized_signal_types_seen"] == []
    assert bundle["recognized_signal_type_count"] == 0
    assert bundle["append_only_line_format_valid"] is False
    assert bundle["source_error_count"] == 0
    assert set(bundle) == BUNDLE_FIELDS
    _assert_inert(bundle)


def test_public_api_accepts_exactly_two_caller_supplied_inputs():
    signature = inspect.signature(
        create_minimal_inert_ledger_status_bundle_report
    )

    assert tuple(signature.parameters) == (
        "verification_result",
        "summary_report",
    )


def test_missing_10dx_fails_closed():
    report = _matching_report(_valid_verifier_success())

    bundle = create_minimal_inert_ledger_status_bundle_report(None, report)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


def test_missing_10ed_fails_closed():
    bundle = create_minimal_inert_ledger_status_bundle_report(
        _valid_verifier_success(),
        None,
    )

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)


def test_invalid_10dx_takes_precedence_when_both_sources_are_invalid():
    bundle = create_minimal_inert_ledger_status_bundle_report(None, None)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


@pytest.mark.parametrize("value", ([], "10DX", 7, True, object()))
def test_non_dict_10dx_fails_closed(value: object):
    report = _matching_report(_valid_verifier_success())

    bundle = create_minimal_inert_ledger_status_bundle_report(value, report)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


@pytest.mark.parametrize("value", ([], "10ED", 7, True, object()))
def test_non_dict_10ed_fails_closed(value: object):
    bundle = create_minimal_inert_ledger_status_bundle_report(
        _valid_verifier_success(),
        value,
    )

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)


def test_valid_success_pair_produces_verified_bundle():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    assert bundle == {
        "ok": True,
        "bundle_schema_version": "10EJ.1",
        "bundle_type": "minimal_inert_ledger_status_bundle_report",
        "bundle_scope": "inert_ledger_status_bundle_only",
        "bundle_decision_id": bundle["bundle_decision_id"],
        "source_verifier_schema_version": "10DX.1",
        "source_verifier_decision_id": "10DX-" + "a" * 32,
        "source_reporter_schema_version": "10ED.1",
        "source_reporter_decision_id": report["reporter_decision_id"],
        "source_ok": True,
        "source_summary_status": "verified",
        "ledger_path_supplied": True,
        "ledger_file_seen": True,
        "records_seen": 2,
        "records_valid": 2,
        "invalid_record_count": 0,
        "verified_record_hash_count": 2,
        "recognized_signal_types_seen": [
            "snapshot_hash_equality",
            "snapshot_id_equality",
        ],
        "recognized_signal_type_count": 2,
        "append_only_line_format_valid": True,
        "source_error_count": 0,
        "bundle_status": "verified_bundle",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": bundle["claim_boundary"],
        "errors": [],
    }
    assert bundle["bundle_decision_id"].startswith("10EJ-")
    _assert_inert(bundle)


def test_valid_failure_pair_produces_verification_failed_bundle():
    verifier = _valid_verifier_failure()
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    assert bundle["ok"] is False
    assert bundle["source_ok"] is False
    assert bundle["source_summary_status"] == "verification_failed"
    assert bundle["source_error_count"] == 2
    assert bundle["bundle_status"] == "verification_failed_bundle"
    assert bundle["errors"] == [SOURCE_FAILED_ERROR]
    _assert_inert(bundle)


@pytest.mark.parametrize("field", sorted(VERIFIER_FIELDS))
def test_missing_required_10dx_field_fails_closed(field: str):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    verifier.pop(field)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


@pytest.mark.parametrize("field", sorted(REPORTER_FIELDS))
def test_missing_required_10ed_field_fails_closed(field: str):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report.pop(field)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)


def test_unexpected_10dx_field_fails_closed():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    verifier["future_field"] = "not authorized"

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


def test_unexpected_10ed_field_fails_closed():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report["future_field"] = "not authorized"

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("verifier_schema_version", "10DX.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("verifier_decision_id", "10DX-" + "A" * 32),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_invalid_10dx_identity_fails_closed(field: str, value: object):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    verifier[field] = value

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10dx_source", INVALID_10DX_ERROR)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("reporter_schema_version", "10ED.2"),
        ("reporter_type", "future_reporter"),
        ("reporter_scope", "future_scope"),
        ("reporter_decision_id", "10ED-" + "A" * 32),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_invalid_10ed_identity_fails_closed(field: str, value: object):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report[field] = value

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)


@pytest.mark.parametrize(
    ("side", "field"),
    tuple(
        ("10dx", field)
        for field in (
            "ok",
            "ledger_path_supplied",
            "ledger_file_seen",
            "append_only_line_format_valid",
        )
    )
    + tuple(
        ("10ed", field)
        for field in (
            "ok",
            "source_ok",
            "ledger_path_supplied",
            "ledger_file_seen",
            "append_only_line_format_valid",
        )
    ),
)
def test_integer_bool_drift_fails_closed(side: str, field: str):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    target = verifier if side == "10dx" else report
    target[field] = 1

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    expected_status = "invalid_10dx_source" if side == "10dx" else "invalid_10ed_source"
    expected_error = INVALID_10DX_ERROR if side == "10dx" else INVALID_10ED_ERROR
    _assert_sanitized_status(bundle, expected_status, expected_error)


@pytest.mark.parametrize("side", ("10dx", "10ed"))
@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(side: str, field: str):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    target = verifier if side == "10dx" else report
    target[field] = 0

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    expected_status = "invalid_10dx_source" if side == "10dx" else "invalid_10ed_source"
    expected_error = INVALID_10DX_ERROR if side == "10dx" else INVALID_10ED_ERROR
    _assert_sanitized_status(bundle, expected_status, expected_error)


@pytest.mark.parametrize("side", ("10dx", "10ed"))
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", -1),
        ("records_valid", -1),
        ("invalid_record_count", -1),
        ("records_seen", True),
        ("records_valid", False),
        ("invalid_record_count", True),
    ),
)
def test_negative_or_bool_counts_fail_closed(
    side: str,
    field: str,
    value: object,
):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    target = verifier if side == "10dx" else report
    target[field] = value

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    expected_status = "invalid_10dx_source" if side == "10dx" else "invalid_10ed_source"
    expected_error = INVALID_10DX_ERROR if side == "10dx" else INVALID_10ED_ERROR
    _assert_sanitized_status(bundle, expected_status, expected_error)


@pytest.mark.parametrize(
    ("side", "field", "value"),
    (
        ("10dx", "records_seen", type("IntSubclass", (int,), {})(2)),
        (
            "10dx",
            "verified_record_hashes",
            type("ListSubclass", (list,), {})(["1" * 64, "2" * 64]),
        ),
        (
            "10dx",
            "verifier_decision_id",
            type("StrSubclass", (str,), {})("10DX-" + "a" * 32),
        ),
        ("10ed", "records_seen", type("IntSubclass", (int,), {})(2)),
        (
            "10ed",
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(
                ["snapshot_hash_equality", "snapshot_id_equality"]
            ),
        ),
        (
            "10ed",
            "reporter_decision_id",
            type("StrSubclass", (str,), {})("10ED-" + "a" * 32),
        ),
    ),
)
def test_dict_list_str_and_int_subclasses_fail_closed(
    side: str,
    field: str,
    value: object,
):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    target = verifier if side == "10dx" else report
    target[field] = value

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    expected_status = "invalid_10dx_source" if side == "10dx" else "invalid_10ed_source"
    expected_error = INVALID_10DX_ERROR if side == "10dx" else INVALID_10ED_ERROR
    _assert_sanitized_status(bundle, expected_status, expected_error)


@pytest.mark.parametrize("side", ("10dx", "10ed"))
def test_hostile_dict_subclass_fails_closed_without_invoking_overrides(side: str):
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    if side == "10dx":
        verifier = _HostileDict(verifier)
    else:
        report = _HostileDict(report)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    expected_status = "invalid_10dx_source" if side == "10dx" else "invalid_10ed_source"
    expected_error = INVALID_10DX_ERROR if side == "10dx" else INVALID_10ED_ERROR
    _assert_sanitized_status(bundle, expected_status, expected_error)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_verifier_decision_id", "10DX-" + "c" * 32),
        ("source_verifier_schema_version", "10DX.2"),
        ("source_ok", False),
        ("ledger_path_supplied", False),
        ("ledger_file_seen", False),
        ("records_seen", 3),
        ("records_valid", 1),
        ("invalid_record_count", 1),
        ("verified_record_hash_count", 1),
        ("recognized_signal_type_count", 1),
        ("append_only_line_format_valid", False),
        ("source_error_count", 1),
    ),
)
def test_valid_but_mismatched_scalar_sources_fail_closed(
    field: str,
    value: object,
):
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report[field] = value
    if field not in {
        "source_verifier_schema_version",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "append_only_line_format_valid",
        "source_error_count",
    }:
        report["reporter_decision_id"] = _reporter_decision_id(report)
    else:
        # Keep the 10ED envelope internally valid while changing the paired 10DX.
        verifier_field = {
            "source_verifier_schema_version": "verifier_schema_version",
            "source_ok": "ok",
            "verified_record_hash_count": None,
            "recognized_signal_type_count": None,
            "source_error_count": None,
        }.get(field, field)
        if verifier_field is not None:
            verifier[verifier_field] = value
        if field == "verified_record_hash_count":
            verifier["verified_record_hashes"] = ["1" * 64]
            verifier["records_valid"] = 1
            verifier["records_seen"] = 1
            report["records_valid"] = 1
            report["records_seen"] = 1
        elif field == "recognized_signal_type_count":
            report["recognized_signal_types_seen"] = ["snapshot_id_equality"]
            verifier["recognized_signal_types_seen"] = [
                "snapshot_hash_equality",
                "snapshot_id_equality",
            ]
        elif field == "source_error_count":
            verifier = _valid_verifier_failure()
            report = _matching_report(verifier)
            verifier["errors"].append("another opaque error")
        report["reporter_decision_id"] = _reporter_decision_id(report)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    assert bundle["ok"] is False
    assert bundle["bundle_status"] in {
        "invalid_10dx_source",
        "invalid_10ed_source",
        "mismatched_sources",
    }
    _assert_inert(bundle)


def test_mismatched_decision_ids_fail_closed_as_mismatched_sources():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report["source_verifier_decision_id"] = "10DX-" + "c" * 32
    report["reporter_decision_id"] = _reporter_decision_id(report)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "mismatched_sources", MISMATCH_ERROR)


def test_mismatched_counts_fail_closed_as_mismatched_sources():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": ["snapshot_id_equality"],
            "recognized_signal_type_count": 1,
        }
    )
    report["reporter_decision_id"] = _reporter_decision_id(report)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "mismatched_sources", MISMATCH_ERROR)


def test_mismatched_signal_type_lists_fail_closed_as_mismatched_sources():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report["recognized_signal_types_seen"] = ["snapshot_id_equality"]
    report["recognized_signal_type_count"] = 1
    report["reporter_decision_id"] = _reporter_decision_id(report)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "mismatched_sources", MISMATCH_ERROR)


def test_mismatched_source_error_count_fails_closed_as_mismatched_sources():
    verifier = _valid_verifier_failure()
    report = _matching_report(verifier)
    verifier["errors"].append("third opaque error")

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    _assert_sanitized_status(bundle, "mismatched_sources", MISMATCH_ERROR)


def test_sources_match_contains_all_thirteen_required_cross_checks():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    matcher = functions["_sources_match"]
    assert matcher is not None

    required_comparisons = (
        'reporter["source_verifier_decision_id"]',
        'verifier["verifier_decision_id"]',
        'reporter["source_verifier_schema_version"]',
        'verifier["verifier_schema_version"]',
        'reporter["source_ok"]',
        'verifier["ok"]',
        'reporter["ledger_path_supplied"]',
        'verifier["ledger_path_supplied"]',
        'reporter["ledger_file_seen"]',
        'verifier["ledger_file_seen"]',
        'reporter["records_seen"]',
        'verifier["records_seen"]',
        'reporter["records_valid"]',
        'verifier["records_valid"]',
        'reporter["invalid_record_count"]',
        'verifier["invalid_record_count"]',
        'reporter["verified_record_hash_count"]',
        'len(verifier["verified_record_hashes"])',
        'reporter["recognized_signal_types_seen"]',
        'verifier["recognized_signal_types_seen"]',
        'reporter["recognized_signal_type_count"]',
        'len(verifier["recognized_signal_types_seen"])',
        'reporter["append_only_line_format_valid"]',
        'verifier["append_only_line_format_valid"]',
        'reporter["source_error_count"]',
        'len(verifier["errors"])',
    )
    for comparison in required_comparisons:
        assert comparison in matcher


def test_source_lists_are_snapshot_detached_from_bundle_and_export():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)
    verifier["verified_record_hashes"].append("3" * 64)
    verifier["recognized_signal_types_seen"].clear()
    verifier["errors"].append("late source error")
    report["recognized_signal_types_seen"].clear()
    report["errors"].append("late reporter error")

    assert bundle["verified_record_hash_count"] == 2
    assert bundle["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    assert bundle["source_error_count"] == 0
    exported = export_minimal_inert_ledger_status_bundle_report(bundle)
    assert "late source error" not in exported
    assert "late reporter error" not in exported


def test_raw_10dx_errors_are_counted_but_not_emitted():
    verifier = _valid_verifier_failure()
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)
    serialized = json.dumps(bundle)

    assert bundle["source_error_count"] == len(verifier["errors"])
    assert all(error not in serialized for error in verifier["errors"])
    assert "source_errors" not in bundle


def test_raw_10dx_hashes_are_counted_but_not_emitted():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)
    serialized = json.dumps(bundle)

    assert bundle["verified_record_hash_count"] == 2
    assert "verified_record_hashes" not in bundle
    assert all(value not in serialized for value in verifier["verified_record_hashes"])


def test_invalid_10ed_raw_errors_are_not_emitted():
    verifier = _valid_verifier_success()
    report = _matching_report(verifier)
    report["errors"] = [
        "C:\\private\\report.ndjson",
        "equality_signal_value=secret-reporter-value",
    ]

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)
    serialized = json.dumps(bundle)

    _assert_sanitized_status(bundle, "invalid_10ed_source", INVALID_10ED_ERROR)
    assert "private" not in serialized
    assert "secret-reporter-value" not in serialized


def test_raw_paths_and_equality_values_cannot_appear_in_output():
    verifier = _valid_verifier_failure()
    verifier["errors"] = [
        "C:\\private\\runtime_adapter_decisions.ndjson",
        "equality_signal_value=secret-value",
        "raw_record={agent_id: private-agent}",
    ]
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)
    serialized = json.dumps(bundle)

    assert "runtime_adapter_decisions.ndjson" not in serialized
    assert "secret-value" not in serialized
    assert "private-agent" not in serialized
    assert "equality_signal_value" not in serialized
    assert bundle["source_error_count"] == 3


def test_output_contains_only_safe_aggregate_fields():
    pairs = (
        (_valid_verifier_success(),),
        (_valid_verifier_failure(),),
    )
    for (verifier,) in pairs:
        bundle = create_minimal_inert_ledger_status_bundle_report(
            verifier,
            _matching_report(verifier),
        )

        assert set(bundle) == BUNDLE_FIELDS
        assert FORBIDDEN_BUNDLE_FIELDS.isdisjoint(bundle)
        _assert_inert(bundle)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_bundled(signal_type: str):
    verifier = _valid_verifier_success()
    verifier["recognized_signal_types_seen"] = [signal_type]
    report = _matching_report(verifier)

    bundle = create_minimal_inert_ledger_status_bundle_report(verifier, report)

    assert bundle["ok"] is True
    assert bundle["recognized_signal_types_seen"] == [signal_type]
    assert bundle["recognized_signal_type_count"] == 1


def test_export_is_deterministic_sorted_json():
    verifier = _valid_verifier_success()
    bundle = create_minimal_inert_ledger_status_bundle_report(
        verifier,
        _matching_report(verifier),
    )

    first = export_minimal_inert_ledger_status_bundle_report(bundle)
    second = export_minimal_inert_ledger_status_bundle_report(dict(bundle))

    assert first == second
    assert first == json.dumps(bundle, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == bundle


def test_export_rejects_unexpected_or_forbidden_fields():
    verifier = _valid_verifier_success()
    bundle = create_minimal_inert_ledger_status_bundle_report(
        verifier,
        _matching_report(verifier),
    )
    bundle["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10EJ bundle shape"):
        export_minimal_inert_ledger_status_bundle_report(bundle)


def test_export_rejects_dict_subclass_without_serializing_override():
    class _TaintedBundle(dict):
        def items(self):
            tainted = dict(super().items())
            tainted["errors"] = ["raw secret"]
            return tainted.items()

    verifier = _valid_verifier_success()
    bundle = _TaintedBundle(
        create_minimal_inert_ledger_status_bundle_report(
            verifier,
            _matching_report(verifier),
        )
    )

    with pytest.raises(ValueError, match="exact 10EJ bundle shape"):
        export_minimal_inert_ledger_status_bundle_report(bundle)


def test_export_rejects_forged_valid_source_reporter_decision_id():
    verifier = _valid_verifier_success()
    bundle = create_minimal_inert_ledger_status_bundle_report(
        verifier,
        _matching_report(verifier),
    )
    bundle["source_reporter_decision_id"] = "10ED-" + "c" * 32
    bundle["bundle_decision_id"] = _bundle_decision_id(bundle)

    with pytest.raises(ValueError, match="exact 10EJ bundle shape"):
        export_minimal_inert_ledger_status_bundle_report(bundle)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", 1),
        ("source_ok", 1),
        ("ledger_file_seen", 1),
        ("records_seen", True),
        ("verified_record_hash_count", -1),
        ("recognized_signal_types_seen", ["future_unknown_signal"]),
        ("recognized_signal_type_count", 99),
        ("source_error_count", -1),
        ("source_summary_status", "runtime_started"),
        ("bundle_status", "runtime_started"),
        ("runtime_allowed", 0),
        ("errors", ["raw source error"]),
        ("bundle_decision_id", "10EJ-tainted"),
        (
            "source_reporter_decision_id",
            type("StrSubclass", (str,), {})("10ED-" + "a" * 32),
        ),
        (
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(["snapshot_id_equality"]),
        ),
        ("source_error_count", type("IntSubclass", (int,), {})(0)),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    verifier = _valid_verifier_success()
    bundle = create_minimal_inert_ledger_status_bundle_report(
        verifier,
        _matching_report(verifier),
    )
    bundle[field] = value

    with pytest.raises(ValueError, match="exact 10EJ bundle shape"):
        export_minimal_inert_ledger_status_bundle_report(bundle)


def test_gate_flags_are_false_on_success_and_failure():
    success = _valid_verifier_success()
    failure = _valid_verifier_failure()
    for bundle in (
        create_minimal_inert_ledger_status_bundle_report(
            success,
            _matching_report(success),
        ),
        create_minimal_inert_ledger_status_bundle_report(
            failure,
            _matching_report(failure),
        ),
        create_minimal_inert_ledger_status_bundle_report(None, None),
    ):
        _assert_inert(bundle)


def test_module_imports_only_allowed_standard_library_modules():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_import_roots = {"__future__", "hashlib", "json", "typing"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_import_roots
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in allowed_import_roots


def test_module_has_no_backend_10dx_10ed_or_10cp_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")

    forbidden_names = (
        "verify_minimal_inert_ledger_readback",
        "export_minimal_inert_ledger_readback_result",
        "create_minimal_inert_ledger_summary_report",
        "export_minimal_inert_ledger_summary_report",
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_runtime_adapter_inert_ledger_writer",
        "backend.",
    )
    for name in forbidden_names:
        assert name not in source


def test_module_has_no_file_access_mutation_scanning_or_runtime_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "__import__",
        "eval",
        "exec",
        "compile",
        "system",
        "popen",
        "open",
        "read",
        "read_text",
        "read_bytes",
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "touch",
        "truncate",
        "mkdir",
        "makedirs",
        "unlink",
        "remove",
        "delete",
        "rename",
        "replace",
        "repair",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "iterdir",
        "emit_event",
        "create_event",
        "map_lookup",
        "append_inert_ledger_record",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls

    assert "world-sim/data" not in source
    assert "runtime_adapter_decisions.ndjson" not in source


def test_caller_owned_lists_are_detached_before_content_validation():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    verifier_validator = functions["_validated_verifier_snapshot"]
    assert verifier_validator is not None
    assert verifier_validator.index(
        "verified_hashes = list(verified_hashes)"
    ) < verifier_validator.index("not _is_lower_hex(record_hash, 64)")
    assert verifier_validator.index(
        "signal_types = list(signal_types)"
    ) < verifier_validator.index("signal_type not in _KNOWN_SIGNAL_TYPES")
    assert verifier_validator.index(
        "source_errors = list(source_errors)"
    ) < verifier_validator.index("not _is_utf8_string(error)")

    reporter_validator = functions["_validated_reporter_snapshot"]
    assert reporter_validator is not None
    assert reporter_validator.index(
        "signal_types = list(signal_types)"
    ) < reporter_validator.index("signal_type not in _KNOWN_SIGNAL_TYPES")
    assert reporter_validator.index(
        "report_errors = list(report_errors)"
    ) < reporter_validator.index("type(error) is not str")

    exporter = functions["export_minimal_inert_ledger_status_bundle_report"]
    assert exporter is not None
    assert exporter.index("signal_types = list(signal_types)") < exporter.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert exporter.index("bundle_errors = list(bundle_errors)") < exporter.index(
        "type(error) is not str"
    )
