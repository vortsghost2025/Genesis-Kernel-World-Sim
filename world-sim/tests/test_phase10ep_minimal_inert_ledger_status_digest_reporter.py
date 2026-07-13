"""Phase 10EP - minimal inert ledger status digest reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_ledger_status_digest_reporter import (
    create_minimal_inert_ledger_status_digest_report,
    export_minimal_inert_ledger_status_digest_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_ledger_status_digest_reporter.py"
)

KNOWN_SIGNAL_TYPES = (
    "snapshot_id_equality",
    "snapshot_hash_equality",
    "current_tile_id_equality",
    "route_intent_id_equality",
    "known_tile_ids_set_equality",
    "route_destination_tile_id_equality",
)

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

GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

FORBIDDEN_DIGEST_FIELDS = {
    "source_verifier_decision_id",
    "source_reporter_decision_id",
    "verified_record_hashes",
    "source_errors",
    "raw_10dx_errors",
    "raw_10ed_errors",
    "raw_10ej_errors",
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

BUNDLE_CLAIM_BOUNDARY = (
    "aggregate 10DX and 10ED status bundle only; no ledger access, raw hashes, "
    "raw source errors, write, repair, runtime action, daemon, scheduler, "
    "network, world-data promotion, movement, map lookup, route execution, "
    "event emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

DIGEST_CLAIM_BOUNDARY = (
    "aggregate 10EJ status digest only; no ledger access, raw hashes, raw "
    "source errors, write, repair, runtime action, daemon, scheduler, network, "
    "world-data promotion, movement, map lookup, route execution, event "
    "emission, NPC behavior, co-presence, awareness, relationship, "
    "interaction, or timing"
)

INVALID_10EJ_ERROR = "bundle_report is not a valid 10EJ bundle"
NON_VERIFIED_ERROR = "source 10EJ bundle did not report verified"
SOURCE_FAILED_ERROR = "source 10DX verification did not pass"
INVALID_10DX_ERROR = "verification_result is not a valid 10DX result"
INVALID_10ED_ERROR = "summary_report is not a valid 10ED report"
MISMATCH_ERROR = "10DX and 10ED sources do not match"

INVALID_DIGEST_TEXT = (
    "10EP status digest | source_bundle= | status= | ok=false | "
    "source_summary_status= | records_seen=0 | records_valid=0 | "
    "invalid_record_count=0 | verified_record_hash_count=0 | "
    "recognized_signal_type_count=0 | recognized_signal_types=none | "
    "append_only_line_format_valid=false | source_error_count=0 | "
    "gates=executed:false,runtime:false,daemon:false,scheduler:false,"
    "network:false,world_data:false,gate7:false"
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


def _digest_text(source: dict) -> str:
    signal_types = ",".join(source["recognized_signal_types_seen"]) or "none"
    source_ok = "true" if source["source_ok"] else "false"
    line_format = (
        "true" if source["append_only_line_format_valid"] else "false"
    )
    return (
        "10EP status digest"
        f" | source_bundle={source['bundle_decision_id']}"
        f" | status={source['bundle_status']}"
        f" | ok={source_ok}"
        f" | source_summary_status={source['source_summary_status']}"
        f" | records_seen={source['records_seen']}"
        f" | records_valid={source['records_valid']}"
        f" | invalid_record_count={source['invalid_record_count']}"
        " | verified_record_hash_count="
        f"{source['verified_record_hash_count']}"
        " | recognized_signal_type_count="
        f"{source['recognized_signal_type_count']}"
        f" | recognized_signal_types={signal_types}"
        f" | append_only_line_format_valid={line_format}"
        f" | source_error_count={source['source_error_count']}"
        " | gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def _valid_bundle(status: str = "verified_bundle") -> dict:
    invalid_errors = {
        "invalid_10dx_source": INVALID_10DX_ERROR,
        "invalid_10ed_source": INVALID_10ED_ERROR,
        "mismatched_sources": MISMATCH_ERROR,
    }
    if status in invalid_errors:
        return {
            "ok": False,
            "bundle_schema_version": "10EJ.1",
            "bundle_type": "minimal_inert_ledger_status_bundle_report",
            "bundle_scope": "inert_ledger_status_bundle_only",
            "bundle_decision_id": "10EJ-" + "c" * 32,
            "source_verifier_schema_version": "",
            "source_verifier_decision_id": "",
            "source_reporter_schema_version": "",
            "source_reporter_decision_id": "",
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
            "bundle_status": status,
            "executed": False,
            "runtime_allowed": False,
            "daemon_allowed": False,
            "scheduler_allowed": False,
            "network_allowed": False,
            "world_sim_data_accessed": False,
            "gate7_activity_allowed": False,
            "claim_boundary": BUNDLE_CLAIM_BOUNDARY,
            "errors": [invalid_errors[status]],
        }

    verified = status == "verified_bundle"
    return {
        "ok": verified,
        "bundle_schema_version": "10EJ.1",
        "bundle_type": "minimal_inert_ledger_status_bundle_report",
        "bundle_scope": "inert_ledger_status_bundle_only",
        "bundle_decision_id": "10EJ-" + ("a" if verified else "b") * 32,
        "source_verifier_schema_version": "10DX.1",
        "source_verifier_decision_id": "10DX-" + "d" * 32,
        "source_reporter_schema_version": "10ED.1",
        "source_reporter_decision_id": "10ED-" + "e" * 32,
        "source_ok": verified,
        "source_summary_status": (
            "verified" if verified else "verification_failed"
        ),
        "ledger_path_supplied": True,
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
        "source_error_count": 0 if verified else 2,
        "bundle_status": status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": BUNDLE_CLAIM_BOUNDARY,
        "errors": [] if verified else [SOURCE_FAILED_ERROR],
    }


def _assert_inert(value: dict) -> None:
    for field in GATE_FLAGS:
        assert value[field] is False, field


def _assert_sanitized_digest(digest: dict) -> None:
    assert digest["ok"] is False
    assert digest["digest_schema_version"] == "10EP.1"
    assert digest["digest_type"] == "minimal_inert_ledger_status_digest_report"
    assert digest["digest_scope"] == "inert_ledger_status_digest_only"
    assert digest["digest_decision_id"].startswith("10EP-")
    assert digest["source_bundle_schema_version"] == ""
    assert digest["source_bundle_decision_id"] == ""
    assert digest["source_bundle_status"] == ""
    assert digest["source_ok"] is False
    assert digest["source_summary_status"] == ""
    assert digest["ledger_path_supplied"] is False
    assert digest["ledger_file_seen"] is False
    assert digest["records_seen"] == 0
    assert digest["records_valid"] == 0
    assert digest["invalid_record_count"] == 0
    assert digest["verified_record_hash_count"] == 0
    assert digest["recognized_signal_types_seen"] == []
    assert digest["recognized_signal_type_count"] == 0
    assert digest["append_only_line_format_valid"] is False
    assert digest["source_error_count"] == 0
    assert digest["digest_status"] == "invalid_10ej_source"
    assert digest["digest_text"] == INVALID_DIGEST_TEXT
    assert digest["claim_boundary"] == DIGEST_CLAIM_BOUNDARY
    assert digest["errors"] == [INVALID_10EJ_ERROR]
    assert set(digest) == DIGEST_FIELDS
    _assert_inert(digest)


def test_public_api_accepts_exactly_one_caller_supplied_input():
    signature = inspect.signature(
        create_minimal_inert_ledger_status_digest_report
    )

    assert tuple(signature.parameters) == ("bundle_report",)


def test_missing_10ej_bundle_fails_closed():
    digest = create_minimal_inert_ledger_status_digest_report(None)

    _assert_sanitized_digest(digest)


@pytest.mark.parametrize("value", ([], "10EJ", 7, True, object()))
def test_non_dict_10ej_bundle_fails_closed(value: object):
    digest = create_minimal_inert_ledger_status_digest_report(value)

    _assert_sanitized_digest(digest)


def test_exact_valid_verified_bundle_produces_verified_digest():
    bundle = _valid_bundle("verified_bundle")

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    assert digest == {
        "ok": True,
        "digest_schema_version": "10EP.1",
        "digest_type": "minimal_inert_ledger_status_digest_report",
        "digest_scope": "inert_ledger_status_digest_only",
        "digest_decision_id": digest["digest_decision_id"],
        "source_bundle_schema_version": "10EJ.1",
        "source_bundle_decision_id": bundle["bundle_decision_id"],
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
        "digest_status": "verified_digest",
        "digest_text": _digest_text(bundle),
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": DIGEST_CLAIM_BOUNDARY,
        "errors": [],
    }
    assert digest["digest_decision_id"] == _digest_decision_id(digest)
    _assert_inert(digest)


@pytest.mark.parametrize(
    "status",
    (
        "verification_failed_bundle",
        "invalid_10dx_source",
        "invalid_10ed_source",
        "mismatched_sources",
    ),
)
def test_other_valid_bundle_statuses_produce_non_verified_digest(status: str):
    bundle = _valid_bundle(status)

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    assert digest["ok"] is False
    assert digest["source_bundle_schema_version"] == "10EJ.1"
    assert digest["source_bundle_decision_id"] == bundle["bundle_decision_id"]
    assert digest["source_bundle_status"] == status
    assert digest["source_ok"] is False
    assert digest["digest_status"] == "non_verified_digest"
    assert digest["digest_text"] == _digest_text(bundle)
    assert digest["errors"] == [NON_VERIFIED_ERROR]
    assert digest["digest_decision_id"] == _digest_decision_id(digest)
    _assert_inert(digest)


@pytest.mark.parametrize("field", sorted(BUNDLE_FIELDS))
def test_missing_required_10ej_field_fails_closed(field: str):
    bundle = _valid_bundle()
    bundle.pop(field)

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


def test_unexpected_10ej_field_fails_closed():
    bundle = _valid_bundle()
    bundle["future_field"] = "not authorized"

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("bundle_schema_version", "10EJ.2"),
        ("bundle_type", "future_bundle"),
        ("bundle_scope", "future_scope"),
        ("claim_boundary", "expanded boundary"),
    ),
)
def test_wrong_10ej_identity_fails_closed(field: str, value: object):
    bundle = _valid_bundle()
    bundle[field] = value

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


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
def test_malformed_bundle_decision_id_fails_closed(decision_id: str):
    bundle = _valid_bundle()
    bundle["bundle_decision_id"] = decision_id

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


def test_bundle_decision_id_is_syntax_only_and_not_recomputed():
    bundle = _valid_bundle()
    bundle["bundle_decision_id"] = "10EJ-" + "0" * 32

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    assert digest["ok"] is True
    assert digest["source_bundle_decision_id"] == "10EJ-" + "0" * 32
    assert digest["digest_text"] == _digest_text(bundle)


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
    bundle = _valid_bundle()
    bundle[field] = 1

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_gate_flag_integer_drift_fails_closed(field: str):
    bundle = _valid_bundle()
    bundle[field] = 0

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


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
    bundle = _valid_bundle()
    bundle[field] = value

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


def test_invalid_recognized_signal_type_fails_closed():
    bundle = _valid_bundle()
    bundle["recognized_signal_types_seen"] = ["future_unknown_signal"]
    bundle["recognized_signal_type_count"] = 1

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


def test_mismatched_recognized_signal_type_count_fails_closed():
    bundle = _valid_bundle()
    bundle["recognized_signal_type_count"] = 1

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("records_seen", type("IntSubclass", (int,), {})(2)),
        (
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(["snapshot_id_equality"]),
        ),
        (
            "bundle_decision_id",
            type("StrSubclass", (str,), {})("10EJ-" + "a" * 32),
        ),
    ),
)
def test_list_str_and_int_subclasses_fail_closed(field: str, value: object):
    bundle = _valid_bundle()
    bundle[field] = value

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    _assert_sanitized_digest(digest)


def test_hostile_dict_subclass_fails_closed_without_invoking_overrides():
    class _HostileDict(dict):
        def get(self, key: object, default: object = None) -> object:
            raise RuntimeError("caller-controlled get")

        def __iter__(self):
            raise RuntimeError("caller-controlled iteration")

    digest = create_minimal_inert_ledger_status_digest_report(
        _HostileDict(_valid_bundle())
    )

    _assert_sanitized_digest(digest)


def test_caller_owned_lists_are_snapshot_detached_before_export():
    bundle = _valid_bundle()

    digest = create_minimal_inert_ledger_status_digest_report(bundle)
    bundle["recognized_signal_types_seen"].clear()
    bundle["errors"].append("late raw 10EJ error")

    assert digest["recognized_signal_types_seen"] == [
        "snapshot_hash_equality",
        "snapshot_id_equality",
    ]
    assert digest["errors"] == []
    exported = export_minimal_inert_ledger_status_digest_report(digest)
    assert "late raw 10EJ error" not in exported


def test_raw_10ej_errors_are_counted_but_not_emitted():
    bundle = _valid_bundle("verification_failed_bundle")

    digest = create_minimal_inert_ledger_status_digest_report(bundle)
    serialized = json.dumps(digest)

    assert digest["source_error_count"] == bundle["source_error_count"] == 2
    assert all(error not in serialized for error in bundle["errors"])
    assert "raw_10ej_errors" not in digest


def test_raw_hashes_cannot_appear_in_output():
    raw_hash = "f" * 64
    bundle = _valid_bundle()
    bundle["verified_record_hashes"] = [raw_hash]

    digest = create_minimal_inert_ledger_status_digest_report(bundle)
    serialized = json.dumps(digest)

    _assert_sanitized_digest(digest)
    assert raw_hash not in serialized
    assert "verified_record_hashes" not in digest


def test_raw_paths_and_equality_values_cannot_appear_in_output():
    bundle = _valid_bundle("verification_failed_bundle")
    bundle["errors"] = [
        "C:\\private\\runtime_adapter_decisions.ndjson",
        "equality_signal_value=secret-value",
        "raw_record={agent_id: private-agent}",
    ]

    digest = create_minimal_inert_ledger_status_digest_report(bundle)
    serialized = json.dumps(digest)

    _assert_sanitized_digest(digest)
    assert "runtime_adapter_decisions.ndjson" not in serialized
    assert "secret-value" not in serialized
    assert "private-agent" not in serialized
    assert "equality_signal_value" not in serialized


def test_output_contains_only_safe_aggregate_fields():
    for status in (
        "verified_bundle",
        "verification_failed_bundle",
        "invalid_10dx_source",
        "invalid_10ed_source",
        "mismatched_sources",
    ):
        digest = create_minimal_inert_ledger_status_digest_report(
            _valid_bundle(status)
        )

        assert set(digest) == DIGEST_FIELDS
        assert FORBIDDEN_DIGEST_FIELDS.isdisjoint(digest)
        _assert_inert(digest)


@pytest.mark.parametrize("signal_type", KNOWN_SIGNAL_TYPES)
def test_each_known_signal_type_can_be_digest_reported(signal_type: str):
    bundle = _valid_bundle()
    bundle.update(
        {
            "records_seen": 1,
            "records_valid": 1,
            "verified_record_hash_count": 1,
            "recognized_signal_types_seen": [signal_type],
            "recognized_signal_type_count": 1,
        }
    )

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    assert digest["ok"] is True
    assert digest["recognized_signal_types_seen"] == [signal_type]
    assert digest["recognized_signal_type_count"] == 1
    assert f"recognized_signal_types={signal_type}" in digest["digest_text"]


def test_digest_text_matches_exact_deterministic_format():
    bundle = _valid_bundle()

    digest = create_minimal_inert_ledger_status_digest_report(bundle)

    assert digest["digest_text"] == (
        "10EP status digest | source_bundle=10EJ-"
        + "a" * 32
        + " | status=verified_bundle | ok=true | "
        "source_summary_status=verified | records_seen=2 | records_valid=2 | "
        "invalid_record_count=0 | verified_record_hash_count=2 | "
        "recognized_signal_type_count=2 | "
        "recognized_signal_types=snapshot_hash_equality,snapshot_id_equality | "
        "append_only_line_format_valid=true | source_error_count=0 | "
        "gates=executed:false,runtime:false,daemon:false,scheduler:false,"
        "network:false,world_data:false,gate7:false"
    )


def test_export_is_deterministic_sorted_json():
    digest = create_minimal_inert_ledger_status_digest_report(_valid_bundle())

    first = export_minimal_inert_ledger_status_digest_report(digest)
    second = export_minimal_inert_ledger_status_digest_report(dict(digest))

    assert first == second
    assert first == json.dumps(digest, sort_keys=True, ensure_ascii=False)
    assert json.loads(first) == digest


def test_export_rejects_unexpected_or_forbidden_fields():
    digest = create_minimal_inert_ledger_status_digest_report(_valid_bundle())
    digest["equality_signal_value"] = "must not export"

    with pytest.raises(ValueError, match="exact 10EP digest shape"):
        export_minimal_inert_ledger_status_digest_report(digest)


def test_export_rejects_dict_subclass_without_serializing_override():
    class _TaintedDigest(dict):
        def items(self):
            tainted = dict(super().items())
            tainted["errors"] = ["raw secret"]
            return tainted.items()

    digest = _TaintedDigest(
        create_minimal_inert_ledger_status_digest_report(_valid_bundle())
    )

    with pytest.raises(ValueError, match="exact 10EP digest shape"):
        export_minimal_inert_ledger_status_digest_report(digest)


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
        ("digest_status", "runtime_started"),
        ("digest_text", "tainted digest"),
        ("runtime_allowed", 0),
        ("errors", ["raw source error"]),
        ("digest_decision_id", "10EP-tainted"),
        ("claim_boundary", "expanded boundary"),
        (
            "source_bundle_decision_id",
            type("StrSubclass", (str,), {})("10EJ-" + "a" * 32),
        ),
        (
            "recognized_signal_types_seen",
            type("ListSubclass", (list,), {})(["snapshot_id_equality"]),
        ),
        ("source_error_count", type("IntSubclass", (int,), {})(0)),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    digest = create_minimal_inert_ledger_status_digest_report(_valid_bundle())
    digest[field] = value
    if field != "digest_decision_id":
        digest["digest_decision_id"] = _digest_decision_id(digest)

    with pytest.raises(ValueError, match="exact 10EP digest shape"):
        export_minimal_inert_ledger_status_digest_report(digest)


def test_gate_flags_are_false_on_success_and_failure():
    for digest in (
        create_minimal_inert_ledger_status_digest_report(_valid_bundle()),
        create_minimal_inert_ledger_status_digest_report(
            _valid_bundle("verification_failed_bundle")
        ),
        create_minimal_inert_ledger_status_digest_report(None),
    ):
        _assert_inert(digest)


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


def test_module_has_no_backend_10dx_10ed_10ej_or_10cp_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")

    forbidden_names = (
        "verify_minimal_inert_ledger_readback",
        "export_minimal_inert_ledger_readback_result",
        "create_minimal_inert_ledger_summary_report",
        "export_minimal_inert_ledger_summary_report",
        "create_minimal_inert_ledger_status_bundle_report",
        "export_minimal_inert_ledger_status_bundle_report",
        "append_inert_ledger_record",
        "local_minimal_inert_ledger_readback_verifier",
        "local_minimal_inert_ledger_summary_reporter",
        "local_minimal_inert_ledger_status_bundle_reporter",
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

    validator = functions["_validated_bundle_snapshot"]
    assert validator is not None
    assert validator.index("signal_types = list(signal_types)") < validator.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert validator.index("bundle_errors = list(bundle_errors)") < validator.index(
        "bundle_errors != expected_errors"
    )

    exporter = functions["export_minimal_inert_ledger_status_digest_report"]
    assert exporter is not None
    assert exporter.index("signal_types = list(signal_types)") < exporter.index(
        "signal_type not in _KNOWN_SIGNAL_TYPES"
    )
    assert exporter.index("digest_errors = list(digest_errors)") < exporter.index(
        "digest_errors != expected_errors"
    )
