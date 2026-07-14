"""Phase 10FZ - inert model-routing approval authorization reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_model_routing_provenance_reporter import (
    create_minimal_inert_model_routing_provenance_report,
)
from backend.world.local_minimal_inert_model_routing_approval_authorization_reporter import (
    create_minimal_inert_model_routing_approval_authorization_report,
    export_minimal_inert_model_routing_approval_authorization_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_model_routing_approval_authorization_reporter.py"
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

PROVENANCE_FIELDS = {
    "ok",
    "provenance_report_schema_version",
    "provenance_report_type",
    "provenance_report_scope",
    "provenance_report_decision_id",
    "source_policy_schema_version",
    "source_policy_revision",
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
    "forbidden_boundaries",
    "provenance_report_status",
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

APPROVAL_FIELDS = {
    "approval_schema_version",
    "approval_revision",
    "approval_type",
    "approval_scope",
    "approval_decision_id",
    "approval_status",
    "approval_authority_id",
    "approval_authority_basis",
    "approver_lane",
    "approved_action",
    "approved_artifact_class",
    "approved_artifact_family",
    "approved_authorized_lane",
    "approved_authority_id",
    "approved_authority_basis",
    "approved_provider_id",
    "approved_provider_name",
    "approved_pinned_model_id",
    "approved_pinned_model_revision",
    "referenced_provenance_report_decision_id",
    "referenced_source_policy_decision_id",
    "forbidden_boundaries",
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "provider_call_allowed",
    "model_invocation_allowed",
    "config_mutation_allowed",
    "agent_launch_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
    "claim_boundary",
    "errors",
}

OUTPUT_FIELDS = {
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

PROVENANCE_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

APPROVAL_FALSE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "provider_call_allowed",
    "model_invocation_allowed",
    "config_mutation_allowed",
    "agent_launch_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

OUTPUT_GATE_FLAGS = PROVENANCE_GATE_FLAGS

PROVENANCE_STRING_FIELDS = (
    "provenance_report_schema_version",
    "provenance_report_type",
    "provenance_report_scope",
    "provenance_report_decision_id",
    "source_policy_schema_version",
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
    "provenance_report_status",
    "claim_boundary",
)

APPROVAL_STRING_FIELDS = (
    "approval_schema_version",
    "approval_type",
    "approval_scope",
    "approval_decision_id",
    "approval_status",
    "approval_authority_id",
    "approval_authority_basis",
    "approver_lane",
    "approved_action",
    "approved_artifact_class",
    "approved_artifact_family",
    "approved_authorized_lane",
    "approved_authority_id",
    "approved_authority_basis",
    "approved_provider_id",
    "approved_provider_name",
    "approved_pinned_model_id",
    "approved_pinned_model_revision",
    "referenced_provenance_report_decision_id",
    "referenced_source_policy_decision_id",
    "claim_boundary",
)

OUTPUT_STRING_FIELDS = (
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

PROVENANCE_CLAIM_BOUNDARY = (
    "report one model routing provenance policy only; no runtime execution, "
    "provider call, model invocation, filesystem scan, config mutation, "
    "agent launch, world-data access, ledger access, write, repair, or gate-7 "
    "activity"
)

APPROVAL_CLAIM_BOUNDARY = (
    "approve or deny one verified model routing provenance report for execution "
    "eligibility only; no runtime execution, provider call, model invocation, "
    "filesystem scan, config mutation, agent launch, world-data access, ledger "
    "access, write, repair, or gate-7 activity"
)

REPORT_CLAIM_BOUNDARY = (
    "report one model routing approval authorization decision only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

INVALID_SOURCE_ERROR = (
    "provenance_report or approval_authorization_artifact is not a valid 10FZ "
    "authorization source"
)

FORBIDDEN_OUTPUT_FIELDS = {
    "approver_lane",
    "approved_artifact_class",
    "approved_artifact_family",
    "approved_authorized_lane",
    "approved_authority_id",
    "approved_authority_basis",
    "approved_provider_id",
    "approved_provider_name",
    "approved_pinned_model_id",
    "approved_pinned_model_revision",
    "referenced_provenance_report_decision_id",
    "referenced_source_policy_decision_id",
    "provider_call_allowed",
    "model_invocation_allowed",
    "config_mutation_allowed",
    "agent_launch_allowed",
    "api_key",
    "access_token",
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


def _approval_decision_id(approval: dict) -> str:
    material = {
        key: approval[key]
        for key in sorted(APPROVAL_FIELDS - {"approval_decision_id"})
    }
    return "10FZ-APPROVAL-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _authorization_report_decision_id(report: dict) -> str:
    material = {
        key: report[key]
        for key in sorted(OUTPUT_FIELDS - {"authorization_report_decision_id"})
    }
    return "10FZ-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_provenance() -> dict:
    report = {
        "ok": True,
        "provenance_report_schema_version": "10FT.1",
        "provenance_report_type": "minimal_inert_model_routing_provenance_report",
        "provenance_report_scope": "model_routing_provenance_report_only",
        "provenance_report_decision_id": "10FT-" + "a" * 32,
        "source_policy_schema_version": "10FT.POLICY.1",
        "source_policy_revision": 1,
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
        "forbidden_boundaries": list(FORBIDDEN_BOUNDARIES),
        "provenance_report_status": "verified_provenance",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": PROVENANCE_CLAIM_BOUNDARY,
        "errors": [],
    }
    assert len(report) == 28
    assert set(report) == PROVENANCE_FIELDS
    return report


def _real_10ft_provenance() -> dict:
    source = {
        "policy_schema_version": "10FT.POLICY.1",
        "policy_revision": 1,
        "policy_type": "minimal_inert_model_routing_provenance_policy",
        "policy_scope": "model_routing_provenance_policy_only",
        "policy_decision_id": "",
        "artifact_class": "implementation_phase",
        "artifact_family": "governance_provenance",
        "authorized_lane": "lane:gpt-5-6-sol",
        "authority_id": "authority:operator-approved-10ft",
        "authority_basis": "phase_10fr_operator_authorization",
        "provider_id": "provider:openai",
        "provider_name": "openai",
        "pinned_model_id": "model:gpt-5-6-sol",
        "pinned_model_revision": "2026-07-14",
        "model_pinned": True,
        "provider_pinned": True,
        "route_locked": True,
        "allowed_action": "produce_artifact",
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
            "authorize one model routing provenance artifact only; no runtime "
            "execution, provider call, model invocation, filesystem scan, config "
            "mutation, agent launch, world-data access, ledger access, write, "
            "repair, or gate-7 activity"
        ),
        "errors": [],
    }
    material = {
        key: source[key]
        for key in sorted(set(source) - {"policy_decision_id"})
    }
    source["policy_decision_id"] = "10FT-POLICY-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]
    return create_minimal_inert_model_routing_provenance_report(source)


def _valid_approval(
    provenance: dict,
    *,
    status: str = "operator_approved",
) -> dict:
    approval = {
        "approval_schema_version": "10FZ.APPROVAL.1",
        "approval_revision": 1,
        "approval_type": "minimal_inert_model_routing_approval_authorization_artifact",
        "approval_scope": "model_routing_approval_authorization_only",
        "approval_decision_id": "",
        "approval_status": status,
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
        "claim_boundary": APPROVAL_CLAIM_BOUNDARY,
        "errors": [],
    }
    approval["approval_decision_id"] = _approval_decision_id(approval)
    assert len(approval) == 35
    assert set(approval) == APPROVAL_FIELDS
    return approval


def _recompute_approval(approval: dict) -> None:
    approval["approval_decision_id"] = _approval_decision_id(approval)


def _recompute_report(report: dict) -> None:
    report["authorization_report_decision_id"] = (
        _authorization_report_decision_id(report)
    )


def _assert_inert(report: dict) -> None:
    for field in OUTPUT_GATE_FLAGS:
        assert report[field] is False, field


def _assert_sanitized_invalid_report(report: dict) -> None:
    assert report == {
        "ok": False,
        "authorization_report_schema_version": "10FZ.1",
        "authorization_report_type": (
            "minimal_inert_model_routing_approval_authorization_report"
        ),
        "authorization_report_scope": (
            "model_routing_approval_authorization_report_only"
        ),
        "authorization_report_decision_id": report[
            "authorization_report_decision_id"
        ],
        "source_provenance_schema_version": "",
        "source_provenance_decision_id": "",
        "source_policy_decision_id": "",
        "artifact_class": "",
        "artifact_family": "",
        "authorized_lane": "",
        "authority_id": "",
        "authority_basis": "",
        "provider_id": "",
        "provider_name": "",
        "pinned_model_id": "",
        "pinned_model_revision": "",
        "approval_schema_version": "",
        "approval_revision": 0,
        "approval_decision_id": "",
        "approval_status": "",
        "approval_authority_id": "",
        "approval_authority_basis": "",
        "approved_action": "",
        "forbidden_boundaries": [],
        "authorization_report_status": "invalid_report",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": REPORT_CLAIM_BOUNDARY,
        "errors": [INVALID_SOURCE_ERROR],
    }
    assert set(report) == OUTPUT_FIELDS
    assert len(report) == 35
    assert report["authorization_report_decision_id"] == (
        _authorization_report_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_public_api_accepts_exactly_two_caller_supplied_artifacts():
    signature = inspect.signature(
        create_minimal_inert_model_routing_approval_authorization_report
    )

    assert tuple(signature.parameters) == (
        "provenance_report",
        "approval_authorization_artifact",
    )


def test_exporter_accepts_exactly_one_authorization_report():
    signature = inspect.signature(
        export_minimal_inert_model_routing_approval_authorization_report
    )

    assert tuple(signature.parameters) == ("authorization_report",)


def test_input_and_output_envelopes_have_exact_field_counts():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert len(PROVENANCE_FIELDS) == 28
    assert len(APPROVAL_FIELDS) == 35
    assert len(OUTPUT_FIELDS) == 35
    assert set(provenance) == PROVENANCE_FIELDS
    assert set(approval) == APPROVAL_FIELDS
    assert set(report) == OUTPUT_FIELDS


def test_matching_operator_approval_produces_exact_authorized_report():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert report == {
        "ok": True,
        "authorization_report_schema_version": "10FZ.1",
        "authorization_report_type": (
            "minimal_inert_model_routing_approval_authorization_report"
        ),
        "authorization_report_scope": (
            "model_routing_approval_authorization_report_only"
        ),
        "authorization_report_decision_id": report[
            "authorization_report_decision_id"
        ],
        "source_provenance_schema_version": "10FT.1",
        "source_provenance_decision_id": provenance[
            "provenance_report_decision_id"
        ],
        "source_policy_decision_id": provenance["source_policy_decision_id"],
        "artifact_class": provenance["artifact_class"],
        "artifact_family": provenance["artifact_family"],
        "authorized_lane": provenance["authorized_lane"],
        "authority_id": provenance["authority_id"],
        "authority_basis": provenance["authority_basis"],
        "provider_id": provenance["provider_id"],
        "provider_name": provenance["provider_name"],
        "pinned_model_id": provenance["pinned_model_id"],
        "pinned_model_revision": provenance["pinned_model_revision"],
        "approval_schema_version": "10FZ.APPROVAL.1",
        "approval_revision": 1,
        "approval_decision_id": approval["approval_decision_id"],
        "approval_status": "operator_approved",
        "approval_authority_id": approval["approval_authority_id"],
        "approval_authority_basis": approval["approval_authority_basis"],
        "approved_action": "authorize_routing_execution",
        "forbidden_boundaries": FORBIDDEN_BOUNDARIES,
        "authorization_report_status": "authorized",
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": REPORT_CLAIM_BOUNDARY,
        "errors": [],
    }
    assert report["authorization_report_decision_id"] == (
        _authorization_report_decision_id(report)
    )
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_valid_operator_denial_produces_not_authorized_report():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance, status="operator_denied")

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert report["ok"] is True
    assert report["authorization_report_status"] == "not_authorized"
    assert report["approval_status"] == "operator_denied"
    assert report["errors"] == []
    assert report["authorization_report_decision_id"] == (
        _authorization_report_decision_id(report)
    )
    _assert_inert(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("referenced_provenance_report_decision_id", "10FT-" + "c" * 32),
        ("referenced_source_policy_decision_id", "10FT-POLICY-" + "d" * 32),
        ("approved_artifact_class", "documentation_phase"),
        ("approved_artifact_family", "governance_approval"),
        ("approved_authorized_lane", "lane:external-beta"),
        ("approved_authority_id", "authority:external-operator"),
        ("approved_authority_basis", "external_operator_authorization"),
        ("approved_pinned_model_id", "model:gpt-5-6-luna"),
        ("approved_pinned_model_revision", "2026-07-15"),
    ),
)
def test_valid_mismatched_operator_approval_is_not_authorized(
    field: str,
    value: str,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval[field] = value
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert report["ok"] is True
    assert report["authorization_report_status"] == "not_authorized"
    assert report["approval_status"] == "operator_approved"
    assert report["errors"] == []


def test_valid_mismatched_provider_identity_is_not_authorized():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approved_provider_id"] = "provider:other"
    approval["approved_provider_name"] = "other"
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert report["ok"] is True
    assert report["authorization_report_status"] == "not_authorized"


def test_approval_decision_id_commits_to_all_other_approval_fields():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    original_id = approval["approval_decision_id"]

    approval["approval_authority_basis"] = "second_operator_authorization"
    _recompute_approval(approval)

    assert approval["approval_decision_id"] == _approval_decision_id(approval)
    assert approval["approval_decision_id"] != original_id
    assert create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )["ok"] is True


def test_tampered_approval_decision_id_fails_closed():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approval_decision_id"] = "10FZ-APPROVAL-" + "f" * 32

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", sorted(PROVENANCE_FIELDS))
def test_missing_provenance_field_fails_closed(field: str):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance.pop(field)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", sorted(APPROVAL_FIELDS))
def test_missing_approval_field_fails_closed(field: str):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval.pop(field)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("provenance_value", "approval_value"),
    (
        (None, None),
        ([], {}),
        ({}, []),
        ("10FT", {}),
        ({}, "10FZ"),
        (7, True),
        (object(), object()),
    ),
)
def test_missing_or_non_dict_inputs_fail_closed(
    provenance_value: object,
    approval_value: object,
):
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance_value,
        approval_value,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("target", ("provenance", "approval"))
def test_unexpected_provenance_or_approval_field_fails_without_leakage(
    target: str,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    if target == "provenance":
        provenance["api_key"] = "must-not-leak-provenance"
    else:
        approval["raw_config"] = "must-not-leak-approval"

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    serialized = json.dumps(report)

    _assert_sanitized_invalid_report(report)
    assert "must-not-leak" not in serialized


@pytest.mark.parametrize("target", ("provenance", "approval"))
def test_string_subclass_dictionary_keys_fail_closed(target: str):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    source = provenance if target == "provenance" else approval
    field = "artifact_class" if target == "provenance" else "approved_artifact_class"
    value = source.pop(field)
    source[type("StrSubclass", (str,), {})(field)] = value

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


def test_dict_subclasses_fail_closed_without_invoking_overrides():
    class _HostileDict(dict):
        iter_called = False
        get_called = False

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

        def get(self, key: object, default: object = None) -> object:
            type(self).get_called = True
            raise RuntimeError("caller-controlled get")

    provenance = _valid_provenance()
    approval = _valid_approval(provenance)

    reports = (
        create_minimal_inert_model_routing_approval_authorization_report(
            _HostileDict(provenance),
            approval,
        ),
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance,
            _HostileDict(approval),
        ),
    )

    for report in reports:
        _assert_sanitized_invalid_report(report)
    assert _HostileDict.iter_called is False
    assert _HostileDict.get_called is False


@pytest.mark.parametrize("field", PROVENANCE_STRING_FIELDS)
def test_non_string_or_string_subclass_provenance_fields_fail_closed(field: str):
    for value in (7, type("StrSubclass", (str,), {})(_valid_provenance()[field])):
        provenance = _valid_provenance()
        approval = _valid_approval(provenance)
        provenance[field] = value

        report = create_minimal_inert_model_routing_approval_authorization_report(
            provenance,
            approval,
        )

        _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", APPROVAL_STRING_FIELDS)
def test_non_string_or_string_subclass_approval_fields_fail_closed(field: str):
    provenance = _valid_provenance()
    original = _valid_approval(provenance)
    for value in (7, type("StrSubclass", (str,), {})(original[field])):
        approval = _valid_approval(provenance)
        approval[field] = value
        if field != "approval_decision_id":
            _recompute_approval(approval)

        report = create_minimal_inert_model_routing_approval_authorization_report(
            provenance,
            approval,
        )

        _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("value", (True, 1.0, -1, 2))
def test_provenance_revision_type_or_value_drift_fails_closed(value: object):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["source_policy_revision"] = value

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("value", (True, 1.0, -1, 2))
def test_approval_revision_type_or_value_drift_fails_closed(value: object):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approval_revision"] = value
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


def test_integer_subclasses_fail_closed():
    int_subclass = type("IntSubclass", (int,), {})(1)
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["source_policy_revision"] = int_subclass
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    _assert_sanitized_invalid_report(report)

    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approval_revision"] = int_subclass
    _recompute_approval(approval)
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", PROVENANCE_GATE_FLAGS)
@pytest.mark.parametrize("value", (True, 0))
def test_provenance_gate_flags_must_be_exactly_false(field: str, value: object):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance[field] = value

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", APPROVAL_FALSE_FLAGS)
@pytest.mark.parametrize("value", (True, 0))
def test_approval_gate_flags_must_be_exactly_false(field: str, value: object):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval[field] = value
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("ok", 1),
        ("provenance_report_schema_version", "10FT.2"),
        ("provenance_report_type", "future_report"),
        ("provenance_report_scope", "future_scope"),
        ("source_policy_schema_version", "10FT.POLICY.2"),
        ("provenance_report_status", "invalid_report"),
        ("claim_boundary", "expanded_boundary"),
    ),
)
def test_wrong_provenance_identity_or_status_fails_closed(
    field: str,
    value: object,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance[field] = value

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("approval_schema_version", "10FZ.APPROVAL.2"),
        ("approval_type", "future_artifact"),
        ("approval_scope", "future_scope"),
        ("approval_status", "approved"),
        ("approved_action", "invoke_model"),
        ("claim_boundary", "expanded_boundary"),
    ),
)
def test_wrong_approval_identity_scope_action_or_status_fails_closed(
    field: str,
    value: object,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval[field] = value
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10FT-",
        "10FT-" + "a" * 31,
        "10FT-" + "a" * 33,
        "10FT-" + "A" * 32,
        "10FT-" + "g" * 32,
    ),
)
def test_malformed_provenance_decision_id_fails_closed(decision_id: str):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["provenance_report_decision_id"] = decision_id

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10FZ-APPROVAL-",
        "10FZ-APPROVAL-" + "a" * 31,
        "10FZ-APPROVAL-" + "a" * 33,
        "10FZ-APPROVAL-" + "A" * 32,
        "10FZ-APPROVAL-" + "g" * 32,
        "10FT-" + "a" * 32,
    ),
)
def test_malformed_approval_decision_id_fails_closed(decision_id: str):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approval_decision_id"] = decision_id

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
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
def test_provenance_boundaries_must_be_exact(boundaries: list[str]):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["forbidden_boundaries"] = boundaries

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
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
def test_approval_boundaries_must_be_exact(boundaries: list[str]):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["forbidden_boundaries"] = boundaries
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


def test_list_subclasses_and_string_subclass_items_fail_closed():
    list_subclass = type("ListSubclass", (list,), {})
    str_subclass = type("StrSubclass", (str,), {})
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    cases = []

    value = _valid_provenance()
    value["forbidden_boundaries"] = list_subclass(FORBIDDEN_BOUNDARIES)
    cases.append((value, _valid_approval(value)))

    value = _valid_provenance()
    value["errors"] = list_subclass([])
    cases.append((value, _valid_approval(value)))

    value = _valid_provenance()
    value["forbidden_boundaries"][0] = str_subclass(FORBIDDEN_BOUNDARIES[0])
    cases.append((value, _valid_approval(value)))

    value = _valid_approval(provenance)
    value["forbidden_boundaries"] = list_subclass(FORBIDDEN_BOUNDARIES)
    _recompute_approval(value)
    cases.append((provenance, value))

    value = _valid_approval(provenance)
    value["errors"] = list_subclass([])
    _recompute_approval(value)
    cases.append((provenance, value))

    value = _valid_approval(provenance)
    value["forbidden_boundaries"][0] = str_subclass(FORBIDDEN_BOUNDARIES[0])
    _recompute_approval(value)
    cases.append((provenance, value))

    for provenance_value, approval_value in cases:
        report = create_minimal_inert_model_routing_approval_authorization_report(
            provenance_value,
            approval_value,
        )
        _assert_sanitized_invalid_report(report)


def test_raw_source_errors_fail_closed_without_leakage():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["errors"] = ["raw provenance failure"]
    approval["errors"] = ["raw approval failure"]
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    serialized = json.dumps(report)

    _assert_sanitized_invalid_report(report)
    assert "raw provenance failure" not in serialized
    assert "raw approval failure" not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authorized_lane", "authority:wrong-prefix"),
        ("authority_id", "lane:wrong-prefix"),
        ("provider_id", "model:wrong-prefix"),
        ("pinned_model_id", "provider:wrong-prefix"),
        ("authorized_lane", "lane:"),
        ("authority_id", "authority:"),
        ("provider_id", "provider:"),
        ("pinned_model_id", "model:"),
    ),
)
def test_provenance_identity_fields_require_safe_prefixes(
    field: str,
    value: str,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance[field] = value

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("approval_authority_id", "authority:wrong-prefix"),
        ("approver_lane", "approval-authority:wrong-prefix"),
        ("approved_authorized_lane", "authority:wrong-prefix"),
        ("approved_authority_id", "lane:wrong-prefix"),
        ("approved_provider_id", "model:wrong-prefix"),
        ("approved_pinned_model_id", "provider:wrong-prefix"),
        ("approval_authority_id", "approval-authority:"),
        ("approver_lane", "lane:"),
    ),
)
def test_approval_identity_fields_require_safe_prefixes(
    field: str,
    value: str,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval[field] = value
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)


def test_provider_id_and_name_must_be_internally_consistent():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance["provider_id"] = "provider:other"
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    _assert_sanitized_invalid_report(report)

    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    approval["approved_provider_id"] = "provider:other"
    _recompute_approval(approval)
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )
    _assert_sanitized_invalid_report(report)


def test_10ft_and_external_ids_are_syntax_only_not_recomputed():
    provenance = _valid_provenance()
    provenance["provenance_report_decision_id"] = "10FT-" + "c" * 32
    provenance["source_policy_decision_id"] = "10FT-POLICY-" + "d" * 32
    provenance["authorized_lane"] = "lane:external-beta"
    provenance["authority_id"] = "authority:external-operator-42"
    approval = _valid_approval(provenance)
    approval["approval_authority_id"] = "approval-authority:external-7"
    approval["approver_lane"] = "lane:external-governance"
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert report["ok"] is True
    assert report["authorization_report_status"] == "authorized"
    assert report["source_provenance_decision_id"] == "10FT-" + "c" * 32
    assert report["source_policy_decision_id"] == "10FT-POLICY-" + "d" * 32
    assert report["authorized_lane"] == "lane:external-beta"
    assert report["authority_id"] == "authority:external-operator-42"
    assert report["approval_authority_id"] == "approval-authority:external-7"


@pytest.mark.parametrize(
    ("source_name", "field", "value"),
    (
        ("provenance", "authority_basis", "C:\\private\\authority"),
        ("provenance", "artifact_class", "../../raw_config"),
        ("provenance", "provider_name", "access_token"),
        ("provenance", "pinned_model_id", "model:sk-proj-example"),
        ("provenance", "artifact_family", "equality-signal-value"),
        ("approval", "approval_authority_basis", "github_pat_abcdef"),
        ("approval", "approval_authority_basis", "auth_token_deadbeef"),
        ("approval", "approved_artifact_class", "raw-config"),
        ("approval", "approved_provider_name", "secret"),
        ("approval", "approved_pinned_model_revision", "api_key"),
        ("approval", "approver_lane", "lane:[REDACTED]"),
    ),
)
def test_tainted_or_sensitive_allowed_text_fails_closed(
    source_name: str,
    field: str,
    value: str,
):
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    source = provenance if source_name == "provenance" else approval
    source[field] = value
    if field == "provider_name":
        provenance["provider_id"] = f"provider:{value}"
    if field == "approved_provider_name":
        approval["approved_provider_id"] = f"provider:{value}"
    _recompute_approval(approval)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    _assert_sanitized_invalid_report(report)
    assert value not in json.dumps(report)


def test_caller_owned_lists_are_detached_and_inputs_are_not_mutated():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    provenance_before = json.loads(json.dumps(provenance))
    approval_before = json.loads(json.dumps(approval))

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert provenance == provenance_before
    assert approval == approval_before
    provenance["forbidden_boundaries"].clear()
    provenance["errors"].append("late provenance error")
    approval["forbidden_boundaries"].clear()
    approval["errors"].append("late approval error")

    assert report["forbidden_boundaries"] == FORBIDDEN_BOUNDARIES
    assert report["errors"] == []
    assert "late" not in json.dumps(report)


def test_real_10ft_producer_output_interoperates_without_10ft_recomputation():
    provenance = _real_10ft_provenance()
    approval = _valid_approval(provenance)

    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
    )

    assert provenance["ok"] is True
    assert provenance["provenance_report_status"] == "verified_provenance"
    assert report["ok"] is True
    assert report["authorization_report_status"] == "authorized"
    assert report["source_provenance_decision_id"] == provenance[
        "provenance_report_decision_id"
    ]


def test_output_contains_only_sanitized_authorization_metadata():
    provenance = _valid_provenance()
    approval = _valid_approval(provenance)
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        approval,
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


def test_export_is_deterministic_for_all_report_statuses():
    provenance = _valid_provenance()
    approved = _valid_approval(provenance)
    denied = _valid_approval(provenance, status="operator_denied")
    mismatched = _valid_approval(provenance)
    mismatched["approved_artifact_class"] = "documentation_phase"
    _recompute_approval(mismatched)
    reports = (
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, approved
        ),
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, denied
        ),
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, mismatched
        ),
        create_minimal_inert_model_routing_approval_authorization_report(None, None),
    )

    for report in reports:
        first = export_minimal_inert_model_routing_approval_authorization_report(
            report
        )
        second = export_minimal_inert_model_routing_approval_authorization_report(
            dict(report)
        )

        assert first == second
        assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
        assert json.loads(first) == report


@pytest.mark.parametrize("field", sorted(OUTPUT_FIELDS))
def test_export_rejects_missing_output_field(field: str):
    provenance = _valid_provenance()
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    report.pop(field)

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)


def test_export_rejects_unexpected_or_forbidden_fields():
    provenance = _valid_provenance()
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    report["raw_provider_payload"] = "must-not-export"

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        iter_called = False

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

    provenance = _valid_provenance()
    report = _TaintedReport(
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance,
            _valid_approval(provenance),
        )
    )

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)
    assert _TaintedReport.iter_called is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("authorization_report_schema_version", "10FZ.2"),
        ("authorization_report_type", "future_report"),
        ("authorization_report_scope", "future_scope"),
        ("authorization_report_decision_id", "10FZ-tainted"),
        ("source_provenance_schema_version", "10FT.2"),
        ("source_provenance_decision_id", "10FT-tainted"),
        ("source_policy_decision_id", "10FT-POLICY-tainted"),
        ("approval_schema_version", "10FZ.APPROVAL.2"),
        ("approval_revision", True),
        ("approval_decision_id", "10FZ-APPROVAL-tainted"),
        ("approval_status", "approved"),
        ("approval_authority_id", "authority:wrong-prefix"),
        ("approved_action", "invoke_model"),
        ("authorization_report_status", "future_status"),
        ("runtime_allowed", 0),
        ("claim_boundary", "expanded_boundary"),
        ("errors", ["raw source error"]),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    provenance = _valid_provenance()
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    report[field] = value
    if field != "authorization_report_decision_id":
        _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)


@pytest.mark.parametrize("field", OUTPUT_STRING_FIELDS)
def test_export_rejects_string_subclass_fields(field: str):
    provenance = _valid_provenance()
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    report[field] = type("StrSubclass", (str,), {})(report[field])
    if field != "authorization_report_decision_id":
        _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)


def test_export_rejects_list_subclasses_and_string_subclass_items():
    provenance = _valid_provenance()
    base = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    reports = []
    value = dict(base)
    value["forbidden_boundaries"] = type("ListSubclass", (list,), {})(
        FORBIDDEN_BOUNDARIES
    )
    reports.append(value)
    value = dict(base)
    value["forbidden_boundaries"] = list(FORBIDDEN_BOUNDARIES)
    value["forbidden_boundaries"][0] = type("StrSubclass", (str,), {})(
        FORBIDDEN_BOUNDARIES[0]
    )
    reports.append(value)
    value = dict(base)
    value["errors"] = type("ListSubclass", (list,), {})([])
    reports.append(value)

    for report in reports:
        _recompute_report(report)
        with pytest.raises(
            ValueError,
            match="exact 10FZ authorization report shape",
        ):
            export_minimal_inert_model_routing_approval_authorization_report(report)


def test_export_rejects_tampered_own_decision_id_for_every_valid_status():
    provenance = _valid_provenance()
    approvals = (
        _valid_approval(provenance),
        _valid_approval(provenance, status="operator_denied"),
    )
    mismatched = _valid_approval(provenance)
    mismatched["approved_artifact_class"] = "documentation_phase"
    _recompute_approval(mismatched)
    approvals = (*approvals, mismatched)

    for approval in approvals:
        report = create_minimal_inert_model_routing_approval_authorization_report(
            provenance,
            approval,
        )
        report["authorization_report_decision_id"] = "10FZ-" + "f" * 32
        with pytest.raises(
            ValueError,
            match="exact 10FZ authorization report shape",
        ):
            export_minimal_inert_model_routing_approval_authorization_report(report)


def test_export_rejects_non_exact_boundaries_after_rehash():
    provenance = _valid_provenance()
    report = create_minimal_inert_model_routing_approval_authorization_report(
        provenance,
        _valid_approval(provenance),
    )
    report["forbidden_boundaries"] = list(reversed(FORBIDDEN_BOUNDARIES))
    _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FZ authorization report shape"):
        export_minimal_inert_model_routing_approval_authorization_report(report)


def test_gate_flags_are_false_on_success_denial_mismatch_and_failure():
    provenance = _valid_provenance()
    matching = _valid_approval(provenance)
    denied = _valid_approval(provenance, status="operator_denied")
    mismatched = _valid_approval(provenance)
    mismatched["approved_artifact_class"] = "documentation_phase"
    _recompute_approval(mismatched)

    for report in (
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, matching
        ),
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, denied
        ),
        create_minimal_inert_model_routing_approval_authorization_report(
            provenance, mismatched
        ),
        create_minimal_inert_model_routing_approval_authorization_report(None, None),
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


def test_snapshot_precedes_key_validation_for_both_inputs_and_exporter():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    provenance_validator = functions["_validated_provenance_snapshot"]
    approval_validator = functions["_validated_approval_snapshot"]
    exporter = functions[
        "export_minimal_inert_model_routing_approval_authorization_report"
    ]
    assert provenance_validator is not None
    assert approval_validator is not None
    assert exporter is not None
    assert provenance_validator.index(
        "snapshot = dict(source)"
    ) < provenance_validator.index("type(key) is not str for key in snapshot")
    assert approval_validator.index(
        "snapshot = dict(source)"
    ) < approval_validator.index("type(key) is not str for key in snapshot")
    assert exporter.index("report = dict(authorization_report)") < exporter.index(
        "type(key) is not str for key in report"
    )


def test_lists_are_detached_before_content_validation_for_both_inputs_and_exporter():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    for name in ("_validated_provenance_snapshot", "_validated_approval_snapshot"):
        validator = functions[name]
        assert validator is not None
        assert validator.index(
            "forbidden_boundaries = list(forbidden_boundaries)"
        ) < validator.index("forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)")
        assert validator.index(
            "forbidden_boundaries = list(forbidden_boundaries)"
        ) < validator.index("for field in")
        assert validator.index("source_errors = list(source_errors)") < validator.index(
            "source_errors != []"
        )
        assert validator.index("source_errors = list(source_errors)") < validator.index(
            "for field in"
        )

    exporter = functions[
        "export_minimal_inert_model_routing_approval_authorization_report"
    ]
    assert exporter is not None
    assert exporter.index(
        "forbidden_boundaries = list(forbidden_boundaries)"
    ) < exporter.index("forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)")
    assert exporter.index(
        "forbidden_boundaries = list(forbidden_boundaries)"
    ) < exporter.index("for field in _OUTPUT_STRING_FIELDS")
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "report_errors != expected_errors"
    )
    assert exporter.index("report_errors = list(report_errors)") < exporter.index(
        "for field in _OUTPUT_STRING_FIELDS"
    )
