"""Phase 10FN - inert ledger verification-verifier status reporter tests."""

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
    verify_minimal_inert_ledger_status_digest_verification_report as verify_source_verification_digest,
)
from backend.world.local_minimal_inert_ledger_status_digest_verification_verifier_status_reporter import (
    create_minimal_inert_ledger_status_digest_verification_verifier_status_report,
    export_minimal_inert_ledger_status_digest_verification_verifier_status_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_digest_verification_verifier_status_reporter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

SOURCE_FIELDS = {
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

OUTPUT_FIELDS = {
    "ok",
    "status_report_schema_version",
    "status_report_type",
    "status_report_scope",
    "status_report_decision_id",
    "source_verifier_schema_version",
    "source_verifier_decision_id",
    "source_verifier_status",
    "source_verifier_ok",
    "status_report_status",
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

FORBIDDEN_OUTPUT_FIELDS = SOURCE_FIELDS - {
    "ok",
    "source_verifier_schema_version",
    "source_verifier_decision_id",
    "source_verifier_status",
    "source_verifier_ok",
    *GATE_FLAGS,
    "claim_boundary",
    "errors",
}
FORBIDDEN_OUTPUT_FIELDS.update(
    {
        "verification_digest_text",
        "digest_text",
        "verified_record_hashes",
        "source_errors",
        "raw_10dx_errors",
        "raw_10ed_errors",
        "raw_10ej_errors",
        "raw_10ep_errors",
        "raw_10ev_errors",
        "raw_10fb_errors",
        "raw_10fh_errors",
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
)

VERIFIER_CLAIM_BOUNDARY = (
    "verify one 10FB status digest verification report only; no ledger "
    "access, verification digest text, digest text, raw hashes, raw source "
    "errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

STATUS_REPORT_CLAIM_BOUNDARY = (
    "report one 10FH verification verifier status only; no ledger access, "
    "verification digest text, digest text, raw hashes, raw source errors, "
    "write, repair, runtime action, daemon, scheduler, network, world-data "
    "promotion, movement, map lookup, route execution, event emission, NPC "
    "behavior, co-presence, awareness, relationship, interaction, or timing"
)

INVALID_10FH_ERROR = (
    "verification_verifier_report is not a valid 10FH verification report"
)
INVALID_10FB_ERROR = (
    "verification_digest_report is not a valid 10FB verification digest report"
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _source_verifier_decision_id(report: dict) -> str:
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
        "source_digest_schema_version": report["source_digest_schema_version"],
        "source_digest_decision_id": report["source_digest_decision_id"],
        "source_digest_status": report["source_digest_status"],
        "source_digest_ok": report["source_digest_ok"],
        "source_bundle_schema_version": report["source_bundle_schema_version"],
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
        "recognized_signal_types_seen": report["recognized_signal_types_seen"],
        "recognized_signal_type_count": report["recognized_signal_type_count"],
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


def _status_report_decision_id(report: dict) -> str:
    material = {
        "status_report_schema_version": report["status_report_schema_version"],
        "status_report_scope": report["status_report_scope"],
        "source_verifier_schema_version": report[
            "source_verifier_schema_version"
        ],
        "source_verifier_decision_id": report["source_verifier_decision_id"],
        "source_verifier_status": report["source_verifier_status"],
        "source_verifier_ok": report["source_verifier_ok"],
        "status_report_status": report["status_report_status"],
        "errors": report["errors"],
    }
    return "10FN-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_10fh_report(
    source_status: str = "verified_verification_digest",
    *,
    verification_status: str = "digest_intact",
) -> dict:
    if verification_status == "invalid_digest":
        source = {
            "ok": False,
            "source_verification_digest_schema_version": "",
            "source_verification_digest_decision_id": "",
            "source_verification_digest_status": "",
            "source_verification_digest_ok": False,
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
            "source_verification_digest_text_valid": False,
            "verification_status": "invalid_digest",
            "errors": [INVALID_10FB_ERROR],
        }
    elif source_status == "invalid_10ev_source":
        source = {
            "ok": True,
            "source_verification_digest_schema_version": "10FB.1",
            "source_verification_digest_decision_id": "10FB-" + "c" * 32,
            "source_verification_digest_status": source_status,
            "source_verification_digest_ok": False,
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
            "source_verification_digest_text_valid": True,
            "verification_status": "digest_intact",
            "errors": [],
        }
    elif source_status == "non_verified_verification_digest":
        source = {
            "ok": True,
            "source_verification_digest_schema_version": "10FB.1",
            "source_verification_digest_decision_id": "10FB-" + "b" * 32,
            "source_verification_digest_status": source_status,
            "source_verification_digest_ok": False,
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
            "source_verification_digest_text_valid": True,
            "verification_status": "digest_intact",
            "errors": [],
        }
    else:
        source = {
            "ok": True,
            "source_verification_digest_schema_version": "10FB.1",
            "source_verification_digest_decision_id": "10FB-" + "a" * 32,
            "source_verification_digest_status": source_status,
            "source_verification_digest_ok": True,
            "source_verifier_schema_version": "10EV.1",
            "source_verifier_decision_id": "10EV-" + "a" * 32,
            "source_verifier_status": "digest_intact",
            "source_verifier_ok": True,
            "source_digest_schema_version": "10EP.1",
            "source_digest_decision_id": "10EP-" + "a" * 32,
            "source_digest_status": "verified_digest",
            "source_digest_ok": True,
            "source_bundle_schema_version": "10EJ.1",
            "source_bundle_decision_id": "10EJ-" + "a" * 32,
            "source_bundle_status": "verified_bundle",
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
            "source_digest_text_valid": True,
            "source_verification_digest_text_valid": True,
            "verification_status": "digest_intact",
            "errors": [],
        }

    source.update(
        {
            "verifier_schema_version": "10FH.1",
            "verifier_type": (
                "minimal_inert_ledger_status_digest_verification_verifier"
            ),
            "verifier_scope": (
                "inert_ledger_status_digest_verification_verification_only"
            ),
            "verifier_decision_id": "",
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": VERIFIER_CLAIM_BOUNDARY,
        }
    )
    source["verifier_decision_id"] = _source_verifier_decision_id(source)
    assert set(source) == SOURCE_FIELDS
    return source


def _recompute_10fh(report: dict) -> None:
    report["verifier_decision_id"] = _source_verifier_decision_id(report)


def _recompute_10fn(report: dict) -> None:
    report["status_report_decision_id"] = _status_report_decision_id(report)


def _assert_inert(value: dict) -> None:
    for field in GATE_FLAGS:
        assert value[field] is False, field


def _assert_sanitized_invalid_report(report: dict) -> None:
    assert report == {
        "ok": False,
        "status_report_schema_version": "10FN.1",
        "status_report_type": (
            "minimal_inert_ledger_status_digest_verification_verifier_status_report"
        ),
        "status_report_scope": (
            "inert_ledger_status_digest_verification_verifier_status_report_only"
        ),
        "status_report_decision_id": report["status_report_decision_id"],
        "source_verifier_schema_version": "",
        "source_verifier_decision_id": "",
        "source_verifier_status": "",
        "source_verifier_ok": False,
        "status_report_status": "invalid_report",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": STATUS_REPORT_CLAIM_BOUNDARY,
        "errors": [INVALID_10FH_ERROR],
    }
    assert report["status_report_decision_id"] == _status_report_decision_id(
        report
    )
    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_public_api_accepts_exactly_one_caller_supplied_input():
    signature = inspect.signature(
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report
    )

    assert tuple(signature.parameters) == ("verification_verifier_report",)


def test_exporter_accepts_exactly_one_status_report():
    signature = inspect.signature(
        export_minimal_inert_ledger_status_digest_verification_verifier_status_report
    )

    assert tuple(signature.parameters) == ("status_report",)


@pytest.mark.parametrize("value", (None, [], "10FH", 7, True, object()))
def test_missing_or_non_dict_10fh_report_fails_closed(value: object):
    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            value
        )
    )

    _assert_sanitized_invalid_report(report)


def test_hostile_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        get_called = False
        iter_called = False

        def get(self, key: object, default: object = None) -> object:
            type(self).get_called = True
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _HostileDict(_valid_10fh_report())
        )
    )

    _assert_sanitized_invalid_report(report)
    assert _HostileDict.get_called is False
    assert _HostileDict.iter_called is False


@pytest.mark.parametrize(
    ("source_status", "verification_status"),
    (
        ("verified_verification_digest", "digest_intact"),
        ("non_verified_verification_digest", "digest_intact"),
        ("invalid_10ev_source", "digest_intact"),
        ("verified_verification_digest", "invalid_digest"),
    ),
)
def test_each_exact_valid_10fh_artifact_produces_verified_status_report(
    source_status: str,
    verification_status: str,
):
    source = _valid_10fh_report(
        source_status,
        verification_status=verification_status,
    )

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    assert report == {
        "ok": True,
        "status_report_schema_version": "10FN.1",
        "status_report_type": (
            "minimal_inert_ledger_status_digest_verification_verifier_status_report"
        ),
        "status_report_scope": (
            "inert_ledger_status_digest_verification_verifier_status_report_only"
        ),
        "status_report_decision_id": report["status_report_decision_id"],
        "source_verifier_schema_version": "10FH.1",
        "source_verifier_decision_id": source["verifier_decision_id"],
        "source_verifier_status": source["verification_status"],
        "source_verifier_ok": source["ok"],
        "status_report_status": "verified",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": STATUS_REPORT_CLAIM_BOUNDARY,
        "errors": [],
    }
    assert report["status_report_decision_id"] == _status_report_decision_id(
        report
    )
    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_real_10fh_producer_interoperates_for_intact_and_invalid_digest():
    source_digest = create_source_digest(None)
    source_verification = verify_source_digest(source_digest)
    source_verification_digest = create_source_verification_digest(
        source_verification
    )
    actual_reports = (
        verify_source_verification_digest(source_verification_digest),
        verify_source_verification_digest(None),
    )

    assert [report["verification_status"] for report in actual_reports] == [
        "digest_intact",
        "invalid_digest",
    ]
    for source in actual_reports:
        report = (
            create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
                source
            )
        )

        assert report["ok"] is True
        assert report["status_report_status"] == "verified"
        assert report["source_verifier_decision_id"] == source[
            "verifier_decision_id"
        ]


