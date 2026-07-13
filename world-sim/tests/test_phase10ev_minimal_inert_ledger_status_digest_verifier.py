"""Phase 10EV - minimal inert ledger status digest verifier tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_status_digest_verifier import (
    export_minimal_inert_ledger_status_digest_verification_report,
    verify_minimal_inert_ledger_status_digest_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_digest_verifier.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

DIGEST_FIELDS = {
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
    "source_verifier_decision_id",
    "source_reporter_decision_id",
    "verified_record_hashes",
    "source_errors",
    "raw_10dx_errors",
    "raw_10ed_errors",
    "raw_10ej_errors",
    "raw_10ep_errors",
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

DIGEST_CLAIM_BOUNDARY = (
    "aggregate 10EJ status digest only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

VERIFIER_CLAIM_BOUNDARY = (
    "verify one 10EP status digest only; no ledger access, digest text, raw "
    "hashes, raw source errors, write, repair, runtime action, daemon, "
    "scheduler, network, world-data promotion, movement, map lookup, route "
    "execution, event emission, NPC behavior, co-presence, awareness, "
    "relationship, interaction, or timing"
)

INVALID_DIGEST_ERROR = "digest_report is not a valid 10EP digest"
INVALID_10EJ_ERROR = "bundle_report is not a valid 10EJ bundle"
NON_VERIFIED_ERROR = "source 10EJ bundle did not report verified"

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


def _digest_decision_id(digest: dict) -> str:
    material = {
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
    return "10EP-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


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


def _digest_text(digest: dict) -> str:
    signal_types = ",".join(digest["recognized_signal_types_seen"]) or "none"
    source_ok = "true" if digest["source_ok"] else "false"
    line_format = (
        "true" if digest["append_only_line_format_valid"] else "false"
    )
    return (
        "10EP status digest"
        f" | source_bundle={digest['source_bundle_decision_id']}"
        f" | status={digest['source_bundle_status']}"
        f" | ok={source_ok}"
        f" | source_summary_status={digest['source_summary_status']}"
        f" | records_seen={digest['records_seen']}"
        f" | records_valid={digest['records_valid']}"
        f" | invalid_record_count={digest['invalid_record_count']}"
        " | verified_record_hash_count="
        f"{digest['verified_record_hash_count']}"
        " | recognized_signal_type_count="
        f"{digest['recognized_signal_type_count']}"
        f" | recognized_signal_types={signal_types}"
        f" | append_only_line_format_valid={line_format}"
        f" | source_error_count={digest['source_error_count']}"
        " | gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def _valid_digest(
    digest_status: str = "verified_digest",
    *,
    source_bundle_status: str | None = None,
) -> dict:
    if digest_status == "invalid_10ej_source":
        digest = {
            "ok": False,
            "digest_schema_version": "10EP.1",
            "digest_type": "minimal_inert_ledger_status_digest_report",
            "digest_scope": "inert_ledger_status_digest_only",
            "digest_decision_id": "",
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
            "digest_status": "invalid_10ej_source",
            "digest_text": "",
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": DIGEST_CLAIM_BOUNDARY,
            "errors": [INVALID_10EJ_ERROR],
        }
    else:
        verified = digest_status == "verified_digest"
        source_status = source_bundle_status or (
            "verified_bundle" if verified else "verification_failed_bundle"
        )
        invalid_source = source_status in INVALID_BUNDLE_STATUSES
        digest = {
            "ok": verified,
            "digest_schema_version": "10EP.1",
            "digest_type": "minimal_inert_ledger_status_digest_report",
            "digest_scope": "inert_ledger_status_digest_only",
            "digest_decision_id": "",
            "source_bundle_schema_version": "10EJ.1",
            "source_bundle_decision_id": "10EJ-"
            + ("a" if verified else "b") * 32,
            "source_bundle_status": source_status,
            "source_ok": verified,
            "source_summary_status": (
                "verified"
                if verified
                else ("" if invalid_source else "verification_failed")
            ),
            "ledger_path_supplied": False if invalid_source else True,
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
                0 if verified or invalid_source else 2
            ),
            "digest_status": digest_status,
            "digest_text": "",
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": DIGEST_CLAIM_BOUNDARY,
            "errors": [] if verified else [NON_VERIFIED_ERROR],
        }

    digest["digest_text"] = _digest_text(digest)
    digest["digest_decision_id"] = _digest_decision_id(digest)
    assert set(digest) == DIGEST_FIELDS
    return digest


def _recompute_digest(digest: dict) -> None:
    digest["digest_text"] = _digest_text(digest)
    digest["digest_decision_id"] = _digest_decision_id(digest)


def _assert_inert(value: dict) -> None:
    for field in GATE_FLAGS:
        assert value[field] is False, field


def _assert_sanitized_verification(report: dict) -> None:
    assert report["ok"] is False
    assert report["verifier_schema_version"] == "10EV.1"
    assert report["verifier_type"] == (
        "minimal_inert_ledger_status_digest_verifier"
    )
    assert report["verifier_scope"] == (
        "inert_ledger_status_digest_verification_only"
    )
    assert report["verifier_decision_id"] == _verifier_decision_id(report)
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
    assert report["digest_text_valid"] is False
    assert report["verification_status"] == "invalid_digest"
    assert report["claim_boundary"] == VERIFIER_CLAIM_BOUNDARY
    assert report["errors"] == [INVALID_DIGEST_ERROR]
    assert set(report) == VERIFICATION_FIELDS
    _assert_inert(report)


def test_public_api_accepts_exactly_one_caller_supplied_input():
    signature = inspect.signature(
        verify_minimal_inert_ledger_status_digest_report
    )

    assert tuple(signature.parameters) == ("digest_report",)


def test_exporter_accepts_exactly_one_verification_report():
    signature = inspect.signature(
        export_minimal_inert_ledger_status_digest_verification_report
    )

    assert tuple(signature.parameters) == ("verification_report",)


def test_missing_10ep_digest_fails_closed():
    report = verify_minimal_inert_ledger_status_digest_report(None)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize("value", ([], "10EP", 7, True, object()))
def test_non_dict_10ep_digest_fails_closed(value: object):
    report = verify_minimal_inert_ledger_status_digest_report(value)

    _assert_sanitized_verification(report)


def test_hostile_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = verify_minimal_inert_ledger_status_digest_report(
        _HostileDict(_valid_digest())
    )

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    ("digest_status", "source_bundle_status"),
    (
        ("verified_digest", "verified_bundle"),
        ("non_verified_digest", "verification_failed_bundle"),
        ("non_verified_digest", "invalid_10dx_source"),
        ("non_verified_digest", "invalid_10ed_source"),
        ("non_verified_digest", "mismatched_sources"),
        ("invalid_10ej_source", None),
    ),
)
def test_each_exact_valid_10ep_digest_verifies_as_intact(
    digest_status: str,
    source_bundle_status: str | None,
):
    digest = _valid_digest(
        digest_status,
        source_bundle_status=source_bundle_status,
    )

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    assert report["ok"] is True
    assert report["verifier_schema_version"] == "10EV.1"
    assert report["verifier_type"] == (
        "minimal_inert_ledger_status_digest_verifier"
    )
    assert report["verifier_scope"] == (
        "inert_ledger_status_digest_verification_only"
    )
    assert report["verifier_decision_id"] == _verifier_decision_id(report)
    assert report["source_digest_schema_version"] == "10EP.1"
    assert report["source_digest_decision_id"] == digest["digest_decision_id"]
    assert report["source_digest_status"] == digest_status
    assert report["source_digest_ok"] is digest["ok"]
    assert report["source_bundle_schema_version"] == digest[
        "source_bundle_schema_version"
    ]
    assert report["source_bundle_decision_id"] == digest[
        "source_bundle_decision_id"
    ]
    assert report["source_bundle_status"] == digest["source_bundle_status"]
    assert report["source_ok"] is digest["source_ok"]
    assert report["source_summary_status"] == digest[
        "source_summary_status"
    ]
    assert report["recognized_signal_types_seen"] == digest[
        "recognized_signal_types_seen"
    ]
    assert report["digest_text_valid"] is True
    assert report["verification_status"] == "digest_intact"
    assert report["errors"] == []
    assert report["claim_boundary"] == VERIFIER_CLAIM_BOUNDARY
    assert set(report) == VERIFICATION_FIELDS
    _assert_inert(report)


@pytest.mark.parametrize("field", sorted(DIGEST_FIELDS))
def test_missing_required_10ep_field_fails_closed(field: str):
    digest = _valid_digest()
    digest.pop(field)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_unexpected_10ep_field_fails_closed():
    digest = _valid_digest()
    digest["future_field"] = "not authorized"

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("digest_schema_version", "10EP.2"),
        ("digest_type", "future_digest"),
        ("digest_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10ep_identity_fails_closed(field: str, value: object):
    digest = _valid_digest()
    digest[field] = value
    if field != "claim_boundary":
        digest["digest_decision_id"] = _digest_decision_id(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

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
        "10EJ-" + "a" * 32,
    ),
)
def test_malformed_digest_decision_id_fails_closed(decision_id: str):
    digest = _valid_digest()
    digest["digest_decision_id"] = decision_id

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_tampered_digest_decision_id_fails_closed():
    digest = _valid_digest()
    digest["digest_decision_id"] = "10EP-" + "f" * 32

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10EJ-",
        "10EJ-" + "a" * 31,
        "10EJ-" + "a" * 33,
        "10EJ-" + "A" * 32,
        "10EJ-" + "g" * 32,
        "10EP-" + "a" * 32,
    ),
)
def test_wrong_source_bundle_decision_id_syntax_fails_closed(
    decision_id: str,
):
    digest = _valid_digest()
    digest["source_bundle_decision_id"] = decision_id
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_source_10ej_decision_id_is_syntax_only_and_not_recomputed():
    digest = _valid_digest()
    digest["source_bundle_decision_id"] = "10EJ-" + "0" * 32
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    assert report["ok"] is True
    assert report["source_bundle_decision_id"] == "10EJ-" + "0" * 32
    assert report["verification_status"] == "digest_intact"


@pytest.mark.parametrize(
    "field",
    (
        "ok",
        "source_ok",
        "ledger_path_supplied",
        "ledger_file_seen",
        "append_only_line_format_valid",
    ),
)
def test_integer_bool_drift_fails_closed(field: str):
    digest = _valid_digest()
    digest[field] = 1
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(field: str):
    digest = _valid_digest()
    digest[field] = 0

    report = verify_minimal_inert_ledger_status_digest_report(digest)

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
    digest = _valid_digest()
    digest[field] = value
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_invalid_recognized_signal_type_fails_closed():
    digest = _valid_digest()
    digest["recognized_signal_types_seen"] = ["future_unknown_signal"]
    digest["recognized_signal_type_count"] = 1
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_mismatched_recognized_signal_type_count_fails_closed():
    digest = _valid_digest()
    digest["recognized_signal_type_count"] = 1
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("digest_schema_version", type("StrSubclass", (str,), {})("10EP.1")),
        (
            "source_bundle_decision_id",
            type("StrSubclass", (str,), {})("10EJ-" + "a" * 32),
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
    digest = _valid_digest()
    digest[field] = value
    digest["digest_decision_id"] = _digest_decision_id(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_string_subclass_dictionary_key_fails_closed():
    digest = _valid_digest()
    value = digest.pop("ok")
    digest[type("StrSubclass", (str,), {})("ok")] = value

    report = verify_minimal_inert_ledger_status_digest_report(digest)

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
        ("source_bundle_schema_version", "10EJ.2"),
        ("source_bundle_status", "future_bundle"),
    ),
)
def test_inconsistent_verified_digest_aggregate_fails_closed(
    field: str,
    value: object,
):
    digest = _valid_digest()
    digest[field] = value
    if field == "recognized_signal_types_seen":
        digest["recognized_signal_type_count"] = len(value)
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_invalid_10ej_digest_requires_fully_sanitized_source_fields():
    digest = _valid_digest("invalid_10ej_source")
    digest["records_seen"] = 1
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_invalid_bundle_status_requires_sanitized_source_aggregate():
    digest = _valid_digest(
        "non_verified_digest",
        source_bundle_status="invalid_10dx_source",
    )
    digest["ledger_path_supplied"] = True
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_digest_status_and_source_bundle_status_mapping_is_exact():
    digest = _valid_digest()
    digest["digest_status"] = "non_verified_digest"
    digest["ok"] = False
    digest["errors"] = [NON_VERIFIED_ERROR]
    digest["digest_decision_id"] = _digest_decision_id(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_digest_error_mapping_is_exact():
    digest = _valid_digest("non_verified_digest")
    digest["errors"] = ["raw 10EP source error"]
    digest["digest_decision_id"] = _digest_decision_id(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_verified(signal_type: str):
    digest = _valid_digest()
    digest.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": [signal_type],
            "recognized_signal_type_count": 1,
        }
    )
    _recompute_digest(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    assert report["ok"] is True
    assert report["recognized_signal_types_seen"] == [signal_type]
    assert report["recognized_signal_type_count"] == 1


def test_digest_text_mismatch_fails_closed_even_with_recomputed_id():
    digest = _valid_digest()
    digest["digest_text"] += " | tampered=true"
    digest["digest_decision_id"] = _digest_decision_id(digest)

    report = verify_minimal_inert_ledger_status_digest_report(digest)

    _assert_sanitized_verification(report)


def test_digest_text_valid_true_only_for_exact_valid_source_text():
    valid = verify_minimal_inert_ledger_status_digest_report(_valid_digest())
    tampered_digest = _valid_digest()
    tampered_digest["digest_text"] = "10EP status digest | approximate"
    tampered_digest["digest_decision_id"] = _digest_decision_id(
        tampered_digest
    )
    invalid = verify_minimal_inert_ledger_status_digest_report(tampered_digest)

    assert valid["digest_text_valid"] is True
    assert invalid["digest_text_valid"] is False


def test_caller_owned_lists_are_snapshot_detached_before_export():
    digest = _valid_digest()

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    digest["recognized_signal_types_seen"].clear()
    digest["errors"].append("late raw 10EP error")

    assert report["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    assert report["errors"] == []
    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )
    assert "late raw 10EP error" not in exported


def test_verifier_does_not_mutate_caller_digest():
    digest = _valid_digest("non_verified_digest")
    before = json.loads(json.dumps(digest))

    verify_minimal_inert_ledger_status_digest_report(digest)

    assert digest == before


@pytest.mark.parametrize(
    "digest",
    (
        _valid_digest("non_verified_digest"),
        _valid_digest("invalid_10ej_source"),
    ),
)
def test_raw_10ep_errors_are_not_emitted(digest: dict):
    raw_error = digest["errors"][0]

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    serialized = json.dumps(report)

    assert report["ok"] is True
    assert report["errors"] == []
    assert raw_error not in serialized
    assert "raw_10ep_errors" not in report


def test_raw_hashes_cannot_appear_in_output():
    raw_hash = "f" * 64
    digest = _valid_digest()
    digest["verified_record_hashes"] = [raw_hash]

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    serialized = json.dumps(report)

    _assert_sanitized_verification(report)
    assert raw_hash not in serialized
    assert "verified_record_hashes" not in report


def test_raw_paths_cannot_appear_in_output():
    private_path = "C:\\private\\runtime_adapter_decisions.ndjson"
    digest = _valid_digest()
    digest["path"] = private_path

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    serialized = json.dumps(report)

    _assert_sanitized_verification(report)
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
    digest = _valid_digest()
    digest[field] = secret

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    serialized = json.dumps(report)

    _assert_sanitized_verification(report)
    assert field not in report
    assert secret not in serialized


def test_digest_text_is_never_emitted():
    digest = _valid_digest()

    report = verify_minimal_inert_ledger_status_digest_report(digest)
    serialized = json.dumps(report)

    assert "digest_text" not in report
    assert digest["digest_text"] not in serialized
    assert report["digest_text_valid"] is True


def test_output_contains_only_safe_aggregate_fields():
    digests = (
        _valid_digest(),
        _valid_digest("non_verified_digest"),
        _valid_digest("invalid_10ej_source"),
        None,
    )
    for digest in digests:
        report = verify_minimal_inert_ledger_status_digest_report(digest)

        assert set(report) == VERIFICATION_FIELDS
        assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
        _assert_inert(report)


def test_export_is_deterministic_sorted_json():
    report = verify_minimal_inert_ledger_status_digest_report(_valid_digest())

    first = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )
    second = export_minimal_inert_ledger_status_digest_verification_report(
        dict(report)
    )

    assert first == second
    assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == report


@pytest.mark.parametrize(
    ("digest_status", "source_bundle_status"),
    (
        ("non_verified_digest", "verification_failed_bundle"),
        ("invalid_10ej_source", None),
    ),
)
def test_export_accepts_each_intact_non_success_digest(
    digest_status: str,
    source_bundle_status: str | None,
):
    digest = _valid_digest(
        digest_status,
        source_bundle_status=source_bundle_status,
    )
    report = verify_minimal_inert_ledger_status_digest_report(digest)

    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )

    assert report["ok"] is True
    assert report["source_digest_ok"] is False
    assert report["verification_status"] == "digest_intact"
    assert json.loads(exported) == report


def test_export_accepts_sanitized_invalid_verification_report():
    report = verify_minimal_inert_ledger_status_digest_report(None)

    exported = export_minimal_inert_ledger_status_digest_verification_report(
        report
    )

    assert json.loads(exported) == report
    assert INVALID_DIGEST_ERROR in exported


def test_export_rejects_unexpected_or_forbidden_fields():
    report = verify_minimal_inert_ledger_status_digest_report(_valid_digest())
    report["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10EV verification shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        def items(self):
            raise RuntimeError("caller-controlled items")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        verify_minimal_inert_ledger_status_digest_report(_valid_digest())
    )

    with pytest.raises(ValueError, match="exact 10EV verification shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("verifier_schema_version", "10EV.2"),
        ("verifier_type", "future_verifier"),
        ("verifier_scope", "future_scope"),
        ("verifier_decision_id", "10EV-tainted"),
        ("source_digest_schema_version", "10EP.2"),
        ("source_digest_decision_id", "10EP-tainted"),
        ("source_digest_status", "runtime_started"),
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
        ("digest_text_valid", False),
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
    report = verify_minimal_inert_ledger_status_digest_report(_valid_digest())
    report[field] = value
    if field != "verifier_decision_id":
        report["verifier_decision_id"] = _verifier_decision_id(report)

    with pytest.raises(ValueError, match="exact 10EV verification shape"):
        export_minimal_inert_ledger_status_digest_verification_report(report)


def test_gate_flags_are_false_on_success_and_failure():
    for report in (
        verify_minimal_inert_ledger_status_digest_report(_valid_digest()),
        verify_minimal_inert_ledger_status_digest_report(
            _valid_digest("non_verified_digest")
        ),
        verify_minimal_inert_ledger_status_digest_report(None),
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
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_minimal_inert_ledger_status_bundle_reporter",
        "local_minimal_inert_ledger_status_digest_reporter",
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
    assert validator.index("digest_errors = list(digest_errors)") < validator.index(
        "digest_errors != expected_errors"
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
