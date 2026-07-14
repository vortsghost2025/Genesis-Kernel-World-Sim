"""Phase 10FT - minimal inert model-routing provenance reporter tests."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from backend.world.local_minimal_inert_model_routing_provenance_reporter import (
    create_minimal_inert_model_routing_provenance_report,
    export_minimal_inert_model_routing_provenance_report,
)


MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_minimal_inert_model_routing_provenance_reporter.py"
)

SOURCE_FIELDS = {
    "policy_schema_version",
    "policy_revision",
    "policy_type",
    "policy_scope",
    "policy_decision_id",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "model_pinned",
    "provider_pinned",
    "route_locked",
    "allowed_action",
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

SOURCE_FALSE_FLAGS = (
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

OUTPUT_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

TRUE_LOCK_FLAGS = (
    "model_pinned",
    "provider_pinned",
    "route_locked",
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

SOURCE_CLAIM_BOUNDARY = (
    "authorize one model routing provenance artifact only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

REPORT_CLAIM_BOUNDARY = (
    "report one model routing provenance policy only; no runtime execution, "
    "provider call, model invocation, filesystem scan, config mutation, "
    "agent launch, world-data access, ledger access, write, repair, or gate-7 "
    "activity"
)

INVALID_SOURCE_ERROR = (
    "routing_provenance_artifact is not a valid 10FT routing provenance policy"
)

SOURCE_STRING_FIELDS = (
    "policy_schema_version",
    "policy_type",
    "policy_scope",
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "allowed_action",
    "claim_boundary",
)

OUTPUT_STRING_FIELDS = (
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

FORBIDDEN_OUTPUT_FIELDS = SOURCE_FIELDS - {
    "policy_schema_version",
    "policy_revision",
    "policy_decision_id",
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
    *OUTPUT_GATE_FLAGS,
    "claim_boundary",
    "errors",
}
FORBIDDEN_OUTPUT_FIELDS.update(
    {
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
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _policy_decision_id(source: dict) -> str:
    material = {
        key: source[key]
        for key in sorted(SOURCE_FIELDS - {"policy_decision_id"})
    }
    return "10FT-POLICY-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _provenance_report_decision_id(report: dict) -> str:
    material = {
        key: report[key]
        for key in sorted(OUTPUT_FIELDS - {"provenance_report_decision_id"})
    }
    return "10FT-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]


def _valid_source() -> dict:
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
        "claim_boundary": SOURCE_CLAIM_BOUNDARY,
        "errors": [],
    }
    source["policy_decision_id"] = _policy_decision_id(source)
    assert set(source) == SOURCE_FIELDS
    assert len(source) == 32
    return source


def _recompute_policy(source: dict) -> None:
    source["policy_decision_id"] = _policy_decision_id(source)


def _recompute_report(report: dict) -> None:
    report["provenance_report_decision_id"] = _provenance_report_decision_id(
        report
    )


def _assert_inert(report: dict) -> None:
    for field in OUTPUT_GATE_FLAGS:
        assert report[field] is False, field


def _assert_sanitized_invalid_report(report: dict) -> None:
    assert report == {
        "ok": False,
        "provenance_report_schema_version": "10FT.1",
        "provenance_report_type": "minimal_inert_model_routing_provenance_report",
        "provenance_report_scope": "model_routing_provenance_report_only",
        "provenance_report_decision_id": report[
            "provenance_report_decision_id"
        ],
        "source_policy_schema_version": "",
        "source_policy_revision": 0,
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
        "forbidden_boundaries": [],
        "provenance_report_status": "invalid_report",
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
    assert report[
        "provenance_report_decision_id"
    ] == _provenance_report_decision_id(report)
    assert set(report) == OUTPUT_FIELDS
    assert len(report) == 28
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_public_api_accepts_exactly_one_caller_supplied_artifact():
    signature = inspect.signature(create_minimal_inert_model_routing_provenance_report)

    assert tuple(signature.parameters) == ("routing_provenance_artifact",)


def test_exporter_accepts_exactly_one_provenance_report():
    signature = inspect.signature(export_minimal_inert_model_routing_provenance_report)

    assert tuple(signature.parameters) == ("provenance_report",)


def test_source_envelope_has_exactly_32_fields():
    assert len(SOURCE_FIELDS) == 32
    assert set(_valid_source()) == SOURCE_FIELDS


def test_valid_source_produces_exact_verified_provenance_report():
    source = _valid_source()

    report = create_minimal_inert_model_routing_provenance_report(source)

    assert report == {
        "ok": True,
        "provenance_report_schema_version": "10FT.1",
        "provenance_report_type": "minimal_inert_model_routing_provenance_report",
        "provenance_report_scope": "model_routing_provenance_report_only",
        "provenance_report_decision_id": report[
            "provenance_report_decision_id"
        ],
        "source_policy_schema_version": "10FT.POLICY.1",
        "source_policy_revision": 1,
        "source_policy_decision_id": source["policy_decision_id"],
        "artifact_class": "implementation_phase",
        "artifact_family": "governance_provenance",
        "authorized_lane": "lane:gpt-5-6-sol",
        "authority_id": "authority:operator-approved-10ft",
        "authority_basis": "phase_10fr_operator_authorization",
        "provider_id": "provider:openai",
        "provider_name": "openai",
        "pinned_model_id": "model:gpt-5-6-sol",
        "pinned_model_revision": "2026-07-14",
        "forbidden_boundaries": FORBIDDEN_BOUNDARIES,
        "provenance_report_status": "verified_provenance",
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
    assert report[
        "provenance_report_decision_id"
    ] == _provenance_report_decision_id(report)
    assert set(report) == OUTPUT_FIELDS
    assert len(report) == 28
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    _assert_inert(report)


def test_output_envelope_has_exactly_28_fields():
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())

    assert len(OUTPUT_FIELDS) == 28
    assert set(report) == OUTPUT_FIELDS
    assert len(report) == 28


@pytest.mark.parametrize("value", (None, [], "10FT", 7, True, object()))
def test_missing_or_non_dict_source_fails_closed(value: object):
    report = create_minimal_inert_model_routing_provenance_report(value)

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

    report = create_minimal_inert_model_routing_provenance_report(
        _HostileDict(_valid_source())
    )

    _assert_sanitized_invalid_report(report)
    assert _HostileDict.get_called is False
    assert _HostileDict.iter_called is False


def test_policy_decision_id_is_recomputed_from_all_safe_source_material():
    source = _valid_source()

    assert source["policy_decision_id"] == _policy_decision_id(source)
    original_id = source["policy_decision_id"]
    source["artifact_class"] = "documentation_phase"
    _recompute_policy(source)

    assert source["policy_decision_id"] != original_id
    assert create_minimal_inert_model_routing_provenance_report(source)["ok"] is True


def test_tampered_policy_decision_id_fails_closed():
    source = _valid_source()
    source["policy_decision_id"] = "10FT-POLICY-" + "f" * 32

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", sorted(SOURCE_FIELDS))
def test_missing_required_source_field_fails_closed(field: str):
    source = _valid_source()
    source.pop(field)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_unexpected_source_field_fails_closed_without_leakage():
    source = _valid_source()
    source["api_key"] = "must-not-leak"

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)
    assert "must-not-leak" not in json.dumps(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("policy_schema_version", "10FT.POLICY.2"),
        ("policy_revision", 2),
        ("policy_type", "future_policy"),
        ("policy_scope", "future_scope"),
        ("allowed_action", "invoke_model"),
        ("claim_boundary", "expanded_boundary"),
    ),
)
def test_wrong_source_identity_or_scope_fails_closed(field: str, value: object):
    source = _valid_source()
    source[field] = value
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", SOURCE_STRING_FIELDS)
def test_non_string_source_fields_fail_closed(field: str):
    source = _valid_source()
    source[field] = 7
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    "decision_id",
    (
        "",
        "10FT-POLICY-",
        "10FT-POLICY-" + "a" * 31,
        "10FT-POLICY-" + "a" * 33,
        "10FT-POLICY-" + "A" * 32,
        "10FT-POLICY-" + "g" * 32,
        "10FT-" + "a" * 32,
    ),
)
def test_malformed_policy_decision_id_fails_closed(decision_id: str):
    source = _valid_source()
    source["policy_decision_id"] = decision_id

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("value", (True, 1.0, -1))
def test_policy_revision_bool_float_or_out_of_range_fails_closed(value: object):
    source = _valid_source()
    source["policy_revision"] = value
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_integer_subclass_policy_revision_fails_closed():
    source = _valid_source()
    source["policy_revision"] = type("IntSubclass", (int,), {})(1)
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", TRUE_LOCK_FLAGS)
@pytest.mark.parametrize("value", (False, 1))
def test_pinning_and_route_lock_flags_must_be_exactly_true(
    field: str,
    value: object,
):
    source = _valid_source()
    source[field] = value
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", SOURCE_FALSE_FLAGS)
@pytest.mark.parametrize("value", (True, 0))
def test_all_execution_provider_model_config_agent_world_gate_flags_are_false(
    field: str,
    value: object,
):
    source = _valid_source()
    source[field] = value
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

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
    source = _valid_source()
    source["forbidden_boundaries"] = boundaries
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_forbidden_boundary_list_subclass_fails_closed():
    source = _valid_source()
    source["forbidden_boundaries"] = type("ListSubclass", (list,), {})(
        FORBIDDEN_BOUNDARIES
    )
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_forbidden_boundary_string_subclass_fails_closed():
    source = _valid_source()
    source["forbidden_boundaries"] = list(FORBIDDEN_BOUNDARIES)
    source["forbidden_boundaries"][0] = type("StrSubclass", (str,), {})(
        FORBIDDEN_BOUNDARIES[0]
    )
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_errors_list_subclass_fails_closed():
    source = _valid_source()
    source["errors"] = type("ListSubclass", (list,), {})([])
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize("field", SOURCE_STRING_FIELDS)
def test_string_subclass_source_field_fails_closed(field: str):
    source = _valid_source()
    source[field] = type("StrSubclass", (str,), {})(source[field])
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_string_subclass_dictionary_key_fails_closed():
    source = _valid_source()
    value = source.pop("artifact_class")
    source[type("StrSubclass", (str,), {})("artifact_class")] = value

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


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
def test_external_identity_fields_require_exact_safe_syntax(
    field: str,
    value: str,
):
    source = _valid_source()
    source[field] = value
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


def test_external_lane_and_authority_ids_are_syntax_only_not_recomputed():
    source = _valid_source()
    source["authorized_lane"] = "lane:external-beta"
    source["authority_id"] = "authority:external-operator-42"
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    assert report["ok"] is True
    assert report["authorized_lane"] == "lane:external-beta"
    assert report["authority_id"] == "authority:external-operator-42"


def test_provider_id_and_name_must_identify_the_same_pinned_provider():
    source = _valid_source()
    source["provider_id"] = "provider:other"
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("authority_basis", "C:\\private\\authority"),
        ("artifact_class", "../../raw_config"),
        ("artifact_class", "raw-config"),
        ("provider_name", "access_token"),
        ("provider_name", "access-token"),
        ("provider_name", "refresh_token"),
        ("provider_name", "ghp_abcdef123456"),
        ("provider_name", "github_pat_abcdef123456"),
        ("provider_name", "sk_live_abcdef123456"),
        ("provider_name", "xoxa-abcdef123456"),
        ("authority_basis", "AKIAABCDEFG123456"),
        ("authority_basis", "whsec_abcdef123456"),
        ("pinned_model_id", "model:secret"),
        ("pinned_model_id", "model:sk-proj-example"),
        ("pinned_model_revision", "api_key"),
        ("pinned_model_revision", "eyJheader.payload.signature"),
        ("artifact_family", "."),
        ("artifact_family", "equality-signal-value"),
        ("artifact_family", "line\nbreak"),
        ("authorized_lane", "lane:[REDACTED]"),
    ),
)
def test_tainted_or_sensitive_allowed_source_text_fails_closed(
    field: str,
    value: str,
):
    source = _valid_source()
    source[field] = value
    if field == "provider_name":
        source["provider_id"] = f"provider:{value}"
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)

    _assert_sanitized_invalid_report(report)
    assert report[field] == ""


def test_raw_source_errors_fail_closed_without_leakage():
    source = _valid_source()
    source["errors"] = ["raw routing policy failure detail"]
    _recompute_policy(source)

    report = create_minimal_inert_model_routing_provenance_report(source)
    serialized = json.dumps(report)

    _assert_sanitized_invalid_report(report)
    assert "raw routing policy failure detail" not in serialized


def test_caller_owned_lists_are_detached_and_source_is_not_mutated():
    source = _valid_source()
    before = json.loads(json.dumps(source))

    report = create_minimal_inert_model_routing_provenance_report(source)

    assert source == before
    source["forbidden_boundaries"].clear()
    source["errors"].append("late raw source error")

    assert report["forbidden_boundaries"] == FORBIDDEN_BOUNDARIES
    assert report["errors"] == []
    assert "late raw source error" not in json.dumps(report)
    assert before == _valid_source()


def test_output_contains_only_sanitized_governance_provenance_metadata():
    source = _valid_source()

    report = create_minimal_inert_model_routing_provenance_report(source)
    serialized = json.dumps(report)

    assert set(report) == OUTPUT_FIELDS
    assert FORBIDDEN_OUTPUT_FIELDS.isdisjoint(report)
    for field in (
        "policy_type",
        "policy_scope",
        "model_pinned",
        "provider_pinned",
        "route_locked",
        "allowed_action",
        "provider_call_allowed",
        "model_invocation_allowed",
        "config_mutation_allowed",
        "agent_launch_allowed",
    ):
        assert field not in report
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


def test_export_is_deterministic_sorted_json_for_valid_and_invalid_reports():
    reports = (
        create_minimal_inert_model_routing_provenance_report(_valid_source()),
        create_minimal_inert_model_routing_provenance_report(None),
    )

    for report in reports:
        first = export_minimal_inert_model_routing_provenance_report(report)
        second = export_minimal_inert_model_routing_provenance_report(dict(report))

        assert first == second
        assert first == json.dumps(report, sort_keys=True, ensure_ascii=False)
        assert json.loads(first) == report


@pytest.mark.parametrize("field", sorted(OUTPUT_FIELDS))
def test_export_rejects_missing_output_field(field: str):
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report.pop(field)

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


def test_export_rejects_unexpected_or_forbidden_fields():
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report["raw_provider_payload"] = "must-not-export"

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


def test_export_rejects_dict_subclass_without_invoking_overrides():
    class _TaintedReport(dict):
        items_called = False
        iter_called = False

        def items(self):
            type(self).items_called = True
            raise RuntimeError("caller-controlled items")

        def __iter__(self):
            type(self).iter_called = True
            raise RuntimeError("caller-controlled iteration")

    report = _TaintedReport(
        create_minimal_inert_model_routing_provenance_report(_valid_source())
    )

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)
    assert _TaintedReport.items_called is False
    assert _TaintedReport.iter_called is False


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("ok", False),
        ("provenance_report_schema_version", "10FT.2"),
        ("provenance_report_type", "future_reporter"),
        ("provenance_report_scope", "future_scope"),
        ("provenance_report_decision_id", "10FT-tainted"),
        ("source_policy_schema_version", "10FT.POLICY.2"),
        ("source_policy_revision", True),
        ("source_policy_decision_id", "10FT-POLICY-tainted"),
        ("authorized_lane", "lane:C:\\private"),
        ("authority_basis", "access_token"),
        ("provider_name", "secret"),
        ("pinned_model_revision", "api_key"),
        ("provenance_report_status", "invalid_report"),
        ("runtime_allowed", 0),
        ("claim_boundary", "expanded_boundary"),
        ("errors", ["raw source error"]),
    ),
)
def test_export_rejects_tainted_allowed_fields(field: str, value: object):
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report[field] = value
    if field != "provenance_report_decision_id":
        _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


@pytest.mark.parametrize("field", OUTPUT_STRING_FIELDS)
def test_export_rejects_string_subclass_fields(field: str):
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report[field] = type("StrSubclass", (str,), {})(report[field])
    if field != "provenance_report_decision_id":
        _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


def test_export_rejects_list_subclasses_and_string_subclass_items():
    base = create_minimal_inert_model_routing_provenance_report(_valid_source())
    reports = []
    list_subclass = dict(base)
    list_subclass["forbidden_boundaries"] = type(
        "ListSubclass", (list,), {}
    )(FORBIDDEN_BOUNDARIES)
    reports.append(list_subclass)
    item_subclass = dict(base)
    item_subclass["forbidden_boundaries"] = list(FORBIDDEN_BOUNDARIES)
    item_subclass["forbidden_boundaries"][0] = type(
        "StrSubclass", (str,), {}
    )(FORBIDDEN_BOUNDARIES[0])
    reports.append(item_subclass)
    error_subclass = dict(base)
    error_subclass["errors"] = type("ListSubclass", (list,), {})([])
    reports.append(error_subclass)

    for report in reports:
        _recompute_report(report)
        with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
            export_minimal_inert_model_routing_provenance_report(report)


def test_export_rejects_tampered_own_report_decision_id():
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report["provenance_report_decision_id"] = "10FT-" + "f" * 32

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


def test_export_rejects_non_exact_forbidden_boundaries_after_rehash():
    report = create_minimal_inert_model_routing_provenance_report(_valid_source())
    report["forbidden_boundaries"] = list(reversed(FORBIDDEN_BOUNDARIES))
    _recompute_report(report)

    with pytest.raises(ValueError, match="exact 10FT provenance report shape"):
        export_minimal_inert_model_routing_provenance_report(report)


def test_gate_flags_are_false_on_success_and_failure():
    for report in (
        create_minimal_inert_model_routing_provenance_report(_valid_source()),
        create_minimal_inert_model_routing_provenance_report(None),
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


def test_module_has_no_backend_proof_chain_or_writer_import_or_call():
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
        "backend.",
    )

    for name in forbidden_names:
        assert name not in source


def test_module_has_no_file_process_network_or_mutation_calls():
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
                node.slice.value, str
            ):
                identifiers.add(node.slice.value)
            return identifiers
        return set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        assert forbidden_calls.isdisjoint(_call_identifiers(node.func))


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
        "subprocess",
        "requests",
        "httpx",
        "api_key",
        "access_token",
        "secret",
        "Kilo",
        "OpenCode",
        "Wave",
        "Hermes",
        "world-sim/data",
    ):
        assert marker not in source


def test_mandated_provider_model_schema_has_no_operational_fragments():
    source = MODULE_PATH.read_text(encoding="utf-8")
    suspicious_operational_fragments = (
        "provider_client",
        "provider_api",
        "call_provider",
        "invoke_model",
        "model_client",
        "model_api",
        "launch_agent",
        "agent_client",
        "config_path",
        "config_file",
    )

    assert "provider_id" in source
    assert "provider_name" in source
    assert "provider_pinned" in source
    assert "model_invocation" in source
    for fragment in suspicious_operational_fragments:
        assert fragment not in source


def test_caller_owned_lists_are_detached_before_content_validation_and_export():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_policy_snapshot"]
    assert validator is not None
    assert validator.index(
        "forbidden_boundaries = list(forbidden_boundaries)"
    ) < validator.index("forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)")
    assert validator.index(
        "forbidden_boundaries = list(forbidden_boundaries)"
    ) < validator.index("for field in _SOURCE_STRING_FIELDS")
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "source_errors != []"
    )
    assert validator.index("source_errors = list(source_errors)") < validator.index(
        "for field in _SOURCE_STRING_FIELDS"
    )

    exporter = functions["export_minimal_inert_model_routing_provenance_report"]
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


def test_plain_dictionary_snapshot_precedes_key_type_validation():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }

    validator = functions["_validated_policy_snapshot"]
    assert validator is not None
    assert validator.index("snapshot = dict(source)") < validator.index(
        "type(key) is not str for key in snapshot"
    )

    exporter = functions["export_minimal_inert_model_routing_provenance_report"]
    assert exporter is not None
    assert exporter.index("report = dict(provenance_report)") < exporter.index(
        "type(key) is not str for key in report"
    )