@pytest.mark.parametrize(
    ("source_digest_status", "source_bundle_status"),
    (
        ("non_verified_digest", "verification_failed_bundle"),
        ("non_verified_digest", "invalid_10dx_source"),
        ("non_verified_digest", "invalid_10ed_source"),
        ("non_verified_digest", "mismatched_sources"),
        ("invalid_10ej_source", ""),
    ),
)
def test_each_nested_valid_10fh_source_variant_is_accepted(
    source_digest_status: str,
    source_bundle_status: str,
):
    source = _valid_10fh_report()
    source["source_digest_status"] = source_digest_status
    source["source_digest_ok"] = False

    if source_digest_status == "invalid_10ej_source":
        source.update(
            {
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
            }
        )
    elif source_bundle_status in {
        "invalid_10dx_source",
        "invalid_10ed_source",
        "mismatched_sources",
    }:
        source.update(
            {
                "source_bundle_status": source_bundle_status,
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
            }
        )
    else:
        source.update(
            {
                "source_bundle_status": source_bundle_status,
                "source_ok": False,
                "source_summary_status": "verification_failed",
                "records_valid": 0,
                "invalid_record_count": 2,
                "verified_record_hash_count": 0,
                "recognized_signal_types_seen": [],
                "recognized_signal_type_count": 0,
                "source_error_count": 2,
            }
        )
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    assert report["ok"] is True
    assert report["status_report_status"] == "verified"


