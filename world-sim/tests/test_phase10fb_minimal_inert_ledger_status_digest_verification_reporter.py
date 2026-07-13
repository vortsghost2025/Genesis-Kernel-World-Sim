"""Phase 10FB - inert ledger digest verification reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_status_digest_verification_reporter import (
    create_minimal_inert_ledger_status_digest_verification_report,
    export_minimal_inert_ledger_status_digest_verification_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_digest_verification_reporter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

VERIFICATION_FIELDS = {
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

OUTPUT_FIELDS = {
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

GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

FORBIDDEN_OUTPUT_FIELDS = {
    "digest_text",
    "source_reporter_decision_id",
    "verified_record_hashes",
    "source_errors",
    "raw_10dx_errors",
    "raw_10ed_errors",
    "raw_10ej_errors",
    "raw_10ep_errors",
    "raw_10ev_errors",
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
    "verify one 10EP status digest only; no ledger access, digest text, raw "
    "hashes, raw source errors, write, repair, runtime action, daemon, "
    "scheduler, network, world-data promotion, movement, map lookup, route "
    "execution, event emission, NPC behavior, co-presence, awareness, "
    "relationship, interaction, or timing"
)

REPORTER_CLAIM_BOUNDARY = (
    "report one 10EV status digest verification only; no ledger access, "
    "digest text, raw hashes, raw source errors, write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, map "
    "lookup, route execution, event emission, NPC behavior, co-presence, "
    "awareness, relationship, interaction, or timing"
)

INVALID_10EV_ERROR = (
    "verification_report is not a valid 10EV verification report"
)
NON_VERIFIED_ERROR = "source 10EV verification did not report digest_intact"
SOURCE_INVALID_DIGEST_ERROR = "digest_report is not a valid 10EP digest"

INVALID_BUNDLE_STATUSES = (
    "invalid_10dx_source",
    "invalid_10ed_source",
    "mismatched_sources",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _verifier_decision_id(report: dict) -> str:
    material = {
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
    return "10EV-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _verification_digest_decision_id(report: dict) -> str:
    material = {
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
    return "10FB-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _verification_digest_text(report: dict) -> str:
    bool_text = lambda value: "true" if value else "false"
    return (
        "10FB verification digest"
        f" | status={report['verification_digest_status']}"
        f" | source_verifier_status={report['source_verifier_status'] or 'none'}"
        f" | source_verifier_ok={bool_text(report['source_verifier_ok'])}"
        f" | source_digest_status={report['source_digest_status'] or 'none'}"
        f" | source_digest_ok={bool_text(report['source_digest_ok'])}"
        f" | source_bundle_status={report['source_bundle_status'] or 'none'}"
        f" | source_ok={bool_text(report['source_ok'])}"
        f" | source_summary_status={report['source_summary_status'] or 'none'}"
        f" | records_seen={report['records_seen']}"
        f" | records_valid={report['records_valid']}"
        f" | invalid_record_count={report['invalid_record_count']}"
        " | verified_record_hash_count="
        f"{report['verified_record_hash_count']}"
        " | recognized_signal_type_count="
        f"{report['recognized_signal_type_count']}"
        " | append_only_line_format_valid="
        f"{bool_text(report['append_only_line_format_valid'])}"
        f" | source_error_count={report['source_error_count']}"
        " | source_digest_text_valid="
        f"{bool_text(report['source_digest_text_valid'])}"
        " | gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def _valid_verification(
    verification_status: str = "digest_intact",
    *,
    source_digest_status: str = "verified_digest",
    source_bundle_status: str | None = None,
) -> dict:
    if verification_status == "invalid_digest":
        report = {
            "ok": False,
            "verifier_schema_version": "10EV.1",
            "verifier_type": "minimal_inert_ledger_status_digest_verifier",
            "verifier_scope": "inert_ledger_status_digest_verification_only",
            "verifier_decision_id": "",
            "source_digest_schema_version": "",
            "source_digest_decision_id": "",
            "source_digest_status": "",
            "source_digest_ok": False,
            "source_bundle_schema_version": "",
            "source_bundle_decision_id": "",
            "source_bundle_status": "",
            "source_ok": False,
            "source_summary_status": "",
            "ledger_path_supplied": False,
            "ledger_file_seen": False,
            "records_seen": 0,
            "records_valid": 0,
            "invalid_record_count": 0,
            "verified_record_hash_count": 0,
            "recognized_signal_types_seen": [],
            "recognized_signal_type_count": 0,
            "append_only_line_format_valid": False,
            "source_error_count": 0,
            "digest_text_valid": False,
            "verification_status": "invalid_digest",
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": VERIFIER_CLAIM_BOUNDARY,
            "errors": [SOURCE_INVALID_DIGEST_ERROR],
        }
    elif source_digest_status == "invalid_10ej_source":
        report = {
            "ok": True,
            "verifier_schema_version": "10EV.1",
            "verifier_type": "minimal_inert_ledger_status_digest_verifier",
            "verifier_scope": "inert_ledger_status_digest_verification_only",
            "verifier_decision_id": "",
            "source_digest_schema_version": "10EP.1",
            "source_digest_decision_id": "10EP-" + "c" * 32,
            "source_digest_status": "invalid_10ej_source",
            "source_digest_ok": False,
            "source_bundle_schema_version": "",
            "source_bundle_decision_id": "",
            "source_bundle_status": "",
            "source_ok": False,
            "source_summary_status": "",
            "ledger_path_supplied": False,
            "ledger_file_seen": False,
            "records_seen": 0,
            "records_valid": 0,
            "invalid_record_count": 0,
            "verified_record_hash_count": 0,
            "recognized_signal_types_seen": [],
            "recognized_signal_type_count": 0,
            "append_only_line_format_valid": False,
            "source_error_count": 0,
            "digest_text_valid": True,
            "verification_status": "digest_intact",
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
    else:
        verified = source_digest_status == "verified_digest"
        bundle_status = source_bundle_status or (
            "verified_bundle" if verified else "verification_failed_bundle"
        )
        invalid_bundle = bundle_status in INVALID_BUNDLE_STATUSES
        report = {
            "ok": True,
            "verifier_schema_version": "10EV.1",
            "verifier_type": "minimal_inert_ledger_status_digest_verifier",
            "verifier_scope": "inert_ledger_status_digest_verification_only",
            "verifier_decision_id": "",
            "source_digest_schema_version": "10EP.1",
            "source_digest_decision_id": "10EP-"
            + ("a" if verified else "b") * 32,
            "source_digest_status": source_digest_status,
            "source_digest_ok": verified,
            "source_bundle_schema_version": "10EJ.1",
            "source_bundle_decision_id": "10EJ-"
            + ("a" if verified else "b") * 32,
            "source_bundle_status": bundle_status,
            "source_ok": verified,
            "source_summary_status": (
                "verified"
                if verified
                else ("" if invalid_bundle else "verification_failed")
            ),
            "ledger_path_supplied": False if invalid_bundle else True,
            "ledger_file_seen": verified,
            "records_seen": 2 if verified else 0,
            "records_valid": 2 if verified else 0,
            "invalid_record_count": 0,
            "verified_record_hash_count": 2 if verified else 0,
            "recognized_signal_types_seen": (
                ["snapshot_hash_equality", "snapshot_id_equality"]
                if verified
                else []
            ),
            "recognized_signal_type_count": 2 if verified else 0,
            "append_only_line_format_valid": verified,
            "source_error_count": (
                0 if verified or invalid_bundle else 2
            ),
            "digest_text_valid": True,
            "verification_status": "digest_intact",
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

    report["verifier_decision_id"] = _verifier_decision_id(report)
    assert set(report) == VERIFICATION_FIELDS
    return report


def _recompute_verifier(report: dict) -> None:
    report["verifier_decision_id"] = _verifier_decision_id(report)


def _assert_inert(value: dict) -> None:
    for field in GATE_FLAGS:
        assert value[field] is False, field


def _assert_sanitized_digest(report: dict) -> None:
    assert report["ok"] is False
    assert report["verification_digest_schema_version"] == "10FB.1"
    assert report["verification_digest_type"] == (
        "minimal_inert_ledger_status_digest_verification_report"
    )
    assert report["verification_digest_scope"] == (
        "inert_ledger_status_digest_verification_report_only"
    )
    assert report["verification_digest_decision_id"] == (
        _verification_digest_decision_id(report)
    )
    assert report["source_verifier_schema_version"] == ""
    assert report["source_verifier_decision_id"] == ""
    assert report["source_verifier_status"] == ""
    assert report["source_verifier_ok"] is False
    assert report["source_digest_schema_version"] == ""
    assert report["source_digest_decision_id"] == ""
    assert report["source_digest_status"] == ""
    assert report["source_digest_ok"] is False
    assert report["source_bundle_schema_version"] == ""
    assert report["source_bundle_decision_id"] == ""
    assert report["source_bundle_status"] == ""
    assert report["source_ok"] is False
    assert report["source_summary_status"] == ""
    assert report["ledger_path_supplied"] is False
    assert report["ledger_file_seen"] is False
    assert report["records_seen"] == 0
    assert report["records_valid"] == 0
    assert report["invalid_record_count"] == 0
    assert report["verified_record_hash_count"] == 0
    assert report["recognized_signal_types_seen"] == []
    assert report["recognized_signal_type_count"] == 0
    assert report["append_only_line_format_valid"] is False
    assert report["source_error_count"] == 0
    assert report["source_digest_text_valid"] is False
    assert report["verification_digest_status"] == "invalid_10ev_source"
    assert report["verification_digest_text"] == _verification_digest_text(
        report
    )
    assert report["claim_boundary"] == REPORTER_CLAIM_BOUNDARY
    assert report["errors"] == [INVALID_10EV_ERROR]
    assert set(report) == OUTPUT_FIELDS
    _assert_inert(report)


def test_public_api_accepts_exactly_one_caller_supplied_input():
    signature = inspect.signature(
        create_minimal_inert_ledger_status_digest_verification_report
    )

    assert tuple(signature.parameters) == ("verification_report",)


def test_exporter_accepts_exactly_one_digest_report():
    signature = inspect.signature(
        export_minimal_inert_ledger_status_digest_verification_report
    )

    assert tuple(signature.parameters) == ("digest_report",)


def test_missing_10ev_report_fails_closed():
    report = create_minimal_inert_ledger_status_digest_verification_report(None)

    _assert_sanitized_digest(report)


@pytest.mark.parametrize("value", ([], "10EV", 7, True, object()))
def test_non_dict_10ev_report_fails_closed(value: object):
    report = create_minimal_inert_ledger_status_digest_verification_report(value)

    _assert_sanitized_digest(report)


def test_hostile_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = create_minimal_inert_ledger_status_digest_verification_report(
        _HostileDict(_valid_verification())
    )

    _assert_sanitized_digest(report)


def test_exact_valid_digest_intact_report_produces_verified_digest():
    source = _valid_verification()

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["verification_digest_schema_version"] == "10FB.1"
    assert report["verification_digest_type"] == (
        "minimal_inert_ledger_status_digest_verification_report"
    )
    assert report["verification_digest_scope"] == (
        "inert_ledger_status_digest_verification_report_only"
    )
    assert report["verification_digest_decision_id"] == (
        _verification_digest_decision_id(report)
    )
    assert report["source_verifier_schema_version"] == "10EV.1"
    assert report["source_verifier_decision_id"] == source[
        "verifier_decision_id"
    ]
    assert report["source_verifier_status"] == "digest_intact"
    assert report["source_verifier_ok"] is True
    assert report["source_digest_decision_id"] == source[
        "source_digest_decision_id"
    ]
    assert report["verification_digest_status"] == (
        "verified_verification_digest"
    )
    assert report["verification_digest_text"] == _verification_digest_text(
        report
    )
    assert report["errors"] == []
    assert report["claim_boundary"] == REPORTER_CLAIM_BOUNDARY
    assert set(report) == OUTPUT_FIELDS
    _assert_inert(report)


def test_exact_valid_invalid_digest_report_produces_non_verified_digest():
    source = _valid_verification("invalid_digest")

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is False
    assert report["source_verifier_schema_version"] == "10EV.1"
    assert report["source_verifier_decision_id"] == source[
        "verifier_decision_id"
    ]
    assert report["source_verifier_status"] == "invalid_digest"
    assert report["source_verifier_ok"] is False
    assert report["source_digest_schema_version"] == ""
    assert report["source_digest_decision_id"] == ""
    assert report["source_digest_status"] == ""
    assert report["source_digest_text_valid"] is False
    assert report["verification_digest_status"] == (
        "non_verified_verification_digest"
    )
    assert report["verification_digest_text"] == _verification_digest_text(
        report
    )
    assert report["errors"] == [NON_VERIFIED_ERROR]
    assert SOURCE_INVALID_DIGEST_ERROR not in json.dumps(report)
    assert report["verification_digest_decision_id"] == (
        _verification_digest_decision_id(report)
    )
    _assert_inert(report)


@pytest.mark.parametrize(
    ("source_digest_status", "source_bundle_status"),
    (
        ("verified_digest", "verified_bundle"),
        ("non_verified_digest", "verification_failed_bundle"),
        ("non_verified_digest", "invalid_10dx_source"),
        ("non_verified_digest", "invalid_10ed_source"),
        ("non_verified_digest", "mismatched_sources"),
        ("invalid_10ej_source", None),
    ),
)
def test_each_exact_digest_intact_10ev_variant_is_reported(
    source_digest_status: str,
    source_bundle_status: str | None,
):
    source = _valid_verification(
        source_digest_status=source_digest_status,
        source_bundle_status=source_bundle_status,
    )

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["source_digest_status"] == source_digest_status
    assert report["verification_digest_status"] == (
        "verified_verification_digest"
    )
    assert report["errors"] == []


@pytest.mark.parametrize("field", sorted(VERIFICATION_FIELDS))
def test_missing_required_10ev_field_fails_closed(field: str):
    source = _valid_verification()
    source.pop(field)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_unexpected_10ev_field_fails_closed():
    source = _valid_verification()
    source["future_field"] = "not authorized"

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("verifier_schema_version", "10EV.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10ev_identity_fails_closed(field: str, value: object):
    source = _valid_verification()
    source[field] = value
    if field != "claim_boundary":
        _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10EV-",
        "10EV-" + "a" * 31,
        "10EV-" + "a" * 33,
        "10EV-" + "A" * 32,
        "10EV-" + "g" * 32,
        "10EP-" + "a" * 32,
    ),
)
def test_malformed_verifier_decision_id_fails_closed(decision_id: str):
    source = _valid_verification()
    source["verifier_decision_id"] = decision_id

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_tampered_verifier_decision_id_fails_closed():
    source = _valid_verification()
    source["verifier_decision_id"] = "10EV-" + "f" * 32

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10EP-",
        "10EP-" + "a" * 31,
        "10EP-" + "a" * 33,
        "10EP-" + "A" * 32,
        "10EP-" + "g" * 32,
        "10EV-" + "a" * 32,
    ),
)
def test_wrong_source_digest_decision_id_syntax_fails_closed(
    decision_id: str,
):
    source = _valid_verification()
    source["source_digest_decision_id"] = decision_id
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_source_10ep_decision_id_is_syntax_only_and_not_recomputed():
    source = _valid_verification()
    source["source_digest_decision_id"] = "10EP-" + "0" * 32
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["source_digest_decision_id"] == "10EP-" + "0" * 32
    assert report["verification_digest_status"] == (
        "verified_verification_digest"
    )


@pytest.mark.parametrize(
    "field",
    (
        "ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "digest_text_valid",
    ),
)
def test_integer_bool_drift_fails_closed(field: str):
    source = _valid_verification()
    source[field] = 1
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(field: str):
    source = _valid_verification()
    source[field] = 0

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    "field",
    (
        "records_seen",
        "records_valid",
        "invalid_record_count",
        "verified_record_hash_count",
        "recognized_signal_type_count",
        "source_error_count",
    ),
)
@pytest.mark.parametrize("value", (-1, True))
def test_negative_or_bool_counts_fail_closed(field: str, value: object):
    source = _valid_verification()
    source[field] = value
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_invalid_recognized_signal_type_fails_closed():
    source = _valid_verification()
    source["recognized_signal_types_seen"] = ["future_unknown_signal"]
    source["recognized_signal_type_count"] = 1
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_mismatched_recognized_signal_type_count_fails_closed():
    source = _valid_verification()
    source["recognized_signal_type_count"] = 1
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "verifier_schema_version",
            type("StrSubclass", (str,), {})("10EV.1"),
        ),
        (
            "source_digest_decision_id",
            type("StrSubclass", (str,), {})("10EP-" + "a" * 32),
        ),
        ("records_seen", type("IntSubclass", (int,), {})(2)),
        (
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(["snapshot_id_equality"]),
        ),
        (
            "recognized_signal_types_seen",
            [type("StrSubclass", (str,), {})("snapshot_id_equality")],
        ),
        ("errors", type("ListSubclass", (list,), {})([])),
        ("errors", [type("StrSubclass", (str,), {})("raw error")]),
    ),
)
def test_list_str_and_int_subclasses_fail_closed(
    field: str,
    value: object,
):
    source = _valid_verification()
    source[field] = value
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_verification()
    value = source.pop("ok")
    source[type("StrSubclass", (str,), {})("ok")] = value

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", 3),
        ("records_valid", 1),
        ("invalid_record_count", 1),
        ("verified_record_hash_count", 1),
        ("ledger_path_supplied", False),
        ("ledger_file_seen", False),
        ("recognized_signal_types_seen", []),
        (
            "recognized_signal_types_seen",
            [
                "current_tile_id_equality",
                "snapshot_hash_equality",
                "snapshot_id_equality",
            ],
        ),
        ("source_ok", False),
        ("source_summary_status", "verification_failed"),
        ("source_digest_ok", False),
        ("source_digest_status", "non_verified_digest"),
        ("source_bundle_schema_version", "10EJ.2"),
        ("source_bundle_status", "future_bundle"),
        ("digest_text_valid", False),
    ),
)
def test_inconsistent_digest_intact_aggregate_fails_closed(
    field: str,
    value: object,
):
    source = _valid_verification()
    source[field] = value
    if field == "recognized_signal_types_seen":
        source["recognized_signal_type_count"] = len(value)
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_invalid_digest_requires_fully_sanitized_source_fields():
    source = _valid_verification("invalid_digest")
    source["records_seen"] = 1
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_verification_status_and_ok_mapping_is_exact():
    source = _valid_verification()
    source["verification_status"] = "invalid_digest"
    source["ok"] = False
    source["errors"] = [SOURCE_INVALID_DIGEST_ERROR]
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)


def test_source_error_mapping_is_exact():
    source = _valid_verification("invalid_digest")
    source["errors"] = ["raw 10EV source error"]
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_digest(report)
    assert "raw 10EV source error" not in json.dumps(report)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_reported(signal_type: str):
    source = _valid_verification()
    source.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": [signal_type],
            "recognized_signal_type_count": 1,
        }
    )
    _recompute_verifier(source)

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["recognized_signal_types_seen"] == [signal_type]
    assert report["recognized_signal_type_count"] == 1
    assert signal_type not in report["verification_digest_text"]


def test_caller_owned_lists_are_snapshot_detached_before_export():
    source = _valid_verification()

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    source["recognized_signal_types_seen"].clear()
    source["errors"].append("late raw 10EV error")

    assert report["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    assert report["errors"] == []
    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )
    assert "late raw 10EV error" not in exported


def test_reporter_does_not_mutate_caller_verification():
    source = _valid_verification(source_digest_status="non_verified_digest")
    before = json.loads(json.dumps(source))

    create_minimal_inert_ledger_status_digest_verification_report(source)

    assert source == before


def test_raw_10ev_errors_are_not_emitted():
    source = _valid_verification("invalid_digest")
    raw_error = source["errors"][0]

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    assert report["verification_digest_status"] == (
        "non_verified_verification_digest"
    )
    assert report["errors"] == [NON_VERIFIED_ERROR]
    assert raw_error not in serialized
    assert "raw_10ev_errors" not in report


def test_raw_hashes_cannot_appear_in_output():
    raw_hash = "f" * 64
    source = _valid_verification()
    source["verified_record_hashes"] = [raw_hash]

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    _assert_sanitized_digest(report)
    assert raw_hash not in serialized
    assert "verified_record_hashes" not in report


def test_raw_paths_cannot_appear_in_output():
    private_path = "C:\\private\\runtime_adapter_decisions.ndjson"
    source = _valid_verification()
    source["path"] = private_path

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    _assert_sanitized_digest(report)
    assert private_path not in serialized
    assert "ledger_path" not in report
    assert "path" not in report


@pytest.mark.parametrize(
    ("field", "secret"),
    (
        ("equality_signal_value", "private-signal-value"),
        ("equality_signal_type", "private-signal-type"),
    ),
)
def test_equality_signal_fields_cannot_appear_in_output(
    field: str,
    secret: str,
):
    source = _valid_verification()
    source[field] = secret

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    _assert_sanitized_digest(report)
    assert field not in report
    assert secret not in serialized


def test_output_contains_only_safe_aggregate_fields():
    sources = (
        _valid_verification(),
        _valid_verification(source_digest_status="non_verified_digest"),
        _valid_verification(source_digest_status="invalid_10ej_source"),
        _valid_verification("invalid_digest"),
        None,
    )
    for source in sources:
        report = create_minimal_inert_ledger_status_digest_verification_report(
            source
        )

        assert set(report) == OUTPUT_FIELDS
        assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
        _assert_inert(report)


def test_verification_digest_text_contains_no_forbidden_values():
    source = _valid_verification()

    report = create_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    text = report["verification_digest_text"]

    assert text == _verification_digest_text(report)
    assert source["verifier_decision_id"] not in text
    assert source["source_digest_decision_id"] not in text
    assert source["source_bundle_decision_id"] not in text
    assert not any(signal_type in text for signal_type in KNOWN_SIGNAL_TYPES)
    for forbidden in (
        "digest_text=",
        "raw_10ev_errors",
        "ledger_path=",
        "record_hash=",
        "equality_signal_value",
        "equality_signal_type",
        "agent_id=",
        "tile=",
        "route=",
        "destination=",
        "timing=",
        "co_presence=",
        "awareness=",
        "relationship=",
        "interaction=",
        "movement=",
        "map_lookup=",
        "event=",
        "npc_behavior=",
    ):
        assert forbidden not in text


def test_export_is_deterministic_sorted_json():
    report = create_minimal_inert_ledger_status_digest_verification_report(
        _valid_verification()
    )

    first = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )
    second = export_minimal_inert_ledger_status_digest_verification_report(
        dict(report)
    )

    assert first == second
    assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == report


def test_export_accepts_non_verified_verification_digest():
    report = create_minimal_inert_ledger_status_digest_verification_report(
        _valid_verification("invalid_digest")
    )

    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )

    assert json.loads(exported) == report
    assert NON_VERIFIED_ERROR in exported
    assert SOURCE_INVALID_DIGEST_ERROR not in exported


def test_export_accepts_sanitized_invalid_10ev_source_digest():
    report = create_minimal_inert_ledger_status_digest_verification_report(None)

    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )

    assert json.loads(exported) == report
    assert INVALID_10EV_ERROR in exported


def test_export_rejects_unexpected_or_forbidden_fields():
    report = create_minimal_inert_ledger_status_digest_verification_report(
        _valid_verification()
    )
    report["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10FB digest shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        def items(self):
            raise RuntimeError("caller-controlled items")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        create_minimal_inert_ledger_status_digest_verification_report(
            _valid_verification()
        )
    )

    with pytest.raises(ValueError, match="exact 10FB digest shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("verification_digest_schema_version", "10FB.2"),
        ("verification_digest_type", "future_reporter"),
        ("verification_digest_scope", "future_scope"),
        ("verification_digest_decision_id", "10FB-tainted"),
        ("source_verifier_schema_version", "10EV.2"),
        ("source_verifier_decision_id", "10EV-tainted"),
        ("source_verifier_status", "runtime_started"),
        ("source_verifier_ok", 1),
        ("source_digest_schema_version", "10EP.2"),
        ("source_digest_decision_id", "10EP-tainted"),
        ("source_digest_status", "future_digest"),
        ("source_digest_ok", 1),
        ("source_bundle_schema_version", "10EJ.2"),
        ("source_bundle_decision_id", "10EJ-tainted"),
        ("source_bundle_status", "future_bundle"),
        ("source_ok", 1),
        ("source_summary_status", "future_summary"),
        ("ledger_path_supplied", 1),
        ("records_seen", True),
        ("verified_record_hash_count", -1),
        ("recognized_signal_types_seen", ["future_unknown_signal"]),
        ("recognized_signal_type_count", 99),
        ("source_error_count", -1),
        ("source_digest_text_valid", False),
        ("verification_digest_status", "invalid_10ev_source"),
        ("verification_digest_text", "tainted text"),
        ("runtime_allowed", 0),
        ("errors", ["raw source error"]),
        ("claim_boundary", "expanded boundary"),
        (
            "source_digest_decision_id",
            type("StrSubclass", (str,), {})("10EP-" + "a" * 32),
        ),
        (
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(["snapshot_id_equality"]),
        ),
        ("source_error_count", type("IntSubclass", (int,), {})(0)),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = create_minimal_inert_ledger_status_digest_verification_report(
        _valid_verification()
    )
    report[field] = value
    if field not in {
        "verification_digest_decision_id",
        "verification_digest_text",
    }:
        report["verification_digest_text"] = _verification_digest_text(report)
    if field != "verification_digest_decision_id":
        report["verification_digest_decision_id"] = (
            _verification_digest_decision_id(report)
        )

    with pytest.raises(ValueError, match="exact 10FB digest shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


def test_gate_flags_are_false_on_success_and_failure():
    for report in (
        create_minimal_inert_ledger_status_digest_verification_report(
            _valid_verification()
        ),
        create_minimal_inert_ledger_status_digest_verification_report(
            _valid_verification("invalid_digest")
        ),
        create_minimal_inert_ledger_status_digest_verification_report(None),
    ):
        _assert_inert(report)


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


def test_module_has_no_backend_or_source_phase_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")

    forbidden_names = (
        "verify_minimal_inert_ledger_readback",
        "create_minimal_inert_ledger_summary_report",
        "create_minimal_inert_ledger_status_bundle_report",
        "create_minimal_inert_ledger_status_digest_report",
        "verify_minimal_inert_ledger_status_digest_report",
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_minimal_inert_ledger_status_bundle_reporter",
        "local_minimal_inert_ledger_status_digest_reporter",
        "local_minimal_inert_ledger_status_digest_verifier",
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
    assert "equality_signal_value" not in source
    assert "equality_signal_type" not in source


def test_caller_owned_lists_are_detached_before_content_validation():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_verification_snapshot"]
    assert validator is not None
    assert validator.index("signal_types = list(signal_types)") < validator.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "source_errors != expected_errors"
    )

    exporter = functions[
        "export_minimal_inert_ledger_status_digest_verification_report"
    ]
    assert exporter is not None
    assert exporter.index("signal_types = list(signal_types)") < exporter.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "report_errors != expected_errors"
    )
