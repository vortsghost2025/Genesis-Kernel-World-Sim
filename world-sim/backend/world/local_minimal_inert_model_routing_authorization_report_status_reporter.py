"""Phase 10GF - inert model-routing authorization status reporting.

Consumes one caller-supplied 10FZ dictionary and returns a sanitized status
artifact. No source service, file, process, or world state is used.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10GF.1"
_STATUS_REPORT_TYPE = (
    "minimal_inert_model_routing_authorization_report_status_report"
)
_STATUS_REPORT_SCOPE = "model_routing_authorization_report_status_only"

_SOURCE_SCHEMA_VERSION = "10FZ.1"
_SOURCE_TYPE = "minimal_inert_model_routing_approval_authorization_report"
_SOURCE_SCOPE = "model_routing_approval_authorization_report_only"
_SOURCE_PROVENANCE_SCHEMA_VERSION = "10FT.1"
_APPROVAL_SCHEMA_VERSION = "10FZ.APPROVAL.1"
_APPROVAL_REVISION = 1
_APPROVED_ACTION = "authorize_routing_execution"
_APPROVAL_STATUSES = frozenset({"operator_approved", "operator_denied"})
_SOURCE_STATUSES = frozenset({"authorized", "not_authorized"})

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

_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_SOURCE_FIELDS = frozenset(
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

_OUTPUT_FIELDS = frozenset(
    {
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
)

_SOURCE_STRING_FIELDS = (
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

_SOURCE_SAFE_METADATA_FIELDS = (
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
)

_OUTPUT_STRING_FIELDS = (
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

_OUTPUT_SAFE_METADATA_FIELDS = (
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
)

_SOURCE_CLAIM_BOUNDARY = (
    "report one model routing approval authorization decision only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

_CLAIM_BOUNDARY = (
    "report one 10FZ model routing authorization status only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "re-authorization, or gate-7 activity"
)

_INVALID_SOURCE_ERROR = (
    "authorization_report is not a valid 10FZ authorization report"
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

_SOURCE_MATERIAL_FIELDS = tuple(
    sorted(_SOURCE_FIELDS - {"authorization_report_decision_id"})
)
_STATUS_MATERIAL_FIELDS = tuple(
    sorted(_OUTPUT_FIELDS - {"authorization_status_report_decision_id"})
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


def _source_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {field: report[field] for field in _SOURCE_MATERIAL_FIELDS}


def _status_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {field: report[field] for field in _STATUS_MATERIAL_FIELDS}


def _validated_authorization_snapshot(
    source: object,
) -> dict[str, Any] | None:
    if type(source) is not dict:
        return None
    snapshot = dict(source)
    if any(type(key) is not str for key in snapshot):
        return None
    if set(snapshot) != _SOURCE_FIELDS:
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

    for field in _SOURCE_STRING_FIELDS:
        if type(snapshot[field]) is not str:
            return None
    status = snapshot["authorization_report_status"]
    approval_status = snapshot["approval_status"]
    if (
        snapshot["ok"] is not True
        or snapshot["authorization_report_schema_version"]
        != _SOURCE_SCHEMA_VERSION
        or snapshot["authorization_report_type"] != _SOURCE_TYPE
        or snapshot["authorization_report_scope"] != _SOURCE_SCOPE
        or snapshot["source_provenance_schema_version"]
        != _SOURCE_PROVENANCE_SCHEMA_VERSION
        or snapshot["approval_schema_version"] != _APPROVAL_SCHEMA_VERSION
        or type(snapshot["approval_revision"]) is not int
        or snapshot["approval_revision"] != _APPROVAL_REVISION
        or approval_status not in _APPROVAL_STATUSES
        or snapshot["approved_action"] != _APPROVED_ACTION
        or status not in _SOURCE_STATUSES
        or status == "authorized" and approval_status != "operator_approved"
        or snapshot["claim_boundary"] != _SOURCE_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["authorization_report_decision_id"],
            "10FZ-",
        )
        or not _is_decision_id(
            snapshot["source_provenance_decision_id"],
            "10FT-",
        )
        or not _is_decision_id(
            snapshot["source_policy_decision_id"],
            "10FT-POLICY-",
        )
        or not _is_decision_id(
            snapshot["approval_decision_id"],
            "10FZ-APPROVAL-",
        )
    ):
        return None

    if any(
        not _is_safe_text(snapshot[field])
        for field in _SOURCE_SAFE_METADATA_FIELDS
    ):
        return None
    if (
        not _is_prefixed_id(snapshot["authorized_lane"], "lane:")
        or not _is_prefixed_id(snapshot["authority_id"], "authority:")
        or not _is_prefixed_id(snapshot["provider_id"], "provider:")
        or not _is_prefixed_id(snapshot["pinned_model_id"], "model:")
        or not _is_prefixed_id(
            snapshot["approval_authority_id"],
            "approval-authority:",
        )
        or snapshot["provider_id"]
        != "provider:" + snapshot["provider_name"]
    ):
        return None

    for field in _GATE_FLAGS:
        if snapshot[field] is not False:
            return None
    if (
        any(type(boundary) is not str for boundary in forbidden_boundaries)
        or forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)
    ):
        return None
    if any(type(error) is not str for error in source_errors) or source_errors != []:
        return None

    expected_decision_id = "10FZ-" + _hash_canonical(
        _source_decision_material(snapshot)
    )[:32]
    if snapshot["authorization_report_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _status_report(
    *,
    source_authorization_schema_version: str = "",
    source_authorization_decision_id: str = "",
    source_authorization_status: str = "",
    source_authorization_ok: bool = False,
    source_provenance_decision_id: str = "",
    source_policy_decision_id: str = "",
    approval_decision_id: str = "",
    approval_status: str = "",
    artifact_class: str = "",
    artifact_family: str = "",
    authorized_lane: str = "",
    provider_id: str = "",
    provider_name: str = "",
    pinned_model_id: str = "",
    pinned_model_revision: str = "",
    authorization_status_report_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_errors = list(errors)
    result = {
        "ok": authorization_status_report_status
        in {"authorized_status", "not_authorized_status"},
        "authorization_status_report_schema_version": _SCHEMA_VERSION,
        "authorization_status_report_type": _STATUS_REPORT_TYPE,
        "authorization_status_report_scope": _STATUS_REPORT_SCOPE,
        "authorization_status_report_decision_id": "",
        "source_authorization_schema_version": (
            source_authorization_schema_version
        ),
        "source_authorization_decision_id": source_authorization_decision_id,
        "source_authorization_status": source_authorization_status,
        "source_authorization_ok": source_authorization_ok,
        "source_provenance_decision_id": source_provenance_decision_id,
        "source_policy_decision_id": source_policy_decision_id,
        "approval_decision_id": approval_decision_id,
        "approval_status": approval_status,
        "artifact_class": artifact_class,
        "artifact_family": artifact_family,
        "authorized_lane": authorized_lane,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "pinned_model_id": pinned_model_id,
        "pinned_model_revision": pinned_model_revision,
        "authorization_status_report_status": authorization_status_report_status,
        "executed": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": safe_errors,
    }
    result["authorization_status_report_decision_id"] = (
        "10GF-" + _hash_canonical(_status_decision_material(result))[:32]
    )
    return result


def create_minimal_inert_model_routing_authorization_report_status_report(
    authorization_report: dict | None,
) -> dict[str, Any]:
    """Report one supplied 10FZ authorization status without source access."""

    try:
        source = _validated_authorization_snapshot(authorization_report)
    except Exception:
        source = None
    if source is None:
        return _status_report(
            authorization_status_report_status="invalid_report",
            errors=[_INVALID_SOURCE_ERROR],
        )

    source_status = source["authorization_report_status"]
    status = (
        "authorized_status"
        if source_status == "authorized"
        else "not_authorized_status"
    )
    return _status_report(
        source_authorization_schema_version=source[
            "authorization_report_schema_version"
        ],
        source_authorization_decision_id=source[
            "authorization_report_decision_id"
        ],
        source_authorization_status=source_status,
        source_authorization_ok=source["ok"],
        source_provenance_decision_id=source[
            "source_provenance_decision_id"
        ],
        source_policy_decision_id=source["source_policy_decision_id"],
        approval_decision_id=source["approval_decision_id"],
        approval_status=source["approval_status"],
        artifact_class=source["artifact_class"],
        artifact_family=source["artifact_family"],
        authorized_lane=source["authorized_lane"],
        provider_id=source["provider_id"],
        provider_name=source["provider_name"],
        pinned_model_id=source["pinned_model_id"],
        pinned_model_revision=source["pinned_model_revision"],
        authorization_status_report_status=status,
        errors=[],
    )


def export_minimal_inert_model_routing_authorization_report_status_report(
    status_report: dict,
) -> str:
    """Export one validated 10GF status report as deterministic sorted JSON."""

    error = "status report must have the exact 10GF status report shape"
    if type(status_report) is not dict:
        raise ValueError(error)
    report = dict(status_report)
    if any(type(key) is not str for key in report):
        raise ValueError(error)
    if set(report) != _OUTPUT_FIELDS:
        raise ValueError(error)

    report_errors = report["errors"]
    if type(report_errors) is not list:
        raise ValueError(error)
    report_errors = list(report_errors)
    report["errors"] = report_errors

    for field in _OUTPUT_STRING_FIELDS:
        if type(report[field]) is not str:
            raise ValueError(error)
    if (
        report["authorization_status_report_schema_version"] != _SCHEMA_VERSION
        or report["authorization_status_report_type"] != _STATUS_REPORT_TYPE
        or report["authorization_status_report_scope"] != _STATUS_REPORT_SCOPE
        or report["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(
            report["authorization_status_report_decision_id"],
            "10GF-",
        )
        or type(report["ok"]) is not bool
        or type(report["source_authorization_ok"]) is not bool
    ):
        raise ValueError(error)
    for field in _GATE_FLAGS:
        if report[field] is not False:
            raise ValueError(error)
    if any(type(item) is not str for item in report_errors):
        raise ValueError(error)

    status = report["authorization_status_report_status"]
    if status == "invalid_report":
        expected_errors = [_INVALID_SOURCE_ERROR]
        source_is_valid = not any(
            (
                report["source_authorization_schema_version"] != "",
                report["source_authorization_decision_id"] != "",
                report["source_authorization_status"] != "",
                report["source_authorization_ok"] is not False,
                report["source_provenance_decision_id"] != "",
                report["source_policy_decision_id"] != "",
                report["approval_decision_id"] != "",
                report["approval_status"] != "",
                report["artifact_class"] != "",
                report["artifact_family"] != "",
                report["authorized_lane"] != "",
                report["provider_id"] != "",
                report["provider_name"] != "",
                report["pinned_model_id"] != "",
                report["pinned_model_revision"] != "",
            )
        )
        expected_ok = False
    elif status in {"authorized_status", "not_authorized_status"}:
        expected_errors = []
        expected_source_status = (
            "authorized"
            if status == "authorized_status"
            else "not_authorized"
        )
        source_is_valid = not any(
            (
                report["source_authorization_schema_version"]
                != _SOURCE_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_authorization_decision_id"],
                    "10FZ-",
                ),
                report["source_authorization_status"]
                != expected_source_status,
                report["source_authorization_ok"] is not True,
                not _is_decision_id(
                    report["source_provenance_decision_id"],
                    "10FT-",
                ),
                not _is_decision_id(
                    report["source_policy_decision_id"],
                    "10FT-POLICY-",
                ),
                not _is_decision_id(
                    report["approval_decision_id"],
                    "10FZ-APPROVAL-",
                ),
                report["approval_status"] not in _APPROVAL_STATUSES,
                status == "authorized_status"
                and report["approval_status"] != "operator_approved",
                any(
                    not _is_safe_text(report[field])
                    for field in _OUTPUT_SAFE_METADATA_FIELDS
                ),
                not _is_prefixed_id(report["authorized_lane"], "lane:"),
                not _is_prefixed_id(report["provider_id"], "provider:"),
                not _is_prefixed_id(report["pinned_model_id"], "model:"),
                report["provider_id"]
                != "provider:" + report["provider_name"],
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

    expected_decision_id = "10GF-" + _hash_canonical(
        _status_decision_material(report)
    )[:32]
    if report["authorization_status_report_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