@pytest.mark.parametrize("field", sorted(SOURCE_FIELDS))
def test_missing_required_10fh_field_fails_closed(field: str):
    source = _valid_10fh_report()
    source.pop(field)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


def test_unexpected_10fh_field_fails_closed():
    source = _valid_10fh_report()
    source["future_field"] = "not authorized"

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("verifier_schema_version", "10FH.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10fh_identity_fails_closed(field: str, value: object):
    source = _valid_10fh_report()
    source[field] = value
    if field != "claim_boundary":
        _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10FH-",
        "10FH-" + "a" * 31,
        "10FH-" + "a" * 33,
        "10FH-" + "A" * 32,
        "10FH-" + "g" * 32,
        "10FB-" + "a" * 32,
    ),
)
def test_malformed_10fh_decision_id_fails_closed(decision_id: str):
    source = _valid_10fh_report()
    source["verifier_decision_id"] = decision_id

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


def test_tampered_10fh_decision_id_fails_closed():
    source = _valid_10fh_report()
    source["verifier_decision_id"] = "10FH-" + "f" * 32

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "prefix", "other_prefix"),
    (
        ("source_verification_digest_decision_id", "10FB-", "10EV-"),
        ("source_verifier_decision_id", "10EV-", "10EP-"),
        ("source_digest_decision_id", "10EP-", "10EJ-"),
        ("source_bundle_decision_id", "10EJ-", "10EP-"),
    ),
)
@pytest.mark.parametrize("suffix", ("", "a" * 31, "a" * 33, "A" * 32, "g" * 32))
def test_malformed_upstream_decision_ids_fail_closed(
    field: str,
    prefix: str,
    other_prefix: str,
    suffix: str,
):
    source = _valid_10fh_report()
    source[field] = (other_prefix + "a" * 32) if not suffix else prefix + suffix
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


