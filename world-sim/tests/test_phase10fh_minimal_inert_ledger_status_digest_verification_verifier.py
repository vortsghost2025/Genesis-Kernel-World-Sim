"""Phase 10FH - inert ledger verification digest verifier tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_status_digest_reporter import (
    create_minimal_inert_ledger_status_digest_report as create_source_digest,
)
from backend.world.local_minimal_inert_ledger_status_digest_verifier import (
    verify_minimal_inert_ledger_status_digest_report as verify_source_digest,
)
from backend.world.local_minimal_inert_ledger_status_digest_verification_reporter import (
    create_minimal_inert_ledger_status_digest_verification_report as create_source_verification_digest,
)
from backend.world.local_minimal_inert_ledger_status_digest_verification_verifier import (
    export_minimal_inert_ledger_status_digest_verification_verifier_report,
    verify_minimal_inert_ledger_status_digest_verification_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_digest_verification_verifier.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

VERIFICATION_DIGEST_FIELDS = {
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

OUTPUT_FIELDS = {
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
    "verification_digest_text",
    "digest_text",
    "source_reporter_decision_id",
    "verified_record_hashes",
    "source_errors",
    "raw_10dx_errors",
    "raw_10ed_errors",
    "raw_10ej_errors",
    "raw_10ep_errors",
    "raw_10ev_errors",
    "raw_10fb_errors",
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

REPORTER_CLAIM_BOUNDARY = (
    "report one 10EV status digest verification only; no ledger access, "
    "digest text, raw hashes, raw source errors, write, repair, runtime "
    "action, daemon, scheduler, network, world-data promotion, movement, map "
    "lookup, route execution, event emission, NPC behavior, co-presence, "
    "awareness, relationship, interaction, or timing"
)

VERIFIER_CLAIM_BOUNDARY = (
    "verify one 10FB status digest verification report only; no ledger "
    "access, verification digest text, digest text, raw hashes, raw source "
    "errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

INVALID_10FB_ERROR = (
    "verification_digest_report is not a valid 10FB verification digest report"
)
INVALID_10EV_ERROR = (
    "verification_report is not a valid 10EV verification report"
)
NON_VERIFIED_ERROR = "source 10EV verification did not report digest_intact"
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
        "source_digest_text_valid": report["source_digest_text_valid"],
        "verification_digest_status": report["verification_digest_status"],
        "verification_digest_text": report["verification_digest_text"],
        "errors": report["errors"],
    }
    return "10FB-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _verification_digest_text(report: dict) -> str:
    def bool_text(value: bool) -> str:
        return "true" if value else "false"

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


def _verifier_decision_id(report: dict) -> str:
    material = {
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
        "source_digest_text_valid": report["source_digest_text_valid"],
        "source_verification_digest_text_valid": report[
            "source_verification_digest_text_valid"
        ],
        "verification_status": report["verification_status"],
        "errors": report["errors"],
    }
    return "10FH-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_10fb_report(
    status: str = "verified_verification_digest",
    *,
    source_digest_status: str = "verified_digest",
    source_bundle_status: str | None = None,
) -> dict:
    if status == "invalid_10ev_source":
        report = {
            "ok": False,
            "source_verifier_schema_version": "",
            "source_verifier_decision_id": "",
            "source_verifier_status": "",
            "source_verifier_ok": False,
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
            "source_digest_text_valid": False,
            "errors": [INVALID_10EV_ERROR],
        }
    elif status == "non_verified_verification_digest":
        report = {
            "ok": False,
            "source_verifier_schema_version": "10EV.1",
            "source_verifier_decision_id": "10EV-" + "b" * 32,
            "source_verifier_status": "invalid_digest",
            "source_verifier_ok": False,
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
            "source_digest_text_valid": False,
            "errors": [NON_VERIFIED_ERROR],
        }
    elif source_digest_status == "invalid_10ej_source":
        report = {
            "ok": True,
            "source_verifier_schema_version": "10EV.1",
            "source_verifier_decision_id": "10EV-" + "c" * 32,
            "source_verifier_status": "digest_intact",
            "source_verifier_ok": True,
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
            "source_digest_text_valid": True,
            "errors": [],
        }
    else:
        source_verified = source_digest_status == "verified_digest"
        bundle_status = source_bundle_status or (
            "verified_bundle"
            if source_verified
            else "verification_failed_bundle"
        )
        invalid_bundle = bundle_status in INVALID_BUNDLE_STATUSES
        report = {
            "ok": True,
            "source_verifier_schema_version": "10EV.1",
            "source_verifier_decision_id": "10EV-"
            + ("a" if source_verified else "b") * 32,
            "source_verifier_status": "digest_intact",
            "source_verifier_ok": True,
            "source_digest_schema_version": "10EP.1",
            "source_digest_decision_id": "10EP-"
            + ("a" if source_verified else "b") * 32,
            "source_digest_status": source_digest_status,
            "source_digest_ok": source_verified,
            "source_bundle_schema_version": "10EJ.1",
            "source_bundle_decision_id": "10EJ-"
            + ("a" if source_verified else "b") * 32,
            "source_bundle_status": bundle_status,
            "source_ok": source_verified,
            "source_summary_status": (
                "verified"
                if source_verified
                else ("" if invalid_bundle else "verification_failed")
            ),
            "ledger_path_supplied": False if invalid_bundle else True,
            "ledger_file_seen": source_verified,
            "records_seen": 2 if source_verified else 0,
            "records_valid": 2 if source_verified else 0,
            "invalid_record_count": 0,
            "verified_record_hash_count": 2 if source_verified else 0,
            "recognized_signal_types_seen": (
                ["snapshot_hash_equality", "snapshot_id_equality"]
                if source_verified
                else []
            ),
            "recognized_signal_type_count": 2 if source_verified else 0,
            "append_only_line_format_valid": source_verified,
            "source_error_count": (
                0 if source_verified or invalid_bundle else 2
            ),
            "source_digest_text_valid": True,
            "errors": [],
        }

    report.update(
        {
            "verification_digest_schema_version": "10FB.1",
            "verification_digest_type": (
                "minimal_inert_ledger_status_digest_verification_report"
            ),
            "verification_digest_scope": (
                "inert_ledger_status_digest_verification_report_only"
            ),
            "verification_digest_decision_id": "",
            "verification_digest_status": status,
            "verification_digest_text": "",
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": REPORTER_CLAIM_BOUNDARY,
        }
    )
    report["verification_digest_text"] = _verification_digest_text(report)
    report["verification_digest_decision_id"] = (
        _verification_digest_decision_id(report)
    )
    assert set(report) == VERIFICATION_DIGEST_FIELDS
    return report


def _recompute_10fb(report: dict) -> None:
    report["verification_digest_text"] = _verification_digest_text(report)
    report["verification_digest_decision_id"] = (
        _verification_digest_decision_id(report)
    )


def _recompute_10fh(report: dict) -> None:
    report["verifier_decision_id"] = _verifier_decision_id(report)


def _assert_inert(value: dict) -> None:
    for field in GATE_FLAGS:
        assert value[field] is False, field


def _assert_sanitized_verification(report: dict) -> None:
    assert report["ok"] is False
    assert report["verifier_schema_version"] == "10FH.1"
    assert report["verifier_type"] == (
        "minimal_inert_ledger_status_digest_verification_verifier"
    )
    assert report["verifier_scope"] == (
        "inert_ledger_status_digest_verification_verification_only"
    )
    assert report["verifier_decision_id"] == _verifier_decision_id(report)
    assert report["source_verification_digest_schema_version"] == ""
    assert report["source_verification_digest_decision_id"] == ""
    assert report["source_verification_digest_status"] == ""
    assert report["source_verification_digest_ok"] is False
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
    assert report["source_verification_digest_text_valid"] is False
    assert report["verification_status"] == "invalid_digest"
    assert report["claim_boundary"] == VERIFIER_CLAIM_BOUNDARY
    assert report["errors"] == [INVALID_10FB_ERROR]
    assert set(report) == OUTPUT_FIELDS
    _assert_inert(report)


def test_public_api_accepts_exactly_one_caller_supplied_input():
    signature = inspect.signature(
        verify_minimal_inert_ledger_status_digest_verification_report
    )

    assert tuple(signature.parameters) == ("verification_digest_report",)


def test_exporter_accepts_exactly_one_verification_report():
    signature = inspect.signature(
        export_minimal_inert_ledger_status_digest_verification_verifier_report
    )

    assert tuple(signature.parameters) == ("verification_report",)


def test_missing_10fb_report_fails_closed():
    report = verify_minimal_inert_ledger_status_digest_verification_report(None)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize("value", ([], "10FB", 7, True, object()))
def test_non_dict_10fb_report_fails_closed(value: object):
    report = verify_minimal_inert_ledger_status_digest_verification_report(value)

    _assert_sanitized_verification(report)


def test_hostile_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        _HostileDict(_valid_10fb_report())
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    "status",
    (
        "verified_verification_digest",
        "non_verified_verification_digest",
        "invalid_10ev_source",
    ),
)
def test_each_exact_valid_10fb_status_verifies_as_digest_intact(status: str):
    source = _valid_10fb_report(status)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["verifier_schema_version"] == "10FH.1"
    assert report["verifier_type"] == (
        "minimal_inert_ledger_status_digest_verification_verifier"
    )
    assert report["verifier_scope"] == (
        "inert_ledger_status_digest_verification_verification_only"
    )
    assert report["verifier_decision_id"] == _verifier_decision_id(report)
    assert report["source_verification_digest_schema_version"] == "10FB.1"
    assert report["source_verification_digest_decision_id"] == source[
        "verification_digest_decision_id"
    ]
    assert report["source_verification_digest_status"] == status
    assert report["source_verification_digest_ok"] is source["ok"]
    assert report["source_verifier_decision_id"] == source[
        "source_verifier_decision_id"
    ]
    assert report["source_digest_decision_id"] == source[
        "source_digest_decision_id"
    ]
    assert report["source_verification_digest_text_valid"] is True
    assert report["verification_status"] == "digest_intact"
    assert report["errors"] == []
    assert report["claim_boundary"] == VERIFIER_CLAIM_BOUNDARY
    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_real_source_chain_interoperates_for_all_three_10fb_statuses():
    source_digest = create_source_digest(None)
    source_verification = verify_source_digest(source_digest)
    actual_reports = (
        create_source_verification_digest(source_verification),
        create_source_verification_digest(verify_source_digest(None)),
        create_source_verification_digest(None),
    )

    assert [
        report["verification_digest_status"] for report in actual_reports
    ] == [
        "verified_verification_digest",
        "non_verified_verification_digest",
        "invalid_10ev_source",
    ]
    for source in actual_reports:
        report = verify_minimal_inert_ledger_status_digest_verification_report(
            source
        )

        assert report["ok"] is True
        assert report["verification_status"] == "digest_intact"
        assert report["source_verification_digest_decision_id"] == source[
            "verification_digest_decision_id"
        ]


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
def test_each_exact_verified_10fb_source_variant_is_accepted(
    source_digest_status: str,
    source_bundle_status: str | None,
):
    source = _valid_10fb_report(
        source_digest_status=source_digest_status,
        source_bundle_status=source_bundle_status,
    )

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["source_digest_status"] == source_digest_status
    assert report["verification_status"] == "digest_intact"


@pytest.mark.parametrize("field", sorted(VERIFICATION_DIGEST_FIELDS))
def test_missing_required_10fb_field_fails_closed(field: str):
    source = _valid_10fb_report()
    source.pop(field)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_unexpected_10fb_field_fails_closed():
    source = _valid_10fb_report()
    source["future_field"] = "not authorized"

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("verification_digest_schema_version", "10FB.2"),
        ("verification_digest_type", "future_reporter"),
        ("verification_digest_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10fb_identity_fails_closed(field: str, value: object):
    source = _valid_10fb_report()
    source[field] = value
    if field != "claim_boundary":
        _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10FB-",
        "10FB-" + "a" * 31,
        "10FB-" + "a" * 33,
        "10FB-" + "A" * 32,
        "10FB-" + "g" * 32,
        "10EV-" + "a" * 32,
    ),
)
def test_malformed_verification_digest_decision_id_fails_closed(
    decision_id: str,
):
    source = _valid_10fb_report()
    source["verification_digest_decision_id"] = decision_id

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_tampered_verification_digest_decision_id_fails_closed():
    source = _valid_10fb_report()
    source["verification_digest_decision_id"] = "10FB-" + "f" * 32

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


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
def test_wrong_source_verifier_decision_id_syntax_fails_closed(
    decision_id: str,
):
    source = _valid_10fb_report()
    source["source_verifier_decision_id"] = decision_id
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


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
    source = _valid_10fb_report()
    source["source_digest_decision_id"] = decision_id
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_source_10ev_and_10ep_ids_are_syntax_only_and_not_recomputed():
    source = _valid_10fb_report()
    source["source_verifier_decision_id"] = "10EV-" + "0" * 32
    source["source_digest_decision_id"] = "10EP-" + "0" * 32
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["source_verifier_decision_id"] == "10EV-" + "0" * 32
    assert report["source_digest_decision_id"] == "10EP-" + "0" * 32


@pytest.mark.parametrize(
    "field",
    (
        "ok",
        "source_verifier_ok",
        "source_digest_ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
        "source_digest_text_valid",
    ),
)
def test_integer_bool_drift_fails_closed(field: str):
    source = _valid_10fb_report()
    source[field] = 1
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(field: str):
    source = _valid_10fb_report()
    source[field] = 0

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


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
    source = _valid_10fb_report()
    source[field] = value
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_invalid_recognized_signal_type_fails_closed():
    source = _valid_10fb_report()
    source["recognized_signal_types_seen"] = ["future_unknown_signal"]
    source["recognized_signal_type_count"] = 1
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_mismatched_recognized_signal_type_count_fails_closed():
    source = _valid_10fb_report()
    source["recognized_signal_type_count"] = 1
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "verification_digest_schema_version",
            type("StrSubclass", (str,), {})("10FB.1"),
        ),
        (
            "source_verifier_decision_id",
            type("StrSubclass", (str,), {})("10EV-" + "a" * 32),
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
        (
            "verification_digest_text",
            type("StrSubclass", (str,), {})("tainted text"),
        ),
    ),
)
def test_list_str_and_int_subclasses_fail_closed(
    field: str,
    value: object,
):
    source = _valid_10fb_report()
    source[field] = value
    if field != "verification_digest_text":
        _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_10fb_report()
    value = source.pop("ok")
    source[type("StrSubclass", (str,), {})("ok")] = value

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


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
        ("source_digest_text_valid", False),
    ),
)
def test_inconsistent_verified_aggregate_fails_closed(
    field: str,
    value: object,
):
    source = _valid_10fb_report()
    source[field] = value
    if field == "recognized_signal_types_seen":
        source["recognized_signal_type_count"] = len(value)
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    "status",
    ("non_verified_verification_digest", "invalid_10ev_source"),
)
def test_failure_statuses_require_exact_sanitized_source_aggregate(status: str):
    source = _valid_10fb_report(status)
    source["records_seen"] = 1
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_verification_digest_status_and_ok_mapping_is_exact():
    source = _valid_10fb_report()
    source["verification_digest_status"] = "non_verified_verification_digest"
    source["ok"] = False
    source["errors"] = [NON_VERIFIED_ERROR]
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)


def test_source_error_mapping_is_exact():
    source = _valid_10fb_report("invalid_10ev_source")
    source["errors"] = ["raw 10FB source error"]
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(report)
    assert "raw 10FB source error" not in json.dumps(report)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_verified(signal_type: str):
    source = _valid_10fb_report()
    source.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": [signal_type],
            "recognized_signal_type_count": 1,
        }
    )
    _recompute_10fb(source)

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    assert report["ok"] is True
    assert report["recognized_signal_types_seen"] == [signal_type]
    assert report["recognized_signal_type_count"] == 1


def test_caller_owned_lists_are_snapshot_detached_before_export():
    source = _valid_10fb_report()

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    source["recognized_signal_types_seen"].clear()
    source["errors"].append("late raw 10FB error")

    assert report["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    assert report["errors"] == []
    exported = (
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )
    )
    assert "late raw 10FB error" not in exported


def test_verifier_does_not_mutate_caller_report():
    source = _valid_10fb_report(
        source_digest_status="non_verified_digest"
    )
    before = json.loads(json.dumps(source))

    verify_minimal_inert_ledger_status_digest_verification_report(source)

    assert source == before


@pytest.mark.parametrize(
    "status",
    ("non_verified_verification_digest", "invalid_10ev_source"),
)
def test_raw_10fb_errors_are_not_emitted(status: str):
    source = _valid_10fb_report(status)
    raw_error = source["errors"][0]

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    assert report["verification_status"] == "digest_intact"
    assert report["errors"] == []
    assert raw_error not in serialized
    assert "raw_10fb_errors" not in report


@pytest.mark.parametrize(
    ("field", "secret"),
    (
        ("verified_record_hashes", "f" * 64),
        ("record_hash", "e" * 64),
        ("path", "C:\\private\\runtime_adapter_decisions.ndjson"),
        ("ledger_path", "C:\\private\\ledger.ndjson"),
        ("equality_signal_value", "private-signal-value"),
        ("equality_signal_type", "private-signal-type"),
        ("records", "private-record-body"),
    ),
)
def test_forbidden_source_values_cannot_appear_in_output(
    field: str,
    secret: object,
):
    source = _valid_10fb_report()
    source[field] = secret

    report = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )
    serialized = json.dumps(report)

    _assert_sanitized_verification(report)
    assert field not in report
    assert secret not in serialized


def test_output_contains_only_safe_aggregate_fields():
    sources = (
        _valid_10fb_report(),
        _valid_10fb_report(
            source_digest_status="non_verified_digest"
        ),
        _valid_10fb_report(source_digest_status="invalid_10ej_source"),
        _valid_10fb_report("non_verified_verification_digest"),
        _valid_10fb_report("invalid_10ev_source"),
        None,
    )
    for source in sources:
        report = verify_minimal_inert_ledger_status_digest_verification_report(
            source
        )

        assert set(report) == OUTPUT_FIELDS
        assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
        _assert_inert(report)


def test_verification_digest_text_is_validated_but_not_emitted():
    source = _valid_10fb_report()
    original_text = source["verification_digest_text"]

    valid = verify_minimal_inert_ledger_status_digest_verification_report(source)

    assert valid["ok"] is True
    assert "verification_digest_text" not in valid
    assert original_text not in json.dumps(valid)

    source["verification_digest_text"] = "tampered safe-looking text"
    source["verification_digest_decision_id"] = (
        _verification_digest_decision_id(source)
    )
    invalid = verify_minimal_inert_ledger_status_digest_verification_report(
        source
    )

    _assert_sanitized_verification(invalid)
    assert "tampered safe-looking text" not in json.dumps(invalid)


def test_export_is_deterministic_sorted_json():
    report = verify_minimal_inert_ledger_status_digest_verification_report(
        _valid_10fb_report()
    )

    first = (
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )
    )
    second = (
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            dict(report)
        )
    )

    assert first == second
    assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == report


@pytest.mark.parametrize(
    "status",
    (
        "verified_verification_digest",
        "non_verified_verification_digest",
        "invalid_10ev_source",
    ),
)
def test_export_accepts_each_digest_intact_source_status(status: str):
    report = verify_minimal_inert_ledger_status_digest_verification_report(
        _valid_10fb_report(status)
    )

    exported = (
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )
    )

    assert json.loads(exported) == report


def test_export_accepts_sanitized_invalid_digest():
    report = verify_minimal_inert_ledger_status_digest_verification_report(None)

    exported = (
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )
    )

    assert json.loads(exported) == report
    assert INVALID_10FB_ERROR in exported


def test_export_rejects_unexpected_or_forbidden_fields():
    report = verify_minimal_inert_ledger_status_digest_verification_report(
        _valid_10fb_report()
    )
    report["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10FH verifier shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        def items(self):
            raise RuntimeError("caller-controlled items")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        verify_minimal_inert_ledger_status_digest_verification_report(
            _valid_10fb_report()
        )
    )

    with pytest.raises(ValueError, match="exact 10FH verifier shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("verifier_schema_version", "10FH.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("verifier_decision_id", "10FH-tainted"),
        ("source_verification_digest_schema_version", "10FB.2"),
        ("source_verification_digest_decision_id", "10FB-tainted"),
        ("source_verification_digest_status", "future_digest"),
        ("source_verification_digest_ok", 1),
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
        ("source_verification_digest_text_valid", False),
        ("verification_status", "invalid_digest"),
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
    report = verify_minimal_inert_ledger_status_digest_verification_report(
        _valid_10fb_report()
    )
    report[field] = value
    if field != "verifier_decision_id":
        _recompute_10fh(report)

    with pytest.raises(ValueError, match="exact 10FH verifier shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_report(
            report
        )


def test_gate_flags_are_false_on_success_and_failure():
    for report in (
        verify_minimal_inert_ledger_status_digest_verification_report(
            _valid_10fb_report()
        ),
        verify_minimal_inert_ledger_status_digest_verification_report(
            _valid_10fb_report("non_verified_verification_digest")
        ),
        verify_minimal_inert_ledger_status_digest_verification_report(None),
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
        "create_minimal_inert_ledger_status_digest_verification_report",
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_minimal_inert_ledger_status_bundle_reporter",
        "local_minimal_inert_ledger_status_digest_reporter",
        "local_minimal_inert_ledger_status_digest_verifier",
        "local_minimal_inert_ledger_status_digest_verification_reporter",
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

    validator = functions["_validated_digest_snapshot"]
    assert validator is not None
    assert validator.index("signal_types = list(signal_types)") < validator.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "source_errors != expected_errors"
    )

    exporter = functions[
        "export_minimal_inert_ledger_status_digest_verification_verifier_report"
    ]
    assert exporter is not None
    assert exporter.index("signal_types = list(signal_types)") < exporter.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "report_errors != expected_errors"
    )


def test_plain_dictionary_snapshot_precedes_key_type_validation():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_digest_snapshot"]
    assert validator is not None
    assert validator.index("snapshot = dict(source)") < validator.index(
        "type(key) is not str for key in snapshot"
    )

    exporter = functions[
        "export_minimal_inert_ledger_status_digest_verification_verifier_report"
    ]
    assert exporter is not None
    assert exporter.index("report = dict(verification_report)") < exporter.index(
        "type(key) is not str for key in report"
    )
