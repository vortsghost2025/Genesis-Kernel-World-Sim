"""Phase 10GX - inert authorization status meta-meta-verification tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_reporter import (
    create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report,
    export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_reporter.py"
)

SOURCE_FIELDS = {
    "ok",
    "authorization_status_meta_verification_schema_version",
    "authorization_status_meta_verification_type",
    "authorization_status_meta_verification_scope",
    "authorization_status_meta_verification_decision_id",
    "source_verification_schema_version",
    "source_verification_decision_id",
    "source_verification_status",
    "source_verification_ok",
    "source_status_report_schema_version",
    "source_status_report_decision_id",
    "source_status_report_status",
    "source_status_report_ok",
    "source_authorization_schema_version",
    "source_authorization_decision_id",
    "source_authorization_status",
    "source_authorization_ok",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "approval_decision_id",
    "approval_status",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "authorization_status_meta_verification_status",
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
    "authorization_status_meta_meta_verification_schema_version",
    "authorization_status_meta_meta_verification_type",
    "authorization_status_meta_meta_verification_scope",
    "authorization_status_meta_meta_verification_decision_id",
    "source_meta_verification_schema_version",
    "source_meta_verification_decision_id",
    "source_meta_verification_status",
    "source_meta_verification_ok",
    "source_verification_schema_version",
    "source_verification_decision_id",
    "source_verification_status",
    "source_verification_ok",
    "source_status_report_schema_version",
    "source_status_report_decision_id",
    "source_status_report_status",
    "source_status_report_ok",
    "source_authorization_schema_version",
    "source_authorization_decision_id",
    "source_authorization_status",
    "source_authorization_ok",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "approval_decision_id",
    "approval_status",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "authorization_status_meta_meta_verification_status",
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

SOURCE_OK_FIELDS = (
    "ok",
    "source_verification_ok",
    "source_status_report_ok",
    "source_authorization_ok",
)

OUTPUT_OK_FIELDS = (
    "ok",
    "source_meta_verification_ok",
    "source_verification_ok",
    "source_status_report_ok",
    "source_authorization_ok",
)

SOURCE_STRING_FIELDS = (
    "authorization_status_meta_verification_schema_version",
    "authorization_status_meta_verification_type",
    "authorization_status_meta_verification_scope",
    "authorization_status_meta_verification_decision_id",
    "source_verification_schema_version",
    "source_verification_decision_id",
    "source_verification_status",
    "source_status_report_schema_version",
    "source_status_report_decision_id",
    "source_status_report_status",
    "source_authorization_schema_version",
    "source_authorization_decision_id",
    "source_authorization_status",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "approval_decision_id",
    "approval_status",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "authorization_status_meta_verification_status",
    "claim_boundary",
)

OUTPUT_STRING_FIELDS = (
    "authorization_status_meta_meta_verification_schema_version",
    "authorization_status_meta_meta_verification_type",
    "authorization_status_meta_meta_verification_scope",
    "authorization_status_meta_meta_verification_decision_id",
    "source_meta_verification_schema_version",
    "source_meta_verification_decision_id",
    "source_meta_verification_status",
    "source_verification_schema_version",
    "source_verification_decision_id",
    "source_verification_status",
    "source_status_report_schema_version",
    "source_status_report_decision_id",
    "source_status_report_status",
    "source_authorization_schema_version",
    "source_authorization_decision_id",
    "source_authorization_status",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "approval_decision_id",
    "approval_status",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "authorization_status_meta_meta_verification_status",
    "claim_boundary",
)

OUTPUT_SOURCE_STRING_FIELDS = (
    "source_meta_verification_schema_version",
    "source_meta_verification_decision_id",
    "source_meta_verification_status",
    "source_verification_schema_version",
    "source_verification_decision_id",
    "source_verification_status",
    "source_status_report_schema_version",
    "source_status_report_decision_id",
    "source_status_report_status",
    "source_authorization_schema_version",
    "source_authorization_decision_id",
    "source_authorization_status",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "approval_decision_id",
    "approval_status",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
)

SOURCE_CLAIM_BOUNDARY = (
    "verify one 10GL model routing authorization status verification report "
    "only; no runtime execution, provider call, model invocation, filesystem "
    "scan, config mutation, agent launch, world-data access, ledger access, "
    "write, repair, re-authorization, source verification, status-report "
    "re-verification, or gate-7 activity"
)

CLAIM_BOUNDARY = (
    "verify one 10GR model routing authorization status meta-verification "
    "report only; no runtime execution, provider call, model invocation, "
    "filesystem scan, config mutation, agent launch, world-data access, ledger "
    "access, write, repair, re-authorization, source verification, status-report "
    "re-verification, meta-verification re-derivation, or gate-7 activity"
)

INVALID_SOURCE_ERROR = (
    "meta_verification_report is not a valid 10GR authorization status "
    "meta-verification report"
)

FORBIDDEN_OUTPUT_FIELDS = {
    "authorization_status_meta_verification_type",
    "authorization_status_meta_verification_scope",
    "api_key",
    "access_token",
    "refresh_token",
    "secret",
    "raw_config",
    "raw_provider_payload",
    "provider_response",
    "file_path",
    "path",
    "ledger_path",
    "record",
    "records",
    "record_hash",
    "raw_hash",
    "raw_source_errors",
    "equality_signal_value",
    "equality_signal_type",
    "runtime_state",
    "movement",
    "map_lookup",
    "route_execution",
    "event",
    "npc_behavior",
    "social",
    "timing",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _source_decision_id(report: dict) -> str:
    material = {
        key: report[key]
        for key in sorted(
            SOURCE_FIELDS
            - {"authorization_status_meta_verification_decision_id"}
        )
    }
    return "10GR-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _output_decision_id(report: dict) -> str:
    material = {
        key: report[key]
        for key in sorted(
            OUTPUT_FIELDS
            - {"authorization_status_meta_meta_verification_decision_id"}
        )
    }
    return "10GX-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_meta_verification_report(
    status: str = "verified_authorized_verification_status",
    *,
    approval_status: str | None = None,
) -> dict:
    authorized = status == "verified_authorized_verification_status"
    if approval_status is None:
        approval_status = "operator_approved" if authorized else "operator_denied"
    report = {
        "ok": True,
        "authorization_status_meta_verification_schema_version": "10GR.1",
        "authorization_status_meta_verification_type": (
            "minimal_inert_model_routing_authorization_report_status_"
            "verification_verifier_status_verification_verifier_status_report"
        ),
        "authorization_status_meta_verification_scope": (
            "model_routing_authorization_report_status_verification_verifier_"
            "status_verification_only"
        ),
        "authorization_status_meta_verification_decision_id": "",
        "source_verification_schema_version": "10GL.1",
        "source_verification_decision_id": "10GL-" + "a" * 32,
        "source_verification_status": (
            "verified_authorized_status"
            if authorized
            else "verified_not_authorized_status"
        ),
        "source_verification_ok": True,
        "source_status_report_schema_version": "10GF.1",
        "source_status_report_decision_id": "10GF-" + "b" * 32,
        "source_status_report_status": (
            "authorized_status" if authorized else "not_authorized_status"
        ),
        "source_status_report_ok": True,
        "source_authorization_schema_version": "10FZ.1",
        "source_authorization_decision_id": "10FZ-" + "c" * 32,
        "source_authorization_status": (
            "authorized" if authorized else "not_authorized"
        ),
        "source_authorization_ok": True,
        "source_provenance_decision_id": "10FT-" + "d" * 32,
        "source_policy_decision_id": "10FT-POLICY-" + "e" * 32,
        "approval_decision_id": "10FZ-APPROVAL-" + "f" * 32,
        "approval_status": approval_status,
        "artifact_class": "implementation_phase",
        "artifact_family": "governance_provenance",
        "authorized_lane": "lane:gpt-5-6-sol",
        "provider_id": "provider:openai",
        "provider_name": "openai",
        "pinned_model_id": "model:gpt-5-6-sol",
        "pinned_model_revision": "2026-07-15",
        "authorization_status_meta_verification_status": status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": SOURCE_CLAIM_BOUNDARY,
        "errors": [],
    }
    report["authorization_status_meta_verification_decision_id"] = (
        _source_decision_id(report)
    )
    assert len(report) == 38
    assert set(report) == SOURCE_FIELDS
    return report


def _recompute_source(report: dict) -> None:
    report["authorization_status_meta_verification_decision_id"] = (
        _source_decision_id(report)
    )


def _recompute_output(report: dict) -> None:
    report["authorization_status_meta_meta_verification_decision_id"] = (
        _output_decision_id(report)
    )


def _create(source: object) -> dict:
    return create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report(
        source
    )


def _export(report: dict) -> str:
    return export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report(
        report
    )


def _assert_inert(report: dict) -> None:
    for field in GATE_FLAGS:
        assert report[field] is False, field


def _assert_sanitized_invalid_report(report: dict) -> None:
    assert report == {
        "ok": False,
        "authorization_status_meta_meta_verification_schema_version": "10GX.1",
        "authorization_status_meta_meta_verification_type": (
            "minimal_inert_model_routing_authorization_report_status_"
            "verification_verifier_status_verification_verifier_status_"
            "verification_verifier_status_report"
        ),
        "authorization_status_meta_meta_verification_scope": (
            "model_routing_authorization_report_status_verification_verifier_"
            "status_verification_verifier_status_verification_only"
        ),
        "authorization_status_meta_meta_verification_decision_id": report[
            "authorization_status_meta_meta_verification_decision_id"
        ],
        "source_meta_verification_schema_version": "",
        "source_meta_verification_decision_id": "",
        "source_meta_verification_status": "",
        "source_meta_verification_ok": False,
        "source_verification_schema_version": "",
        "source_verification_decision_id": "",
        "source_verification_status": "",
        "source_verification_ok": False,
        "source_status_report_schema_version": "",
        "source_status_report_decision_id": "",
        "source_status_report_status": "",
        "source_status_report_ok": False,
        "source_authorization_schema_version": "",
        "source_authorization_decision_id": "",
        "source_authorization_status": "",
        "source_authorization_ok": False,
        "source_provenance_decision_id": "",
        "source_policy_decision_id": "",
        "approval_decision_id": "",
        "approval_status": "",
        "artifact_class": "",
        "artifact_family": "",
        "authorized_lane": "",
        "provider_id": "",
        "provider_name": "",
        "pinned_model_id": "",
        "pinned_model_revision": "",
        "authorization_status_meta_meta_verification_status": (
            "invalid_meta_verification_report"
        ),
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "errors": [INVALID_SOURCE_ERROR],
    }
    assert len(report) == 42
    assert set(report) == OUTPUT_FIELDS
    assert report["authorization_status_meta_meta_verification_decision_id"] == (
        _output_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_public_api_accepts_exactly_one_meta_verification_report():
    signature = inspect.signature(
        create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report
    )
    assert tuple(signature.parameters) == ("meta_verification_report",)
    parameter = signature.parameters["meta_verification_report"]
    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.default is inspect.Parameter.empty


def test_exporter_accepts_exactly_one_meta_meta_verification_report():
    signature = inspect.signature(
        export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report
    )
    assert tuple(signature.parameters) == ("meta_meta_verification_report",)
    parameter = signature.parameters["meta_meta_verification_report"]
    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.default is inspect.Parameter.empty


def test_input_and_output_envelopes_have_exact_field_counts():
    source = _valid_meta_verification_report()
    report = _create(source)
    assert len(SOURCE_FIELDS) == 38
    assert len(OUTPUT_FIELDS) == 42
    assert set(source) == SOURCE_FIELDS
    assert set(report) == OUTPUT_FIELDS


def test_valid_authorized_source_produces_exact_meta_meta_report():
    source = _valid_meta_verification_report()
    report = _create(source)
    assert report == {
        "ok": True,
        "authorization_status_meta_meta_verification_schema_version": "10GX.1",
        "authorization_status_meta_meta_verification_type": (
            "minimal_inert_model_routing_authorization_report_status_"
            "verification_verifier_status_verification_verifier_status_"
            "verification_verifier_status_report"
        ),
        "authorization_status_meta_meta_verification_scope": (
            "model_routing_authorization_report_status_verification_verifier_"
            "status_verification_verifier_status_verification_only"
        ),
        "authorization_status_meta_meta_verification_decision_id": report[
            "authorization_status_meta_meta_verification_decision_id"
        ],
        "source_meta_verification_schema_version": "10GR.1",
        "source_meta_verification_decision_id": source[
            "authorization_status_meta_verification_decision_id"
        ],
        "source_meta_verification_status": (
            "verified_authorized_verification_status"
        ),
        "source_meta_verification_ok": True,
        "source_verification_schema_version": "10GL.1",
        "source_verification_decision_id": source[
            "source_verification_decision_id"
        ],
        "source_verification_status": "verified_authorized_status",
        "source_verification_ok": True,
        "source_status_report_schema_version": "10GF.1",
        "source_status_report_decision_id": source[
            "source_status_report_decision_id"
        ],
        "source_status_report_status": "authorized_status",
        "source_status_report_ok": True,
        "source_authorization_schema_version": "10FZ.1",
        "source_authorization_decision_id": source[
            "source_authorization_decision_id"
        ],
        "source_authorization_status": "authorized",
        "source_authorization_ok": True,
        "source_provenance_decision_id": source[
            "source_provenance_decision_id"
        ],
        "source_policy_decision_id": source["source_policy_decision_id"],
        "approval_decision_id": source["approval_decision_id"],
        "approval_status": "operator_approved",
        "artifact_class": source["artifact_class"],
        "artifact_family": source["artifact_family"],
        "authorized_lane": source["authorized_lane"],
        "provider_id": source["provider_id"],
        "provider_name": source["provider_name"],
        "pinned_model_id": source["pinned_model_id"],
        "pinned_model_revision": source["pinned_model_revision"],
        "authorization_status_meta_meta_verification_status": (
            "verified_authorized_meta_verification_status"
        ),
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "errors": [],
    }
    assert report["authorization_status_meta_meta_verification_decision_id"] == (
        _output_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


@pytest.mark.parametrize("approval_status", ("operator_denied", "operator_approved"))
def test_valid_not_authorized_source_produces_meta_meta_report(
    approval_status: str,
):
    source = _valid_meta_verification_report(
        "verified_not_authorized_verification_status",
        approval_status=approval_status,
    )
    report = _create(source)
    assert report["ok"] is True
    assert report["source_meta_verification_status"] == (
        "verified_not_authorized_verification_status"
    )
    assert report["source_verification_status"] == "verified_not_authorized_status"
    assert report["source_status_report_status"] == "not_authorized_status"
    assert report["source_authorization_status"] == "not_authorized"
    assert report["approval_status"] == approval_status
    assert report["authorization_status_meta_meta_verification_status"] == (
        "verified_not_authorized_meta_verification_status"
    )
    for field in OUTPUT_OK_FIELDS:
        assert report[field] is True
    assert report["errors"] == []
    assert report["authorization_status_meta_meta_verification_decision_id"] == (
        _output_decision_id(report)
    )
    _assert_inert(report)


def test_10gr_decision_id_commits_to_all_other_37_source_fields():
    source = _valid_meta_verification_report()
    original_id = source["authorization_status_meta_verification_decision_id"]
    source["artifact_class"] = "documentation_phase"
    _recompute_source(source)
    report = _create(source)
    assert source["authorization_status_meta_verification_decision_id"] == (
        _source_decision_id(source)
    )
    assert source["authorization_status_meta_verification_decision_id"] != original_id
    assert report["ok"] is True
    assert report["artifact_class"] == "documentation_phase"


def test_10gx_decision_id_commits_to_all_other_41_output_fields():
    report = _create(_valid_meta_verification_report())
    original_id = report[
        "authorization_status_meta_meta_verification_decision_id"
    ]
    report["artifact_class"] = "documentation_phase"
    _recompute_output(report)
    assert report["authorization_status_meta_meta_verification_decision_id"] == (
        _output_decision_id(report)
    )
    assert report[
        "authorization_status_meta_meta_verification_decision_id"
    ] != original_id


def test_tampered_10gr_decision_id_fails_closed():
    source = _valid_meta_verification_report()
    source["authorization_status_meta_verification_decision_id"] = (
        "10GR-" + "0" * 32
    )
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize("field", sorted(SOURCE_FIELDS))
def test_missing_source_field_fails_closed(field: str):
    source = _valid_meta_verification_report()
    source.pop(field)
    _assert_sanitized_invalid_report(_create(source))


def test_extra_source_field_fails_closed_without_leakage():
    source = _valid_meta_verification_report()
    source["raw_provider_payload"] = "must-not-leak"
    report = _create(source)
    _assert_sanitized_invalid_report(report)
    assert "must-not-leak" not in json.dumps(report)


@pytest.mark.parametrize("value", (None, [], "10GR", 7, True, object()))
def test_missing_or_non_dict_source_fails_closed(value: object):
    _assert_sanitized_invalid_report(_create(value))


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

    report = _create(_HostileDict(_valid_meta_verification_report()))
    _assert_sanitized_invalid_report(report)
    assert _HostileDict.get_called is False
    assert _HostileDict.iter_called is False


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_meta_verification_report()
    value = source.pop("artifact_class")
    source[type("StrSubclass", (str,), {})("artifact_class")] = value
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize("field", SOURCE_STRING_FIELDS)
@pytest.mark.parametrize("kind", ("non_string", "subclass"))
def test_source_string_fields_require_exact_built_in_strings(
    field: str,
    kind: str,
):
    source = _valid_meta_verification_report()
    source[field] = (
        7
        if kind == "non_string"
        else type("StrSubclass", (str,), {})(source[field])
    )
    if field != "authorization_status_meta_verification_decision_id":
        _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize("field", SOURCE_OK_FIELDS)
@pytest.mark.parametrize("value", (False, 1, 0))
def test_source_ok_fields_must_be_exactly_true(field: str, value: object):
    source = _valid_meta_verification_report()
    source[field] = value
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize("field", GATE_FLAGS)
@pytest.mark.parametrize("value", (True, 0))
def test_source_gate_flags_must_be_exactly_false(field: str, value: object):
    source = _valid_meta_verification_report()
    source[field] = value
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authorization_status_meta_verification_schema_version", "10GR.2"),
        ("authorization_status_meta_verification_type", "future_report"),
        ("authorization_status_meta_verification_scope", "future_scope"),
        ("source_verification_schema_version", "10GL.2"),
        ("source_verification_status", "future_status"),
        ("source_status_report_schema_version", "10GF.2"),
        ("source_status_report_status", "future_status"),
        ("source_authorization_schema_version", "10FZ.2"),
        ("source_authorization_status", "future_status"),
        ("approval_status", "approved"),
        ("authorization_status_meta_verification_status", "future_status"),
        ("claim_boundary", "expanded_boundary"),
    ),
)
def test_wrong_source_identity_or_status_fails_closed(field: str, value: str):
    source = _valid_meta_verification_report()
    source[field] = value
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize(
    ("meta_status", "verification_status", "report_status", "authorization_status"),
    (
        (
            "verified_authorized_verification_status",
            "verified_not_authorized_status",
            "authorized_status",
            "authorized",
        ),
        (
            "verified_authorized_verification_status",
            "verified_authorized_status",
            "not_authorized_status",
            "authorized",
        ),
        (
            "verified_not_authorized_verification_status",
            "verified_not_authorized_status",
            "not_authorized_status",
            "authorized",
        ),
        (
            "verified_not_authorized_verification_status",
            "verified_authorized_status",
            "not_authorized_status",
            "not_authorized",
        ),
    ),
)
def test_source_status_layers_must_be_consistent(
    meta_status: str,
    verification_status: str,
    report_status: str,
    authorization_status: str,
):
    source = _valid_meta_verification_report(meta_status)
    source["source_verification_status"] = verification_status
    source["source_status_report_status"] = report_status
    source["source_authorization_status"] = authorization_status
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


def test_verified_authorized_source_requires_operator_approved():
    source = _valid_meta_verification_report()
    source["approval_status"] = "operator_denied"
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


@pytest.mark.parametrize(
    ("field", "prefix", "other_prefix"),
    (
        ("authorization_status_meta_verification_decision_id", "10GR-", "10GX-"),
        ("source_verification_decision_id", "10GL-", "10GR-"),
        ("source_status_report_decision_id", "10GF-", "10GL-"),
        ("source_authorization_decision_id", "10FZ-", "10GF-"),
        ("source_provenance_decision_id", "10FT-", "10FZ-"),
        ("source_policy_decision_id", "10FT-POLICY-", "10FT-"),
        ("approval_decision_id", "10FZ-APPROVAL-", "10FZ-"),
    ),
)
@pytest.mark.parametrize("suffix", ("", "a" * 31, "a" * 33, "A" * 32, "g" * 32))
def test_malformed_source_decision_ids_fail_closed(
    field: str,
    prefix: str,
    other_prefix: str,
    suffix: str,
):
    source = _valid_meta_verification_report()
    source[field] = (other_prefix + "a" * 32) if not suffix else prefix + suffix
    if field != "authorization_status_meta_verification_decision_id":
        _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


def test_deeper_source_ids_and_metadata_are_syntax_only_not_recomputed():
    source = _valid_meta_verification_report()
    source["source_verification_decision_id"] = "10GL-" + "0" * 32
    source["source_status_report_decision_id"] = "10GF-" + "1" * 32
    source["source_authorization_decision_id"] = "10FZ-" + "2" * 32
    source["source_provenance_decision_id"] = "10FT-" + "3" * 32
    source["source_policy_decision_id"] = "10FT-POLICY-" + "4" * 32
    source["approval_decision_id"] = "10FZ-APPROVAL-" + "5" * 32
    source["artifact_class"] = "documentation_phase"
    source["artifact_family"] = "external_governance"
    source["authorized_lane"] = "lane:external-beta"
    source["provider_id"] = "provider:external"
    source["provider_name"] = "external"
    source["pinned_model_id"] = "model:external-1"
    source["pinned_model_revision"] = "external-revision-2"
    _recompute_source(source)
    report = _create(source)
    assert report["ok"] is True
    assert report["source_verification_decision_id"] == "10GL-" + "0" * 32
    assert report["source_status_report_decision_id"] == "10GF-" + "1" * 32
    assert report["source_authorization_decision_id"] == "10FZ-" + "2" * 32
    assert report["source_provenance_decision_id"] == "10FT-" + "3" * 32
    assert report["source_policy_decision_id"] == "10FT-POLICY-" + "4" * 32
    assert report["approval_decision_id"] == "10FZ-APPROVAL-" + "5" * 32
    assert report["artifact_class"] == "documentation_phase"
    assert report["artifact_family"] == "external_governance"
    assert report["authorized_lane"] == "lane:external-beta"
    assert report["provider_id"] == "provider:external"
    assert report["provider_name"] == "external"
    assert report["pinned_model_id"] == "model:external-1"
    assert report["pinned_model_revision"] == "external-revision-2"
    assert json.loads(_export(report)) == report


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authorized_lane", "authority:wrong-prefix"),
        ("provider_id", "model:wrong-prefix"),
        ("pinned_model_id", "provider:wrong-prefix"),
        ("authorized_lane", "lane:"),
        ("provider_id", "provider:"),
        ("pinned_model_id", "model:"),
    ),
)
def test_source_identity_fields_require_safe_prefixes(field: str, value: str):
    source = _valid_meta_verification_report()
    source[field] = value
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


def test_provider_id_and_name_must_be_internally_consistent():
    source = _valid_meta_verification_report()
    source["provider_id"] = "provider:other"
    _recompute_source(source)
    _assert_sanitized_invalid_report(_create(source))


def test_list_subclasses_and_string_subclass_items_fail_closed():
    list_subclass = type("ListSubclass", (list,), {})
    str_subclass = type("StrSubclass", (str,), {})
    first = _valid_meta_verification_report()
    first["errors"] = list_subclass([])
    second = _valid_meta_verification_report()
    second["errors"] = [str_subclass("raw source error")]
    for source in (first, second):
        _recompute_source(source)
        _assert_sanitized_invalid_report(_create(source))


def test_raw_source_errors_fail_closed_without_leakage():
    source = _valid_meta_verification_report()
    source["errors"] = ["raw 10GR source failure"]
    _recompute_source(source)
    report = _create(source)
    _assert_sanitized_invalid_report(report)
    assert "raw 10GR source failure" not in json.dumps(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("artifact_class", "../../raw_config"),
        ("artifact_family", "equality-signal-value"),
        ("authorized_lane", "lane:sk-proj-example"),
        ("provider_name", "access_token"),
        ("provider_name", "auth_token_deadbeef"),
        ("pinned_model_revision", "api_key"),
        ("pinned_model_revision", "github_pat_abcdef"),
        ("pinned_model_revision", "glpat-abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "hf_abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "xapp-1-abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "C:private.txt"),
        ("authorized_lane", "lane:C:private.txt"),
        ("authorized_lane", "lane:lane:C:private.txt"),
        ("pinned_model_id", "model:C:private.txt"),
        ("pinned_model_revision", "revision:C:private.txt"),
        ("pinned_model_revision", "password"),
        ("pinned_model_revision", "credential"),
        ("pinned_model_revision", "ghp_abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "AKIAABCDEFGHIJKLMNOP"),
        ("pinned_model_revision", "pk-live-example"),
        ("pinned_model_revision", "/tmp/private.txt"),
        ("pinned_model_revision", "C:\\private.txt"),
        ("authorized_lane", "lane:/tmp/private.txt"),
        ("pinned_model_id", "model:\\server\\private.txt"),
        ("pinned_model_revision", "secret"),
    ),
)
def test_tainted_source_text_fails_closed_without_leakage(
    field: str,
    value: str,
):
    source = _valid_meta_verification_report()
    source[field] = value
    if field == "provider_name":
        source["provider_id"] = f"provider:{value}"
    _recompute_source(source)
    report = _create(source)
    _assert_sanitized_invalid_report(report)
    assert value not in json.dumps(report)


@pytest.mark.parametrize("value", ("pathfinder", "xapplication"))
def test_benign_sensitive_prefix_near_matches_remain_valid(value: str):
    source = _valid_meta_verification_report()
    source["pinned_model_revision"] = value
    _recompute_source(source)

    report = _create(source)

    assert report["ok"] is True
    assert report["pinned_model_revision"] == value
    assert json.loads(_export(report)) == report


def test_caller_owned_list_is_detached_and_source_is_not_mutated():
    source = _valid_meta_verification_report()
    before = json.loads(json.dumps(source))
    report = _create(source)
    assert source == before
    source["errors"].append("late raw source error")
    assert report["errors"] == []
    assert "late raw source error" not in json.dumps(report)


def test_invalid_creator_input_is_not_mutated():
    source = _valid_meta_verification_report()
    source["errors"] = ["raw source detail"]
    before = json.loads(json.dumps(source))
    _assert_sanitized_invalid_report(_create(source))
    assert source == before


def test_output_contains_only_sanitized_status_metadata():
    report = _create(_valid_meta_verification_report())
    serialized = json.dumps(report)
    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    for marker in (
        "api_key",
        "access_token",
        "raw_config",
        "raw_provider_payload",
        "equality_signal_value",
        "equality_signal_type",
        "world-sim/data",
    ):
        assert marker not in serialized


def test_export_is_deterministic_for_all_meta_meta_statuses():
    reports = (
        _create(_valid_meta_verification_report()),
        _create(
            _valid_meta_verification_report(
                "verified_not_authorized_verification_status"
            )
        ),
        _create(None),
    )
    for report in reports:
        first = _export(report)
        second = _export(dict(report))
        assert first == second
        assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
        assert json.loads(first) == report


def test_exporter_does_not_mutate_valid_or_rejected_inputs():
    valid = _create(_valid_meta_verification_report())
    valid_before = json.loads(json.dumps(valid))
    _export(valid)
    assert valid == valid_before
    invalid = dict(valid)
    invalid["errors"] = ["raw source detail"]
    invalid_before = json.loads(json.dumps(invalid))
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(invalid)
    assert invalid == invalid_before


def test_export_accepts_not_authorized_status_with_operator_approved():
    report = _create(
        _valid_meta_verification_report(
            "verified_not_authorized_verification_status",
            approval_status="operator_approved",
        )
    )
    assert json.loads(_export(report)) == report


def test_export_rejects_rehashed_immediate_10gr_decision_id_rebinding():
    report = _create(_valid_meta_verification_report())
    report["source_meta_verification_decision_id"] = "10GR-" + "0" * 32
    _recompute_output(report)

    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_export_rejects_authorized_status_with_operator_denied_after_rehash():
    report = _create(_valid_meta_verification_report())
    report["approval_status"] = "operator_denied"
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        (
            "authorization_status_meta_meta_verification_status",
            "verified_not_authorized_meta_verification_status",
        ),
        (
            "source_meta_verification_status",
            "verified_not_authorized_verification_status",
        ),
        ("source_verification_status", "verified_not_authorized_status"),
        ("source_status_report_status", "not_authorized_status"),
        ("source_authorization_status", "not_authorized"),
        ("source_meta_verification_ok", False),
        ("source_verification_ok", False),
        ("source_status_report_ok", False),
        ("source_authorization_ok", False),
    ),
)
def test_export_rejects_rehashed_status_mismatches(field: str, value: object):
    report = _create(_valid_meta_verification_report())
    report[field] = value
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("pinned_model_revision", "glpat-abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "hf_abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "xapp-1-abcdefghijklmnopqrstuvwxyz"),
        ("pinned_model_revision", "C:private.txt"),
        ("authorized_lane", "lane:C:private.txt"),
        ("authorized_lane", "lane:lane:C:private.txt"),
        ("pinned_model_id", "model:C:private.txt"),
        ("pinned_model_revision", "revision:C:private.txt"),
    ),
)
def test_export_rejects_rehashed_sensitive_or_path_shaped_metadata(
    field: str,
    value: str,
):
    report = _create(_valid_meta_verification_report())
    report[field] = value
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize("field", sorted(OUTPUT_FIELDS))
def test_export_rejects_missing_output_field(field: str):
    report = _create(_valid_meta_verification_report())
    report.pop(field)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_export_rejects_unexpected_or_forbidden_fields():
    report = _create(_valid_meta_verification_report())
    report["raw_provider_payload"] = "must-not-export"
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        iter_called = False

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(_create(_valid_meta_verification_report()))
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)
    assert _TaintedReport.iter_called is False


def test_export_rejects_string_subclass_dictionary_key():
    report = _create(_valid_meta_verification_report())
    value = report.pop("artifact_class")
    report[type("StrSubclass", (str,), {})("artifact_class")] = value
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize("field", OUTPUT_SOURCE_STRING_FIELDS)
def test_export_invalid_report_requires_each_source_string_neutral(field: str):
    report = _create(None)
    report[field] = "tainted"
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize(
    "field",
    (
        "source_meta_verification_ok",
        "source_verification_ok",
        "source_status_report_ok",
        "source_authorization_ok",
    ),
)
def test_export_invalid_report_requires_each_source_ok_false(field: str):
    report = _create(None)
    report[field] = True
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("authorization_status_meta_meta_verification_schema_version", "10GX.2"),
        ("authorization_status_meta_meta_verification_type", "future_report"),
        ("authorization_status_meta_meta_verification_scope", "future_scope"),
        (
            "authorization_status_meta_meta_verification_decision_id",
            "10GX-tainted",
        ),
        ("source_meta_verification_schema_version", "10GR.2"),
        ("source_meta_verification_decision_id", "10GR-tainted"),
        ("source_meta_verification_status", "future_status"),
        ("source_meta_verification_ok", 1),
        ("source_verification_schema_version", "10GL.2"),
        ("source_verification_decision_id", "10GL-tainted"),
        ("source_verification_status", "future_status"),
        ("source_verification_ok", 1),
        ("source_status_report_schema_version", "10GF.2"),
        ("source_status_report_decision_id", "10GF-tainted"),
        ("source_status_report_status", "future_status"),
        ("source_status_report_ok", 1),
        ("source_authorization_schema_version", "10FZ.2"),
        ("source_authorization_decision_id", "10FZ-tainted"),
        ("source_authorization_status", "future_status"),
        ("source_authorization_ok", 1),
        ("source_provenance_decision_id", "10FT-tainted"),
        ("source_policy_decision_id", "10FT-POLICY-tainted"),
        ("approval_decision_id", "10FZ-APPROVAL-tainted"),
        ("approval_status", "approved"),
        ("authorized_lane", "authority:wrong-prefix"),
        ("provider_id", "model:wrong-prefix"),
        ("pinned_model_id", "provider:wrong-prefix"),
        ("authorization_status_meta_meta_verification_status", "future_status"),
        ("runtime_allowed", 0),
        ("claim_boundary", "expanded_boundary"),
        ("errors", ["raw source error"]),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = _create(_valid_meta_verification_report())
    report[field] = value
    if field != "authorization_status_meta_meta_verification_decision_id":
        _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize("field", OUTPUT_OK_FIELDS)
def test_export_rejects_boolean_integer_drift(field: str):
    report = _create(_valid_meta_verification_report())
    report[field] = 1
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_export_rejects_each_gate_flag_integer_drift(field: str):
    report = _create(_valid_meta_verification_report())
    report[field] = 0
    _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize("field", OUTPUT_STRING_FIELDS)
def test_export_rejects_string_subclass_fields(field: str):
    report = _create(_valid_meta_verification_report())
    report[field] = type("StrSubclass", (str,), {})(report[field])
    if field != "authorization_status_meta_meta_verification_decision_id":
        _recompute_output(report)
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_export_rejects_list_subclass_and_string_subclass_error_items():
    base = _create(_valid_meta_verification_report())
    first = dict(base)
    first["errors"] = type("ListSubclass", (list,), {})([])
    second = dict(base)
    second["errors"] = [type("StrSubclass", (str,), {})("tainted")]
    for report in (first, second):
        _recompute_output(report)
        with pytest.raises(
            ValueError,
            match="exact 10GX meta-meta-verification report shape",
        ):
            _export(report)


def test_export_invalid_report_rejects_equal_string_subclass_error_item():
    report = _create(None)
    report["errors"] = [
        type("StrSubclass", (str,), {})(INVALID_SOURCE_ERROR)
    ]
    _recompute_output(report)

    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


@pytest.mark.parametrize(
    "status",
    (
        "verified_authorized_verification_status",
        "verified_not_authorized_verification_status",
    ),
)
def test_export_rejects_tampered_own_decision_id_for_each_valid_status(
    status: str,
):
    report = _create(_valid_meta_verification_report(status))
    report["authorization_status_meta_meta_verification_decision_id"] = (
        "10GX-" + "0" * 32
    )
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_export_rejects_tampered_own_decision_id_for_invalid_status():
    report = _create(None)
    report["authorization_status_meta_meta_verification_decision_id"] = (
        "10GX-" + "0" * 32
    )
    with pytest.raises(ValueError, match="exact 10GX meta-meta-verification report shape"):
        _export(report)


def test_gate_flags_are_false_on_valid_and_invalid_reports():
    for report in (
        _create(_valid_meta_verification_report()),
        _create(
            _valid_meta_verification_report(
                "verified_not_authorized_verification_status"
            )
        ),
        _create(None),
    ):
        _assert_inert(report)


def test_module_imports_only_allowed_standard_library_modules():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    plain_imports = []
    from_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            plain_imports.extend((alias.name, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            from_imports.append(
                (
                    node.module,
                    tuple((alias.name, alias.asname) for alias in node.names),
                )
            )
    assert sorted(plain_imports) == [("hashlib", None), ("json", None)]
    assert sorted(from_imports) == [
        ("__future__", (("annotations", None),)),
        ("typing", (("Any", None),)),
    ]


def test_module_has_no_backend_prior_phase_or_writer_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden_names = (
        "append_inert_ledger_record",
        "verify_minimal_inert_ledger_status_digest_verification_report",
        "create_minimal_inert_ledger_status_digest_verification_verifier_status_report",
        "create_minimal_inert_model_routing_provenance_report",
        "export_minimal_inert_model_routing_provenance_report",
        "create_minimal_inert_model_routing_approval_authorization_report",
        "export_minimal_inert_model_routing_approval_authorization_report",
        "create_minimal_inert_model_routing_authorization_report_status_report",
        "export_minimal_inert_model_routing_authorization_report_status_report",
        "create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_report",
        "export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_report",
        "create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report",
        "export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report",
        "backend.",
    )
    for name in forbidden_names:
        assert name not in source


def _call_identifiers(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {*_call_identifiers(node.value), node.attr}
    if isinstance(node, ast.Call):
        return _call_identifiers(node.func)
    if isinstance(node, ast.Subscript):
        identifiers = _call_identifiers(node.value)
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            identifiers.add(node.slice.value)
        return identifiers
    return set()


def test_module_has_no_file_process_network_mutation_or_dynamic_lookup_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "__import__",
        "__getattribute__",
        "__subclasses__",
        "__class__",
        "__dict__",
        "__mro__",
        "__bases__",
        "eval",
        "exec",
        "compile",
        "import_module",
        "getattr",
        "setattr",
        "globals",
        "locals",
        "vars",
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
        "request",
        "get",
        "post",
        "send",
        "invoke",
        "generate",
        "launch",
        "emit_event",
        "create_event",
        "map_lookup",
        "append_inert_ledger_record",
        "__builtins__",
        "__globals__",
        "append",
        "clear",
        "extend",
        "insert",
        "pop",
        "popitem",
        "setdefault",
        "update",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert forbidden_calls.isdisjoint(_call_identifiers(node.func))
    for node in ast.walk(tree):
        value = None
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            value = node.value
        if value is not None:
            assert forbidden_calls.isdisjoint(_call_identifiers(value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_calls
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_calls


def test_module_calls_only_fixed_allowlisted_callables():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed_call_names = {
        "ValueError",
        "_canonical_json",
        "_hash_canonical",
        "_is_decision_id",
        "_is_lower_hex",
        "_is_prefixed_id",
        "_is_safe_text",
        "_source_decision_material",
        "_source_decision_material_from_output",
        "_meta_meta_decision_material",
        "_validated_meta_verification_snapshot",
        "_meta_meta_verification_report",
        "all",
        "any",
        "dict",
        "dumps",
        "encode",
        "frozenset",
        "hexdigest",
        "isalnum",
        "join",
        "len",
        "list",
        "lower",
        "set",
        "sha256",
        "sorted",
        "startswith",
        "count",
        "tuple",
        "type",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        assert isinstance(node.func, (ast.Name, ast.Attribute))
        call_name = (
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        )
        assert call_name in allowed_call_names


def test_module_does_not_mutate_or_delete_public_input_parameters():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_parameters = {
        "create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report": {
            "meta_verification_report"
        },
        "export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report": {
            "meta_meta_verification_report"
        },
        "_validated_meta_verification_snapshot": {"source"},
    }

    def _root_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            return _root_name(node.value)
        return None

    for function in (
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in public_parameters
    ):
        aliases = set(public_parameters[function.name])
        changed = True
        while changed:
            changed = False
            for node in ast.walk(function):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                if not isinstance(node.value, ast.Name) or node.value.id not in aliases:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
        for node in ast.walk(function):
            targets: list[ast.AST] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            elif isinstance(node, ast.AugAssign):
                targets.append(node.target)
            elif isinstance(node, ast.Delete):
                targets.extend(node.targets)
            for target in targets:
                if isinstance(target, ast.Name):
                    continue
                assert _root_name(target) not in aliases
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {
                    "append",
                    "clear",
                    "extend",
                    "insert",
                    "pop",
                    "popitem",
                    "remove",
                    "setdefault",
                    "sort",
                    "update",
                }:
                    assert _root_name(node.func.value) not in aliases


def test_module_has_no_operational_provider_model_agent_config_runtime_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _qualified_call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = _qualified_call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        if isinstance(node, ast.Call):
            return _qualified_call_name(node.func)
        if isinstance(node, ast.Subscript):
            return _qualified_call_name(node.value)
        return ""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _qualified_call_name(node.func).lower()
        for marker in (
            "provider",
            "model",
            "agent",
            "config",
            "runtime",
            "request",
            "http",
        ):
            assert marker not in call_name


def test_module_has_no_forbidden_paths_clients_or_raw_sensitive_markers():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for marker in (
        "open(",
        "pathlib",
        "os.",
        "glob",
        "walk",
        "listdir",
        "iterdir",
        "subprocess",
        "requests",
        "httpx",
        "provider_client",
        "provider_api",
        "call_provider",
        "model_client",
        "model_api",
        "invoke_model",
        "launch_agent",
        "agent_client",
        "config_path",
        "config_file",
        "api_key",
        "token",
        "secret",
        "Kilo",
        "OpenCode",
        "Wave",
        "Hermes",
        "world-sim/data",
    ):
        assert marker not in source


def test_snapshot_precedes_key_validation_for_input_and_exporter():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    validator = functions["_validated_meta_verification_snapshot"]
    exporter = functions[
        "export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report"
    ]
    assert validator is not None
    assert exporter is not None
    assert validator.index("snapshot = dict(source)") < validator.index(
        "type(key) is not str for key in snapshot"
    )
    assert exporter.index("report = dict(meta_meta_verification_report)") < exporter.index(
        "type(key) is not str for key in report"
    )


def test_lists_are_detached_before_content_validation_and_export():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    validator = functions["_validated_meta_verification_snapshot"]
    exporter = functions[
        "export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_verification_verifier_status_report"
    ]
    assert validator is not None
    assert exporter is not None
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "source_errors != []"
    )
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "report_errors != expected_errors"
    )