def test_upstream_ids_are_syntax_only_and_not_recomputed_or_emitted():
    source = _valid_10fh_report()
    source["source_verification_digest_decision_id"] = "10FB-" + "0" * 32
    source["source_verifier_decision_id"] = "10EV-" + "1" * 32
    source["source_digest_decision_id"] = "10EP-" + "2" * 32
    source["source_bundle_decision_id"] = "10EJ-" + "3" * 32
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )
    serialized = json.dumps(report)

    assert report["ok"] is True
    for decision_id in (
        source["source_verification_digest_decision_id"],
        source["source_verifier_decision_id"],
        source["source_digest_decision_id"],
        source["source_bundle_decision_id"],
    ):
        assert decision_id not in serialized


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_integer_bool_drift_fails_closed(field: str):
    source = _valid_10fh_report()
    source[field] = 1
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(field: str):
    source = _valid_10fh_report()
    source[field] = 0
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


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
    source = _valid_10fh_report()
    source[field] = value
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "verifier_schema_version",
            type("StrSubclass", (str,), {})("10FH.1"),
        ),
        (
            "source_verification_digest_decision_id",
            type("StrSubclass", (str,), {})("10FB-" + "a" * 32),
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
    ),
)
def test_list_str_and_int_subclasses_fail_closed(field: str, value: object):
    source = _valid_10fh_report()
    source[field] = value
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_10fh_report()
    value = source.pop("ok")
    source[type("StrSubclass", (str,), {})("ok")] = value

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


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
        ("source_ok", False),
        ("source_summary_status", "verification_failed"),
        ("source_digest_ok", False),
        ("source_digest_status", "non_verified_digest"),
        ("source_bundle_schema_version", "10EJ.2"),
        ("source_bundle_status", "future_bundle"),
        ("source_digest_text_valid", False),
        ("source_verification_digest_text_valid", False),
        ("verification_status", "invalid_digest"),
        ("ok", False),
    ),
)
def test_inconsistent_digest_intact_aggregate_fails_closed(
    field: str,
    value: object,
):
    source = _valid_10fh_report()
    source[field] = value
    if field == "recognized_signal_types_seen":
        source["recognized_signal_type_count"] = len(value)
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    _assert_sanitized_invalid_report(report)


def test_invalid_digest_requires_exact_sanitized_source_aggregate_and_error():
    source = _valid_10fh_report(verification_status="invalid_digest")
    source["records_seen"] = 1
    source["errors"] = ["raw 10FH error"]
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )
    serialized = json.dumps(report)

    _assert_sanitized_invalid_report(report)
    assert "raw 10FH error" not in serialized


def test_invalid_signal_type_order_or_count_fails_closed():
    for signal_types, count in (
        (["future_unknown_signal"], 1),
        (["snapshot_id_equality", "snapshot_hash_equality"], 2),
        (["snapshot_id_equality"], 2),
    ):
        source = _valid_10fh_report()
        source["recognized_signal_types_seen"] = signal_types
        source["recognized_signal_type_count"] = count
        _recompute_10fh(source)

        report = (
            create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
                source
            )
        )

        _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_validated(signal_type: str):
    source = _valid_10fh_report()
    source.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": [signal_type],
            "recognized_signal_type_count": 1,
        }
    )
    _recompute_10fh(source)

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )

    assert report["ok"] is True
    assert report["status_report_status"] == "verified"
    assert "recognized_signal_types_seen" not in report


