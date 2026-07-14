"""Phase 10FZ - inert model-routing approval authorization reporting.

Consumes caller-supplied provenance and approval dictionaries and returns a
sanitized authorization artifact. No source service, file, process, or world
state is used.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10FZ.1"
_REPORT_TYPE = "minimal_inert_model_routing_approval_authorization_report"
_REPORT_SCOPE = "model_routing_approval_authorization_report_only"

_PROVENANCE_SCHEMA_VERSION = "10FT.1"
_PROVENANCE_TYPE = "minimal_inert_model_routing_provenance_report"
_PROVENANCE_SCOPE = "model_routing_provenance_report_only"
_SOURCE_POLICY_SCHEMA_VERSION = "10FT.POLICY.1"
_SOURCE_POLICY_REVISION = 1

_APPROVAL_SCHEMA_VERSION = "10FZ.APPROVAL.1"
_APPROVAL_REVISION = 1
_APPROVAL_TYPE = "minimal_inert_model_routing_approval_authorization_artifact"
_APPROVAL_SCOPE = "model_routing_approval_authorization_only"
_APPROVED_ACTION = "authorize_routing_execution"
_APPROVAL_STATUSES = frozenset({"operator_approved", "operator_denied"})

_FORBIDDEN_BOUNDARIES = (
    "agent_launch",
    "config_mutation",
    "filesystem_scan",
    "gate7_activity",
    "model_invocation",
    "provider_call",
    "runtime_execution",
    "world_sim_data_access",
)

_PROVENANCE_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_APPROVAL_FALSE_FLAGS = (
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

_OUTPUT_GATE_FLAGS = _PROVENANCE_GATE_FLAGS

_PROVENANCE_FIELDS = frozenset(
    {
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
)

_APPROVAL_FIELDS = frozenset(
    {
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
)

_OUTPUT_FIELDS = frozenset(
    {
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
)

_PROVENANCE_STRING_FIELDS = (
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

_PROVENANCE_SAFE_METADATA_FIELDS = (
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
)

_APPROVAL_STRING_FIELDS = (
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

_APPROVAL_SAFE_METADATA_FIELDS = (
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
)

_OUTPUT_STRING_FIELDS = (
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

_OUTPUT_SAFE_METADATA_FIELDS = (
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "authority_id",
    "authority_basis",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
    "approval_authority_id",
    "approval_authority_basis",
    "approved_action",
)

_PROVENANCE_CLAIM_BOUNDARY = (
    "report one model routing provenance policy only; no runtime execution, "
    "provider call, model invocation, filesystem scan, config mutation, "
    "agent launch, world-data access, ledger access, write, repair, or gate-7 "
    "activity"
)

_APPROVAL_CLAIM_BOUNDARY = (
    "approve or deny one verified model routing provenance report for execution "
    "eligibility only; no runtime execution, provider call, model invocation, "
    "filesystem scan, config mutation, agent launch, world-data access, ledger "
    "access, write, repair, or gate-7 activity"
)

_REPORT_CLAIM_BOUNDARY = (
    "report one model routing approval authorization decision only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

_INVALID_SOURCE_ERROR = (
    "provenance_report or approval_authorization_artifact is not a valid 10FZ "
    "authorization source"
)

_SAFE_TEXT_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:"
)
_SENSITIVE_COMPACT_FRAGMENTS = (
    "api" + "key",
    "to" + "ken",
    "access" + "to" + "ken",
    "refresh" + "to" + "ken",
    "se" + "cret",
    "raw" + "config",
    "password",
    "credential",
    "equality" + "signal",
    "equality" + "value",
    "gh" + "p",
    "gh" + "o",
    "gh" + "u",
    "gh" + "s",
    "gh" + "r",
    "github" + "pat",
    "sk" + "live",
    "sk" + "test",
    "sk" + "proj",
    "rk" + "live",
    "rk" + "test",
    "ak" + "ia",
    "as" + "ia",
    "xo" + "xb",
    "xo" + "xp",
    "xo" + "xa",
    "wh" + "sec",
    "ai" + "za",
    "ey" + "j",
)

_APPROVAL_MATERIAL_FIELDS = tuple(
    sorted(_APPROVAL_FIELDS - {"approval_decision_id"})
)
_REPORT_MATERIAL_FIELDS = tuple(
    sorted(_OUTPUT_FIELDS - {"authorization_report_decision_id"})
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _hash_canonical(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_decision_id(value: object, prefix: str) -> bool:
    return (
        type(value) is str
        and value.startswith(prefix)
        and _is_lower_hex(value[len(prefix) :], 32)
    )


def _is_safe_text(value: object) -> bool:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 128
        or any(character not in _SAFE_TEXT_CHARACTERS for character in value)
        or not value[0].isalnum()
        or not value[-1].isalnum()
    ):
        return False
    lowered = value.lower()
    compacted = "".join(
        character for character in lowered if character.isalnum()
    )
    return not any(
        (
            ".." in lowered,
            "sk-" in lowered,
            "pk-" in lowered,
            any(
                fragment in compacted
                for fragment in _SENSITIVE_COMPACT_FRAGMENTS
            ),
        )
    )


def _is_prefixed_id(value: object, prefix: str) -> bool:
    return (
        _is_safe_text(value)
        and type(value) is str
        and value.startswith(prefix)
        and len(value) > len(prefix)
    )


def _approval_decision_material(source: dict[str, Any]) -> dict[str, Any]:
    return {field: source[field] for field in _APPROVAL_MATERIAL_FIELDS}


def _authorization_report_decision_material(
    report: dict[str, Any],
) -> dict[str, Any]:
    return {field: report[field] for field in _REPORT_MATERIAL_FIELDS}


def _validated_provenance_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict:
        return None
    snapshot = dict(source)
    if any(type(key) is not str for key in snapshot):
        return None
    if set(snapshot) != _PROVENANCE_FIELDS:
        return None

    forbidden_boundaries = snapshot["forbidden_boundaries"]
    if type(forbidden_boundaries) is not list:
        return None
    forbidden_boundaries = list(forbidden_boundaries)
    snapshot["forbidden_boundaries"] = forbidden_boundaries

    source_errors = snapshot["errors"]
    if type(source_errors) is not list:
        return None
    source_errors = list(source_errors)
    snapshot["errors"] = source_errors

    for field in _PROVENANCE_STRING_FIELDS:
        if type(snapshot[field]) is not str:
            return None
    if (
        snapshot["ok"] is not True
        or snapshot["provenance_report_schema_version"]
        != _PROVENANCE_SCHEMA_VERSION
        or snapshot["provenance_report_type"] != _PROVENANCE_TYPE
        or snapshot["provenance_report_scope"] != _PROVENANCE_SCOPE
        or snapshot["source_policy_schema_version"]
        != _SOURCE_POLICY_SCHEMA_VERSION
        or type(snapshot["source_policy_revision"]) is not int
        or snapshot["source_policy_revision"] != _SOURCE_POLICY_REVISION
        or snapshot["provenance_report_status"] != "verified_provenance"
        or snapshot["claim_boundary"] != _PROVENANCE_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["provenance_report_decision_id"],
            "10FT-",
        )
        or not _is_decision_id(
            snapshot["source_policy_decision_id"],
            "10FT-POLICY-",
        )
    ):
        return None

    if any(
        not _is_safe_text(snapshot[field])
        for field in _PROVENANCE_SAFE_METADATA_FIELDS
    ):
        return None
    if (
        not _is_prefixed_id(snapshot["authorized_lane"], "lane:")
        or not _is_prefixed_id(snapshot["authority_id"], "authority:")
        or not _is_prefixed_id(snapshot["provider_id"], "provider:")
        or not _is_prefixed_id(snapshot["pinned_model_id"], "model:")
        or snapshot["provider_id"]
        != "provider:" + snapshot["provider_name"]
    ):
        return None

    for field in _PROVENANCE_GATE_FLAGS:
        if snapshot[field] is not False:
            return None
    if (
        any(type(boundary) is not str for boundary in forbidden_boundaries)
        or forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)
    ):
        return None
    if any(type(error) is not str for error in source_errors) or source_errors != []:
        return None
    return snapshot


def _validated_approval_snapshot(source: object) -> dict[str, Any] | None:
    if type(source) is not dict:
        return None
    snapshot = dict(source)
    if any(type(key) is not str for key in snapshot):
        return None
    if set(snapshot) != _APPROVAL_FIELDS:
        return None

    forbidden_boundaries = snapshot["forbidden_boundaries"]
    if type(forbidden_boundaries) is not list:
        return None
    forbidden_boundaries = list(forbidden_boundaries)
    snapshot["forbidden_boundaries"] = forbidden_boundaries

    source_errors = snapshot["errors"]
    if type(source_errors) is not list:
        return None
    source_errors = list(source_errors)
    snapshot["errors"] = source_errors

    for field in _APPROVAL_STRING_FIELDS:
        if type(snapshot[field]) is not str:
            return None
    if (
        snapshot["approval_schema_version"] != _APPROVAL_SCHEMA_VERSION
        or type(snapshot["approval_revision"]) is not int
        or snapshot["approval_revision"] != _APPROVAL_REVISION
        or snapshot["approval_type"] != _APPROVAL_TYPE
        or snapshot["approval_scope"] != _APPROVAL_SCOPE
        or snapshot["approval_status"] not in _APPROVAL_STATUSES
        or snapshot["approved_action"] != _APPROVED_ACTION
        or snapshot["claim_boundary"] != _APPROVAL_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["approval_decision_id"],
            "10FZ-APPROVAL-",
        )
        or not _is_decision_id(
            snapshot["referenced_provenance_report_decision_id"],
            "10FT-",
        )
        or not _is_decision_id(
            snapshot["referenced_source_policy_decision_id"],
            "10FT-POLICY-",
        )
    ):
        return None

    if any(
        not _is_safe_text(snapshot[field])
        for field in _APPROVAL_SAFE_METADATA_FIELDS
    ):
        return None
    if (
        not _is_prefixed_id(
            snapshot["approval_authority_id"],
            "approval-authority:",
        )
        or not _is_prefixed_id(snapshot["approver_lane"], "lane:")
        or not _is_prefixed_id(snapshot["approved_authorized_lane"], "lane:")
        or not _is_prefixed_id(
            snapshot["approved_authority_id"],
            "authority:",
        )
        or not _is_prefixed_id(
            snapshot["approved_provider_id"],
            "provider:",
        )
        or not _is_prefixed_id(
            snapshot["approved_pinned_model_id"],
            "model:",
        )
        or snapshot["approved_provider_id"]
        != "provider:" + snapshot["approved_provider_name"]
    ):
        return None

    for field in _APPROVAL_FALSE_FLAGS:
        if snapshot[field] is not False:
            return None
    if (
        any(type(boundary) is not str for boundary in forbidden_boundaries)
        or forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)
    ):
        return None
    if any(type(error) is not str for error in source_errors) or source_errors != []:
        return None

    expected_decision_id = "10FZ-APPROVAL-" + _hash_canonical(
        _approval_decision_material(snapshot)
    )[:32]
    if snapshot["approval_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _approval_matches_provenance(
    provenance: dict[str, Any],
    approval: dict[str, Any],
) -> bool:
    if approval["approval_status"] != "operator_approved":
        return False
    pairs = (
        (
            "referenced_provenance_report_decision_id",
            "provenance_report_decision_id",
        ),
        ("referenced_source_policy_decision_id", "source_policy_decision_id"),
        ("approved_artifact_class", "artifact_class"),
        ("approved_artifact_family", "artifact_family"),
        ("approved_authorized_lane", "authorized_lane"),
        ("approved_authority_id", "authority_id"),
        ("approved_authority_basis", "authority_basis"),
        ("approved_provider_id", "provider_id"),
        ("approved_provider_name", "provider_name"),
        ("approved_pinned_model_id", "pinned_model_id"),
        ("approved_pinned_model_revision", "pinned_model_revision"),
    )
    return all(approval[left] == provenance[right] for left, right in pairs) and (
        approval["forbidden_boundaries"] == provenance["forbidden_boundaries"]
    )


def _authorization_report(
    *,
    source_provenance_schema_version: str = "",
    source_provenance_decision_id: str = "",
    source_policy_decision_id: str = "",
    artifact_class: str = "",
    artifact_family: str = "",
    authorized_lane: str = "",
    authority_id: str = "",
    authority_basis: str = "",
    provider_id: str = "",
    provider_name: str = "",
    pinned_model_id: str = "",
    pinned_model_revision: str = "",
    approval_schema_version: str = "",
    approval_revision: int = 0,
    approval_decision_id: str = "",
    approval_status: str = "",
    approval_authority_id: str = "",
    approval_authority_basis: str = "",
    approved_action: str = "",
    forbidden_boundaries: list[str] | None = None,
    authorization_report_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_boundaries = list(forbidden_boundaries or [])
    safe_errors = list(errors)
    result = {
        "ok": authorization_report_status in {"authorized", "not_authorized"},
        "authorization_report_schema_version": _SCHEMA_VERSION,
        "authorization_report_type": _REPORT_TYPE,
        "authorization_report_scope": _REPORT_SCOPE,
        "authorization_report_decision_id": "",
        "source_provenance_schema_version": source_provenance_schema_version,
        "source_provenance_decision_id": source_provenance_decision_id,
        "source_policy_decision_id": source_policy_decision_id,
        "artifact_class": artifact_class,
        "artifact_family": artifact_family,
        "authorized_lane": authorized_lane,
        "authority_id": authority_id,
        "authority_basis": authority_basis,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "pinned_model_id": pinned_model_id,
        "pinned_model_revision": pinned_model_revision,
        "approval_schema_version": approval_schema_version,
        "approval_revision": approval_revision,
        "approval_decision_id": approval_decision_id,
        "approval_status": approval_status,
        "approval_authority_id": approval_authority_id,
        "approval_authority_basis": approval_authority_basis,
        "approved_action": approved_action,
        "forbidden_boundaries": safe_boundaries,
        "authorization_report_status": authorization_report_status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _REPORT_CLAIM_BOUNDARY,
        "errors": safe_errors,
    }
    result["authorization_report_decision_id"] = "10FZ-" + _hash_canonical(
        _authorization_report_decision_material(result)
    )[:32]
    return result


def create_minimal_inert_model_routing_approval_authorization_report(
    provenance_report: dict | None,
    approval_authorization_artifact: dict | None,
) -> dict[str, Any]:
    """Report authorization without source-system or execution access."""

    try:
        provenance = _validated_provenance_snapshot(provenance_report)
        approval = _validated_approval_snapshot(approval_authorization_artifact)
    except Exception:
        provenance = None
        approval = None
    if provenance is None or approval is None:
        return _authorization_report(
            authorization_report_status="invalid_report",
            errors=[_INVALID_SOURCE_ERROR],
        )

    status = (
        "authorized"
        if _approval_matches_provenance(provenance, approval)
        else "not_authorized"
    )
    return _authorization_report(
        source_provenance_schema_version=provenance[
            "provenance_report_schema_version"
        ],
        source_provenance_decision_id=provenance[
            "provenance_report_decision_id"
        ],
        source_policy_decision_id=provenance["source_policy_decision_id"],
        artifact_class=provenance["artifact_class"],
        artifact_family=provenance["artifact_family"],
        authorized_lane=provenance["authorized_lane"],
        authority_id=provenance["authority_id"],
        authority_basis=provenance["authority_basis"],
        provider_id=provenance["provider_id"],
        provider_name=provenance["provider_name"],
        pinned_model_id=provenance["pinned_model_id"],
        pinned_model_revision=provenance["pinned_model_revision"],
        approval_schema_version=approval["approval_schema_version"],
        approval_revision=approval["approval_revision"],
        approval_decision_id=approval["approval_decision_id"],
        approval_status=approval["approval_status"],
        approval_authority_id=approval["approval_authority_id"],
        approval_authority_basis=approval["approval_authority_basis"],
        approved_action=approval["approved_action"],
        forbidden_boundaries=provenance["forbidden_boundaries"],
        authorization_report_status=status,
        errors=[],
    )


def export_minimal_inert_model_routing_approval_authorization_report(
    authorization_report: dict,
) -> str:
    """Export one validated 10FZ authorization report as deterministic JSON."""

    error = "authorization report must have the exact 10FZ authorization report shape"
    if type(authorization_report) is not dict:
        raise ValueError(error)
    report = dict(authorization_report)
    if any(type(key) is not str for key in report):
        raise ValueError(error)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError(error)

    forbidden_boundaries = report["forbidden_boundaries"]
    if type(forbidden_boundaries) is not list:
        raise ValueError(error)
    forbidden_boundaries = list(forbidden_boundaries)
    report["forbidden_boundaries"] = forbidden_boundaries

    report_errors = report["errors"]
    if type(report_errors) is not list:
        raise ValueError(error)
    report_errors = list(report_errors)
    report["errors"] = report_errors

    for field in _OUTPUT_STRING_FIELDS:
        if type(report[field]) is not str:
            raise ValueError(error)
    if (
        report["authorization_report_schema_version"] != _SCHEMA_VERSION
        or report["authorization_report_type"] != _REPORT_TYPE
        or report["authorization_report_scope"] != _REPORT_SCOPE
        or report["claim_boundary"] != _REPORT_CLAIM_BOUNDARY
        or not _is_decision_id(
            report["authorization_report_decision_id"],
            "10FZ-",
        )
        or type(report["approval_revision"]) is not int
        or type(report["ok"]) is not bool
    ):
        raise ValueError(error)
    for field in _OUTPUT_GATE_FLAGS:
        if report[field] is not False:
            raise ValueError(error)
    if any(type(boundary) is not str for boundary in forbidden_boundaries):
        raise ValueError(error)
    if any(type(item) is not str for item in report_errors):
        raise ValueError(error)

    status = report["authorization_report_status"]
    if status == "invalid_report":
        expected_errors = [_INVALID_SOURCE_ERROR]
        source_is_valid = not any(
            (
                report["source_provenance_schema_version"] != "",
                report["source_provenance_decision_id"] != "",
                report["source_policy_decision_id"] != "",
                report["artifact_class"] != "",
                report["artifact_family"] != "",
                report["authorized_lane"] != "",
                report["authority_id"] != "",
                report["authority_basis"] != "",
                report["provider_id"] != "",
                report["provider_name"] != "",
                report["pinned_model_id"] != "",
                report["pinned_model_revision"] != "",
                report["approval_schema_version"] != "",
                report["approval_revision"] != 0,
                report["approval_decision_id"] != "",
                report["approval_status"] != "",
                report["approval_authority_id"] != "",
                report["approval_authority_basis"] != "",
                report["approved_action"] != "",
                bool(forbidden_boundaries),
            )
        )
        expected_ok = False
    elif status in {"authorized", "not_authorized"}:
        expected_errors = []
        source_is_valid = not any(
            (
                report["source_provenance_schema_version"]
                != _PROVENANCE_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_provenance_decision_id"],
                    "10FT-",
                ),
                not _is_decision_id(
                    report["source_policy_decision_id"],
                    "10FT-POLICY-",
                ),
                report["approval_schema_version"] != _APPROVAL_SCHEMA_VERSION,
                report["approval_revision"] != _APPROVAL_REVISION,
                not _is_decision_id(
                    report["approval_decision_id"],
                    "10FZ-APPROVAL-",
                ),
                report["approval_status"] not in _APPROVAL_STATUSES,
                report["approved_action"] != _APPROVED_ACTION,
                any(
                    not _is_safe_text(report[field])
                    for field in _OUTPUT_SAFE_METADATA_FIELDS
                ),
                not _is_prefixed_id(report["authorized_lane"], "lane:"),
                not _is_prefixed_id(report["authority_id"], "authority:"),
                not _is_prefixed_id(report["provider_id"], "provider:"),
                not _is_prefixed_id(report["pinned_model_id"], "model:"),
                not _is_prefixed_id(
                    report["approval_authority_id"],
                    "approval-authority:",
                ),
                report["provider_id"] != "provider:" + report["provider_name"],
                forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES),
                status == "authorized"
                and report["approval_status"] != "operator_approved",
            )
        )
        expected_ok = True
    else:
        raise ValueError(error)

    if (
        not source_is_valid
        or report_errors != expected_errors
        or report["ok"] is not expected_ok
    ):
        raise ValueError(error)

    expected_decision_id = "10FZ-" + _hash_canonical(
        _authorization_report_decision_material(report)
    )[:32]
    if report["authorization_report_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
