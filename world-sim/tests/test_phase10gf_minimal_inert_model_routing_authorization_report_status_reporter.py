"""Phase 10GF - inert model-routing authorization status reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_model_routing_approval_authorization_reporter import (
    create_minimal_inert_model_routing_approval_authorization_report,
)
from backend.world.local_minimal_inert_model_routing_authorization_report_status_reporter import (
    create_minimal_inert_model_routing_authorization_report_status_report,
    export_minimal_inert_model_routing_authorization_report_status_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_model_routing_authorization_report_status_reporter.py"
)

FORBIDDEN_BOUNDARIES = [
    "agent_launch",
    "config_mutation",
    "filesystem_scan",
    "gate7_activity",
    "model_invocation",
    "provider_call",
    "runtime_execution",
    "world_sim_data_access",
]

SOURCE_FIELDS = {
    "ok",
    "authorization_report_schema_version",
    "authorization_report_type",
    "authorization_report_scope",
    "authorization_report_decision_id",
    "source_provenance_schema_version",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "approval_schema_version",
    "approval_revision",
    "approval_decision_id",
    "approval_status",
    "approval_authority_id",
    "approval_authority_basis",
    "approved_action",
    "forbidden_boundaries",
    "authorization_report_status",
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
    "authorization_status_report_schema_version",
    "authorization_status_report_type",
    "authorization_status_report_scope",
    "authorization_status_report_decision_id",
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
    "authorization_status_report_status",
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

SOURCE_STRING_FIELDS = (
    "authorization_report_schema_version",
    "authorization_report_type",
    "authorization_report_scope",
    "authorization_report_decision_id",
    "source_provenance_schema_version",
    "source_provenance_decision_id",
    "source_policy_decision_id",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "approval_schema_version",
    "approval_decision_id",
    "approval_status",
    "approval_authority_id",
    "approval_authority_basis",
    "approved_action",
    "authorization_report_status",
    "claim_boundary",
)

OUTPUT_STRING_FIELDS = (
    "authorization_status_report_schema_version",
    "authorization_status_report_type",
    "authorization_status_report_scope",
    "authorization_status_report_decision_id",
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
    "authorization_status_report_status",
    "claim_boundary",
)

SOURCE_CLAIM_BOUNDARY = (
    "report one model routing approval authorization decision only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

STATUS_REPORT_CLAIM_BOUNDARY = (
    "report one 10FZ model routing authorization status only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "re-authorization, or gate-7 activity"
)

INVALID_SOURCE_ERROR = (
    "authorization_report is not a valid 10FZ authorization report"
)

FORBIDDEN_OUTPUT_FIELDS = {
    "authorization_report_type",
    "authorization_report_scope",
    "source_provenance_schema_version",
    "authority_id",
    "authority_basis",
    "approval_schema_version",
    "approval_revision",
    "approval_authority_id",
    "approval_authority_basis",
    "approved_action",
    "forbidden_boundaries",
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
        for key in sorted(SOURCE_FIELDS - {"authorization_report_decision_id"})
    }
    return "10FZ-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _status_decision_id(report: dict) -> str:
    material = {
        key: report[key]
        for key in sorted(
            OUTPUT_FIELDS - {"authorization_status_report_decision_id"}
        )
    }
    return "10GF-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_authorization_report(
    status: str = "authorized",
    *,
    approval_status: str | None = None,
) -> dict:
    if approval_status is None:
        approval_status = (
            "operator_approved" if status == "authorized" else "operator_denied"
        )
    report = {
        "ok": True,
        "authorization_report_schema_version": "10FZ.1",
        "authorization_report_type": (
            "minimal_inert_model_routing_approval_authorization_report"
        ),
        "authorization_report_scope": (
            "model_routing_approval_authorization_report_only"
        ),
        "authorization_report_decision_id": "",
        "source_provenance_schema_version": "10FT.1",
        "source_provenance_decision_id": "10FT-" + "a" * 32,
        "source_policy_decision_id": "10FT-POLICY-" + "b" * 32,
        "artifact_class": "implementation_phase",
        "artifact_family": "governance_provenance",
        "authorized_lane": "lane:gpt-5-6-sol",
        "authority_id": "authority:operator-approved-10ft",
        "authority_basis": "phase_10fr_operator_authorization",
        "provider_id": "provider:openai",
        "provider_name": "openai",
        "pinned_model_id": "model:gpt-5-6-sol",
        "pinned_model_revision": "2026-07-14",
        "approval_schema_version": "10FZ.APPROVAL.1",
        "approval_revision": 1,
        "approval_decision_id": "10FZ-APPROVAL-" + "c" * 32,
        "approval_status": approval_status,
        "approval_authority_id": "approval-authority:operator-10fz",
        "approval_authority_basis": "phase_10fx_operator_authorization",
        "approved_action": "authorize_routing_execution",
        "forbidden_boundaries": list(FORBIDDEN_BOUNDARIES),
        "authorization_report_status": status,
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
    report["authorization_report_decision_id"] = _source_decision_id(report)
    assert len(report) == 35
    assert set(report) == SOURCE_FIELDS
    return report


def _recompute_source(report: dict) -> None:
    report["authorization_report_decision_id"] = _source_decision_id(report)


def _recompute_status(report: dict) -> None:
    report["authorization_status_report_decision_id"] = _status_decision_id(report)


def _assert_inert(report: dict) -> None:
    for field in GATE_FLAGS:
        assert report[field] is False, field


def _assert_sanitized_invalid_report(report: dict) -> None:
    assert report == {
        "ok": False,
        "authorization_status_report_schema_version": "10GF.1",
        "authorization_status_report_type": (
            "minimal_inert_model_routing_authorization_report_status_report"
        ),
        "authorization_status_report_scope": (
            "model_routing_authorization_report_status_only"
        ),
        "authorization_status_report_decision_id": report[
            "authorization_status_report_decision_id"
        ],
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
        "authorization_status_report_status": "invalid_report",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": STATUS_REPORT_CLAIM_BOUNDARY,
        "errors": [INVALID_SOURCE_ERROR],
    }
    assert len(report) == 30
    assert set(report) == OUTPUT_FIELDS
    assert report["authorization_status_report_decision_id"] == (
        _status_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def _valid_10fz_producer_report() -> dict:
    provenance = {
        "ok": True,
        "provenance_report_schema_version": "10FT.1",
        "provenance_report_type": "minimal_inert_model_routing_provenance_report",
        "provenance_report_scope": "model_routing_provenance_report_only",
        "provenance_report_decision_id": "10FT-" + "d" * 32,
        "source_policy_schema_version": "10FT.POLICY.1",
        "source_policy_revision": 1,
        "source_policy_decision_id": "10FT-POLICY-" + "e" * 32,
        "artifact_class": "implementation_phase",
        "artifact_family": "governance_provenance",
        "authorized_lane": "lane:gpt-5-6-sol",
        "authority_id": "authority:operator-approved-10ft",
        "authority_basis": "phase_10fr_operator_authorization",
        "provider_id": "provider:openai",
        "provider_name": "openai",
        "pinned_model_id": "model:gpt-5-6-sol",
        "pinned_model_revision": "2026-07-14",
        "forbidden_boundaries": list(FORBIDDEN_BOUNDARIES),
        "provenance_report_status": "verified_provenance",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": (
            "report one model routing provenance policy only; no runtime "
            "execution, provider call, model invocation, filesystem scan, config "
            "mutation, agent launch, world-data access, ledger access, write, "
            "repair, or gate-7 activity"
        ),
        "errors": [],
    }
    approval = {
        "approval_schema_version": "10FZ.APPROVAL.1",
        "approval_revision": 1,
        "approval_type": (
            "minimal_inert_model_routing_approval_authorization_artifact"
        ),
        "approval_scope": "model_routing_approval_authorization_only",
        "approval_decision_id": "",
        "approval_status": "operator_approved",
        "approval_authority_id": "approval-authority:operator-10fz",
        "approval_authority_basis": "phase_10fx_operator_authorization",
        "approver_lane": "lane:operator-governance",
        "approved_action": "authorize_routing_execution",
        "approved_artifact_class": provenance["artifact_class"],
        "approved_artifact_family": provenance["artifact_family"],
        "approved_authorized_lane": provenance["authorized_lane"],
        "approved_authority_id": provenance["authority_id"],
        "approved_authority_basis": provenance["authority_basis"],
        "approved_provider_id": provenance["provider_id"],
        "approved_provider_name": provenance["provider_name"],
        "approved_pinned_model_id": provenance["pinned_model_id"],
        "approved_pinned_model_revision": provenance["pinned_model_revision"],
        "referenced_provenance_report_decision_id": provenance[
            "provenance_report_decision_id"
        ],
        "referenced_source_policy_decision_id": provenance[
            "source_policy_decision_id"
        ],
        "forbidden_boundaries": list(FORBIDDEN_BOUNDARIES),
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "provider_call_allowed": False,
        "model_invocation_allowed": False,
        "config_mutation_allowed": False,
        "agent_launch_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": (
            "approve or deny one verified model routing provenance report for "
            "execution eligibility only; no runtime execution, provider call, "
            "model invocation, filesystem scan, config mutation, agent launch, "
            "world-data access, ledger access, write, repair, or gate-7 activity"
        ),
        "errors": [],
    }
    approval_material = {
        key: approval[key]
        for key in sorted(set(approval) - {"approval_decision_id"})
    }
    approval["approval_decision_id"] = "10FZ-APPROVAL-" + hashlib.sha256(
        _canonical_json(approval_material).encode("utf-8")
    ).hexdigest()[:32]
    return create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )


def test_public_api_accepts_exactly_one_caller_supplied_authorization_report():
    signature = inspect.signature(
        create_minimal_inert_model_routing_authorization_report_status_report
    )

    assert tuple(signature.parameters) == ("authorization_report",)
    parameter = signature.parameters["authorization_report"]
    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.default is inspect.Parameter.empty


def test_exporter_accepts_exactly_one_status_report():
    signature = inspect.signature(
        export_minimal_inert_model_routing_authorization_report_status_report
    )

    assert tuple(signature.parameters) == ("status_report",)
    parameter = signature.parameters["status_report"]
    assert parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameter.default is inspect.Parameter.empty


def test_input_and_output_envelopes_have_exact_field_counts():
    source = _valid_authorization_report()
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert len(SOURCE_FIELDS) == 35
    assert len(OUTPUT_FIELDS) == 30
    assert set(source) == SOURCE_FIELDS
    assert set(report) == OUTPUT_FIELDS


def test_valid_authorized_source_produces_exact_authorized_status_report():
    source = _valid_authorization_report()

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert report == {
        "ok": True,
        "authorization_status_report_schema_version": "10GF.1",
        "authorization_status_report_type": (
            "minimal_inert_model_routing_authorization_report_status_report"
        ),
        "authorization_status_report_scope": (
            "model_routing_authorization_report_status_only"
        ),
        "authorization_status_report_decision_id": report[
            "authorization_status_report_decision_id"
        ],
        "source_authorization_schema_version": "10FZ.1",
        "source_authorization_decision_id": source[
            "authorization_report_decision_id"
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
        "authorization_status_report_status": "authorized_status",
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
    assert report["authorization_status_report_decision_id"] == (
        _status_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


@pytest.mark.parametrize("approval_status", ("operator_denied", "operator_approved"))
def test_valid_not_authorized_source_produces_not_authorized_status_report(
    approval_status: str,
):
    source = _valid_authorization_report(
        "not_authorized",
        approval_status=approval_status,
    )

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert report["ok"] is True
    assert report["source_authorization_status"] == "not_authorized"
    assert report["source_authorization_ok"] is True
    assert report["approval_status"] == approval_status
    assert report["authorization_status_report_status"] == "not_authorized_status"
    assert report["errors"] == []
    assert report["authorization_status_report_decision_id"] == (
        _status_decision_id(report)
    )
    _assert_inert(report)


def test_10fz_decision_id_commits_to_all_other_34_source_fields():
    source = _valid_authorization_report()
    original_id = source["authorization_report_decision_id"]
    source["artifact_class"] = "documentation_phase"
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert source["authorization_report_decision_id"] == _source_decision_id(source)
    assert source["authorization_report_decision_id"] != original_id
    assert report["ok"] is True
    assert report["artifact_class"] == "documentation_phase"


def test_10gf_decision_id_commits_to_all_other_29_output_fields():
    source = _valid_authorization_report()
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )
    original_id = report["authorization_status_report_decision_id"]
    report["artifact_class"] = "documentation_phase"
    _recompute_status(report)

    assert report["authorization_status_report_decision_id"] == (
        _status_decision_id(report)
    )
    assert report["authorization_status_report_decision_id"] != original_id


def test_tampered_10fz_decision_id_fails_closed():
    source = _valid_authorization_report()
    source["authorization_report_decision_id"] = "10FZ-" + "f" * 32

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", sorted(SOURCE_FIELDS))
def test_missing_source_field_fails_closed(field: str):
    source = _valid_authorization_report()
    source.pop(field)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_extra_source_field_fails_closed_without_leakage():
    source = _valid_authorization_report()
    source["raw_provider_payload"] = "must-not-leak"

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)
    assert "must-not-leak" not in json.dumps(report)


@pytest.mark.parametrize("value", (None, [], "10FZ", 7, True, object()))
def test_missing_or_non_dict_source_fails_closed(value: object):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        value
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

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _HostileDict(_valid_authorization_report())
    )

    _assert_sanitized_invalid_report(report)
    assert _HostileDict.get_called is False
    assert _HostileDict.iter_called is False


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_authorization_report()
    value = source.pop("artifact_class")
    source[type("StrSubclass", (str,), {})("artifact_class")] = value

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", SOURCE_STRING_FIELDS)
@pytest.mark.parametrize("kind", ("non_string", "subclass"))
def test_source_string_fields_require_exact_built_in_strings(
    field: str,
    kind: str,
):
    source = _valid_authorization_report()
    source[field] = (
        7
        if kind == "non_string"
        else type("StrSubclass", (str,), {})(source[field])
    )
    if field != "authorization_report_decision_id":
        _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("value", (True, 1.0, -1, 0, 2))
def test_approval_revision_type_or_value_drift_fails_closed(value: object):
    source = _valid_authorization_report()
    source["approval_revision"] = value
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_integer_subclass_approval_revision_fails_closed():
    source = _valid_authorization_report()
    source["approval_revision"] = type("IntSubclass", (int,), {})(1)
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("value", (False, 1, 0))
def test_valid_source_ok_must_be_exactly_true(value: object):
    source = _valid_authorization_report()
    source["ok"] = value
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
@pytest.mark.parametrize("value", (True, 0))
def test_source_gate_flags_must_be_exactly_false(field: str, value: object):
    source = _valid_authorization_report()
    source[field] = value
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authorization_report_schema_version", "10FZ.2"),
        ("authorization_report_type", "future_report"),
        ("authorization_report_scope", "future_scope"),
        ("source_provenance_schema_version", "10FT.2"),
        ("approval_schema_version", "10FZ.APPROVAL.2"),
        ("approval_status", "approved"),
        ("approved_action", "invoke_model"),
        ("authorization_report_status", "future_status"),
        ("claim_boundary", "expanded_boundary"),
    ),
)
def test_wrong_source_identity_status_or_action_fails_closed(
    field: str,
    value: str,
):
    source = _valid_authorization_report()
    source[field] = value
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_authorized_status_requires_operator_approved():
    source = _valid_authorization_report()
    source["approval_status"] = "operator_denied"
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "prefix", "other_prefix"),
    (
        ("authorization_report_decision_id", "10FZ-", "10GF-"),
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
    source = _valid_authorization_report()
    source[field] = (other_prefix + "a" * 32) if not suffix else prefix + suffix
    if field != "authorization_report_decision_id":
        _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_source_external_ids_are_syntax_only_not_recomputed():
    source = _valid_authorization_report()
    source["source_provenance_decision_id"] = "10FT-" + "0" * 32
    source["source_policy_decision_id"] = "10FT-POLICY-" + "1" * 32
    source["approval_decision_id"] = "10FZ-APPROVAL-" + "2" * 32
    source["authorized_lane"] = "lane:external-beta"
    source["authority_id"] = "authority:external-operator-42"
    source["approval_authority_id"] = "approval-authority:external-7"
    source["provider_id"] = "provider:external"
    source["provider_name"] = "external"
    source["pinned_model_id"] = "model:external-1"
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert report["ok"] is True
    assert report["source_provenance_decision_id"] == "10FT-" + "0" * 32
    assert report["source_policy_decision_id"] == "10FT-POLICY-" + "1" * 32
    assert report["approval_decision_id"] == "10FZ-APPROVAL-" + "2" * 32
    assert report["authorized_lane"] == "lane:external-beta"
    assert report["provider_id"] == "provider:external"
    assert report["pinned_model_id"] == "model:external-1"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authorized_lane", "authority:wrong-prefix"),
        ("authority_id", "lane:wrong-prefix"),
        ("provider_id", "model:wrong-prefix"),
        ("pinned_model_id", "provider:wrong-prefix"),
        ("approval_authority_id", "authority:wrong-prefix"),
        ("authorized_lane", "lane:"),
        ("authority_id", "authority:"),
        ("provider_id", "provider:"),
        ("pinned_model_id", "model:"),
        ("approval_authority_id", "approval-authority:"),
    ),
)
def test_source_identity_fields_require_safe_prefixes(field: str, value: str):
    source = _valid_authorization_report()
    source[field] = value
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_provider_id_and_name_must_be_internally_consistent():
    source = _valid_authorization_report()
    source["provider_id"] = "provider:other"
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    "boundaries",
    (
        list(reversed(FORBIDDEN_BOUNDARIES)),
        FORBIDDEN_BOUNDARIES[:-1],
        [*FORBIDDEN_BOUNDARIES, "ledger_read"],
        [*FORBIDDEN_BOUNDARIES, FORBIDDEN_BOUNDARIES[-1]],
        [*FORBIDDEN_BOUNDARIES[:-1], "future_boundary"],
    ),
)
def test_forbidden_boundaries_must_be_exact_and_deterministic(
    boundaries: list[str],
):
    source = _valid_authorization_report()
    source["forbidden_boundaries"] = boundaries
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)


def test_list_subclasses_and_string_subclass_items_fail_closed():
    list_subclass = type("ListSubclass", (list,), {})
    str_subclass = type("StrSubclass", (str,), {})
    cases = []

    value = _valid_authorization_report()
    value["forbidden_boundaries"] = list_subclass(FORBIDDEN_BOUNDARIES)
    cases.append(value)

    value = _valid_authorization_report()
    value["errors"] = list_subclass([])
    cases.append(value)

    value = _valid_authorization_report()
    value["forbidden_boundaries"][0] = str_subclass(FORBIDDEN_BOUNDARIES[0])
    cases.append(value)

    for source in cases:
        _recompute_source(source)
        report = create_minimal_inert_model_routing_authorization_report_status_report(
            source
        )
        _assert_sanitized_invalid_report(report)


def test_raw_source_errors_fail_closed_without_leakage():
    source = _valid_authorization_report()
    source["errors"] = ["raw 10FZ source failure"]
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)
    assert "raw 10FZ source failure" not in json.dumps(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("artifact_class", "../../raw_config"),
        ("artifact_family", "equality-signal-value"),
        ("authorized_lane", "lane:sk-proj-example"),
        ("authority_basis", "C:\\private\\authority"),
        ("provider_name", "access_token"),
        ("provider_name", "auth_token_deadbeef"),
        ("pinned_model_revision", "api_key"),
        ("approval_authority_basis", "github_pat_abcdef"),
        ("approval_authority_basis", "secret"),
        ("approval_authority_id", "approval-authority:[REDACTED]"),
    ),
)
def test_tainted_or_sensitive_source_text_fails_closed_without_leakage(
    field: str,
    value: str,
):
    source = _valid_authorization_report()
    source[field] = value
    if field == "provider_name":
        source["provider_id"] = f"provider:{value}"
    _recompute_source(source)

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    _assert_sanitized_invalid_report(report)
    assert value not in json.dumps(report)


def test_caller_owned_lists_are_detached_and_source_is_not_mutated():
    source = _valid_authorization_report()
    before = json.loads(json.dumps(source))

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert source == before
    source["forbidden_boundaries"].clear()
    source["errors"].append("late raw source error")
    assert report["errors"] == []
    assert "late raw source error" not in json.dumps(report)


def test_real_10fz_producer_output_interoperates_without_10fz_import_in_production():
    source = _valid_10fz_producer_report()

    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )

    assert source["ok"] is True
    assert source["authorization_report_status"] == "authorized"
    assert report["ok"] is True
    assert report["authorization_status_report_status"] == "authorized_status"
    assert report["source_authorization_decision_id"] == source[
        "authorization_report_decision_id"
    ]


def test_output_contains_only_sanitized_status_metadata():
    source = _valid_authorization_report()
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )
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


def test_export_is_deterministic_for_all_status_report_statuses():
    reports = (
        create_minimal_inert_model_routing_authorization_report_status_report(
            _valid_authorization_report()
        ),
        create_minimal_inert_model_routing_authorization_report_status_report(
            _valid_authorization_report("not_authorized")
        ),
        create_minimal_inert_model_routing_authorization_report_status_report(None),
    )

    for report in reports:
        first = export_minimal_inert_model_routing_authorization_report_status_report(
            report
        )
        second = export_minimal_inert_model_routing_authorization_report_status_report(
            dict(report)
        )

        assert first == second
        assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
        assert json.loads(first) == report


def test_export_accepts_not_authorized_status_with_operator_approved():
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report(
            "not_authorized",
            approval_status="operator_approved",
        )
    )

    exported = export_minimal_inert_model_routing_authorization_report_status_report(
        report
    )

    assert json.loads(exported) == report


def test_export_rejects_authorized_status_with_operator_denied_after_rehash():
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report["approval_status"] = "operator_denied"
    _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize("field", sorted(OUTPUT_FIELDS))
def test_export_rejects_missing_output_field(field: str):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report.pop(field)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


def test_export_rejects_unexpected_or_forbidden_fields():
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report["raw_provider_payload"] = "must-not-export"

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        iter_called = False

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        create_minimal_inert_model_routing_authorization_report_status_report(
            _valid_authorization_report()
        )
    )

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)
    assert _TaintedReport.iter_called is False


def test_export_rejects_string_subclass_dictionary_key():
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    value = report.pop("artifact_class")
    report[type("StrSubclass", (str,), {})("artifact_class")] = value

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_authorization_schema_version", "10FZ.1"),
        ("source_authorization_decision_id", "10FZ-" + "a" * 32),
        ("source_authorization_status", "authorized"),
        ("source_authorization_ok", True),
        ("source_provenance_decision_id", "10FT-" + "b" * 32),
        ("source_policy_decision_id", "10FT-POLICY-" + "c" * 32),
        ("approval_decision_id", "10FZ-APPROVAL-" + "d" * 32),
        ("approval_status", "operator_approved"),
        ("artifact_class", "implementation_phase"),
        ("artifact_family", "governance_provenance"),
        ("authorized_lane", "lane:gpt-5-6-sol"),
        ("provider_id", "provider:openai"),
        ("provider_name", "openai"),
        ("pinned_model_id", "model:gpt-5-6-sol"),
        ("pinned_model_revision", "2026-07-14"),
    ),
)
def test_export_invalid_report_requires_each_source_field_neutral(
    field: str,
    value: object,
):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        None
    )
    report[field] = value
    _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("authorization_status_report_schema_version", "10GF.2"),
        ("authorization_status_report_type", "future_report"),
        ("authorization_status_report_scope", "future_scope"),
        ("authorization_status_report_decision_id", "10GF-tainted"),
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
        ("authorization_status_report_status", "future_status"),
        ("runtime_allowed", 0),
        ("claim_boundary", "expanded_boundary"),
        ("errors", ["raw source error"]),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report[field] = value
    if field != "authorization_status_report_decision_id":
        _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize("field", ("ok", "source_authorization_ok"))
def test_export_rejects_boolean_integer_drift(field: str):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report[field] = 1
    _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize("field", GATE_FLAGS)
def test_export_rejects_each_gate_flag_integer_drift(field: str):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report[field] = 0
    _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


@pytest.mark.parametrize("field", OUTPUT_STRING_FIELDS)
def test_export_rejects_string_subclass_fields(field: str):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    report[field] = type("StrSubclass", (str,), {})(report[field])
    if field != "authorization_status_report_decision_id":
        _recompute_status(report)

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


def test_export_rejects_list_subclass_and_string_subclass_error_items():
    base = create_minimal_inert_model_routing_authorization_report_status_report(
        _valid_authorization_report()
    )
    reports = []

    value = dict(base)
    value["errors"] = type("ListSubclass", (list,), {})([])
    reports.append(value)

    value = dict(base)
    value["errors"] = [type("StrSubclass", (str,), {})("tainted")]
    reports.append(value)

    for report in reports:
        _recompute_status(report)
        with pytest.raises(ValueError, match="exact 10GF status report shape"):
            export_minimal_inert_model_routing_authorization_report_status_report(
                report
            )


@pytest.mark.parametrize(
    "source",
    (
        _valid_authorization_report(),
        _valid_authorization_report("not_authorized"),
    ),
)
def test_export_rejects_tampered_own_decision_id_for_each_valid_status(
    source: dict,
):
    report = create_minimal_inert_model_routing_authorization_report_status_report(
        source
    )
    report["authorization_status_report_decision_id"] = "10GF-" + "f" * 32

    with pytest.raises(ValueError, match="exact 10GF status report shape"):
        export_minimal_inert_model_routing_authorization_report_status_report(report)


def test_gate_flags_are_false_on_authorized_not_authorized_and_invalid_reports():
    for report in (
        create_minimal_inert_model_routing_authorization_report_status_report(
            _valid_authorization_report()
        ),
        create_minimal_inert_model_routing_authorization_report_status_report(
            _valid_authorization_report("not_authorized")
        ),
        create_minimal_inert_model_routing_authorization_report_status_report(None),
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


def test_module_has_no_backend_prior_phase_or_writer_import_or_call():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden_names = (
        "append_inert_ledger_record",
        "verify_minimal_inert_ledger_readback",
        "create_minimal_inert_ledger_summary_report",
        "create_minimal_inert_ledger_status_bundle_report",
        "create_minimal_inert_ledger_status_digest_report",
        "verify_minimal_inert_ledger_status_digest_report",
        "create_minimal_inert_ledger_status_digest_verification_report",
        "verify_minimal_inert_ledger_status_digest_verification_report",
        "create_minimal_inert_ledger_status_digest_verification_verifier_status_report",
        "create_minimal_inert_model_routing_provenance_report",
        "export_minimal_inert_model_routing_provenance_report",
        "create_minimal_inert_model_routing_approval_authorization_report",
        "export_minimal_inert_model_routing_approval_authorization_report",
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
        if isinstance(node.slice, ast.Constant) and isinstance(
            node.slice.value,
            str,
        ):
            identifiers.add(node.slice.value)
        return identifiers
    return set()


def test_module_has_no_file_process_network_mutation_or_dynamic_lookup_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "__import__",
        "__getattribute__",
        "eval",
        "exec",
        "compile",
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
            assert node.id != "__builtins__"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_calls

    def _constant_text(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = _constant_text(node.left)
            right = _constant_text(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            key = _constant_text(node.slice)
            assert key not in forbidden_calls


def test_module_does_not_mutate_or_delete_public_input_parameters():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_parameters = {
        "create_minimal_inert_model_routing_authorization_report_status_report": {
            "authorization_report"
        },
        "export_minimal_inert_model_routing_authorization_report_status_report": {
            "status_report"
        },
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
        parameters = public_parameters[function.name]
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
                assert _root_name(target) not in parameters


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

    validator = functions["_validated_authorization_snapshot"]
    exporter = functions[
        "export_minimal_inert_model_routing_authorization_report_status_report"
    ]
    assert validator is not None
    assert exporter is not None
    assert validator.index("snapshot = dict(source)") < validator.index(
        "type(key) is not str for key in snapshot"
    )
    assert exporter.index("report = dict(status_report)") < exporter.index(
        "type(key) is not str for key in report"
    )

    validator_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_validated_authorization_snapshot"
    )
    exporter_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        == "export_minimal_inert_model_routing_authorization_report_status_report"
    )

    def _assignment_line(function: ast.FunctionDef, name: str) -> int:
        return next(
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
        )

    validator_snapshot_line = _assignment_line(validator_node, "snapshot")
    exporter_snapshot_line = _assignment_line(exporter_node, "report")
    def _key_validation_line(function: ast.FunctionDef) -> int:
        return next(
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.GeneratorExp)
            and any(
                isinstance(generator.target, ast.Name)
                and generator.target.id == "key"
                for generator in node.generators
            )
        )

    validator_key_line = _key_validation_line(validator_node)
    exporter_key_line = _key_validation_line(exporter_node)
    assert validator_snapshot_line < validator_key_line
    assert exporter_snapshot_line < exporter_key_line


def test_lists_are_detached_before_content_validation_and_export():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_authorization_snapshot"]
    exporter = functions[
        "export_minimal_inert_model_routing_authorization_report_status_report"
    ]
    assert validator is not None
    assert exporter is not None
    assert validator.index(
        "forbidden_boundaries = list(forbidden_boundaries)"
    ) < validator.index("forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)")
    assert validator.index(
        "source_errors = list(source_errors)"
    ) < validator.index("source_errors != []")
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "report_errors != expected_errors"
    )