def test_caller_owned_lists_are_snapshot_detached_and_source_is_not_mutated():
    source = _valid_10fh_report()
    before = json.loads(json.dumps(source))

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )
    source["recognized_signal_types_seen"].clear()
    source["errors"].append("late raw 10FH error")

    assert before["recognized_signal_types_seen"] != source[
        "recognized_signal_types_seen"
    ]
    assert report["errors"] == []
    assert "late raw 10FH error" not in json.dumps(report)
    assert before == _valid_10fh_report()


def test_output_contains_only_immediate_sanitized_10fh_status():
    source = _valid_10fh_report()

    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            source
        )
    )
    serialized = json.dumps(report)

    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    assert report["source_verifier_decision_id"] == source[
        "verifier_decision_id"
    ]
    for field in (
        "source_verification_digest_decision_id",
        "source_digest_decision_id",
        "source_bundle_decision_id",
        "records_seen",
        "recognized_signal_types_seen",
        "source_error_count",
    ):
        assert field not in report
        assert str(source[field]) not in serialized or str(source[field]) in {
            "True",
            "False",
            "0",
            "2",
        }


def test_export_is_deterministic_sorted_json_for_verified_and_invalid_reports():
    reports = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _valid_10fh_report()
        ),
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            None
        ),
    )

    for report in reports:
        first = export_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            report
        )
        second = export_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            dict(report)
        )

        assert first == second
        assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
        assert json.loads(first) == report


def test_export_rejects_unexpected_or_forbidden_fields():
    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _valid_10fh_report()
        )
    )
    report["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10FN status report shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            report
        )


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        def items(self):
            raise RuntimeError("caller-controlled items")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _valid_10fh_report()
        )
    )

    with pytest.raises(ValueError, match="exact 10FN status report shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            report
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("status_report_schema_version", "10FN.2"),
        ("status_report_type", "future_reporter"),
        ("status_report_scope", "future_scope"),
        ("status_report_decision_id", "10FN-tainted"),
        ("source_verifier_schema_version", "10FH.2"),
        ("source_verifier_decision_id", "10FH-tainted"),
        ("source_verifier_status", "future_status"),
        ("source_verifier_ok", 1),
        ("status_report_status", "invalid_report"),
        ("runtime_allowed", 0),
        ("errors", ["raw source error"]),
        ("claim_boundary", "expanded boundary"),
        (
            "source_verifier_decision_id",
            type("StrSubclass", (str,), {})("10FH-" + "a" * 32),
        ),
        ("errors", type("ListSubclass", (list,), {})([])),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _valid_10fh_report()
        )
    )
    report[field] = value
    if field != "status_report_decision_id":
        _recompute_10fn(report)

    with pytest.raises(ValueError, match="exact 10FN status report shape"):
        export_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            report
        )


def test_gate_flags_are_false_on_success_and_failure():
    for report in (
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            _valid_10fh_report()
        ),
        create_minimal_inert_ledger_status_digest_verification_verifier_status_report(
            None
        ),
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
        "verify_minimal_inert_ledger_status_digest_verification_report",
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_minimal_inert_ledger_status_bundle_reporter",
        "local_minimal_inert_ledger_status_digest_reporter",
        "local_minimal_inert_ledger_status_digest_verifier",
        "local_minimal_inert_ledger_status_digest_verification_reporter",
        "local_minimal_inert_ledger_status_digest_verification_verifier",
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


def test_caller_owned_lists_are_detached_before_content_validation_and_export():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_verifier_snapshot"]
    assert validator is not None
    assert validator.index("signal_types = list(signal_types)") < validator.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "source_errors != expected_errors"
    )

    exporter = functions[
        "export_minimal_inert_ledger_status_digest_verification_verifier_status_report"
    ]
    assert exporter is not None
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

    validator = functions["_validated_verifier_snapshot"]
    assert validator is not None
    assert validator.index("snapshot = dict(source)") < validator.index(
        "type(key) is not str for key in snapshot"
    )

    exporter = functions[
        "export_minimal_inert_ledger_status_digest_verification_verifier_status_report"
    ]
    assert exporter is not None
    assert exporter.index("report = dict(status_report)") < exporter.index(
        "type(key) is not str for key in report"
    )
