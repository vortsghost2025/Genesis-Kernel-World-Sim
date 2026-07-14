"""Phase 10FT - inert model-routing provenance reporting.

Consumes one caller-supplied policy dictionary and returns a sanitized
provenance artifact. No source service, file, process, or world state is used.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10FT.1"
_REPORT_TYPE = "minimal_inert_model_routing_provenance_report"
_REPORT_SCOPE = "model_routing_provenance_report_only"
_POLICY_SCHEMA_VERSION = "10FT.POLICY.1"
_POLICY_REVISION = 1
_POLICY_TYPE = "minimal_inert_model_routing_provenance_policy"
_POLICY_SCOPE = "model_routing_provenance_policy_only"
_ALLOWED_ACTION = "produce_artifact"

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

_SOURCE_FALSE_FLAGS = (
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

_OUTPUT_GATE_FLAGS = (
    "executed",
    "runtime_allowed",
    "daemon_allowed",
    "scheduler_allowed",
    "network_allowed",
    "world_sim_data_accessed",
    "gate7_activity_allowed",
)

_TRUE_LOCK_FLAGS = (
    "model_pinned",
    "provider_pinned",
    "route_locked",
)

_SOURCE_FIELDS = frozenset(
    {
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
)

_OUTPUT_FIELDS = frozenset(
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

_SOURCE_STRING_FIELDS = (
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
)

_OUTPUT_STRING_FIELDS = (
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
)

_SOURCE_CLAIM_BOUNDARY = (
    "authorize one model routing provenance artifact only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "or gate-7 activity"
)

_REPORT_CLAIM_BOUNDARY = (
    "report one model routing provenance policy only; no runtime execution, "
    "provider call, model invocation, filesystem scan, config mutation, "
    "agent launch, world-data access, ledger access, write, repair, or gate-7 "
    "activity"
)

_INVALID_SOURCE_ERROR = (
    "routing_provenance_artifact is not a valid 10FT routing provenance policy"
)

_SAFE_TEXT_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:"
)
_SENSITIVE_COMPACT_FRAGMENTS = (
    "api" + "key",
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

_POLICY_MATERIAL_FIELDS = tuple(
    sorted(_SOURCE_FIELDS - {"policy_decision_id"})
)
_REPORT_MATERIAL_FIELDS = tuple(
    sorted(_OUTPUT_FIELDS - {"provenance_report_decision_id"})
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
        and isinstance(value, str)
        and value.startswith(prefix)
        and len(value) > len(prefix)
    )


def _policy_decision_material(source: dict[str, Any]) -> dict[str, Any]:
    return {field: source[field] for field in _POLICY_MATERIAL_FIELDS}


def _provenance_report_decision_material(
    report: dict[str, Any],
) -> dict[str, Any]:
    return {field: report[field] for field in _REPORT_MATERIAL_FIELDS}


def _validated_policy_snapshot(source: object) -> dict[str, Any] | None:
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
    if (
        snapshot["policy_schema_version"] != _POLICY_SCHEMA_VERSION
        or type(snapshot["policy_revision"]) is not int
        or snapshot["policy_revision"] != _POLICY_REVISION
        or snapshot["policy_type"] != _POLICY_TYPE
        or snapshot["policy_scope"] != _POLICY_SCOPE
        or snapshot["allowed_action"] != _ALLOWED_ACTION
        or snapshot["claim_boundary"] != _SOURCE_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["policy_decision_id"],
            "10FT-POLICY-",
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
        or snapshot["provider_id"]
        != "provider:" + snapshot["provider_name"]
    ):
        return None

    for field in _TRUE_LOCK_FLAGS:
        if snapshot[field] is not True:
            return None
    for field in _SOURCE_FALSE_FLAGS:
        if snapshot[field] is not False:
            return None

    if (
        any(type(boundary) is not str for boundary in forbidden_boundaries)
        or forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES)
    ):
        return None

    if any(type(error) is not str for error in source_errors) or source_errors != []:
        return None

    expected_decision_id = "10FT-POLICY-" + _hash_canonical(
        _policy_decision_material(snapshot)
    )[:32]
    if snapshot["policy_decision_id"] != expected_decision_id:
        return None
    return snapshot


def _provenance_report(
    *,
    source_policy_schema_version: str = "",
    source_policy_revision: int = 0,
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
    forbidden_boundaries: list[str] | None = None,
    provenance_report_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_boundaries = list(forbidden_boundaries or [])
    safe_errors = list(errors)
    result = {
        "ok": provenance_report_status == "verified_provenance",
        "provenance_report_schema_version": _SCHEMA_VERSION,
        "provenance_report_type": _REPORT_TYPE,
        "provenance_report_scope": _REPORT_SCOPE,
        "provenance_report_decision_id": "",
        "source_policy_schema_version": source_policy_schema_version,
        "source_policy_revision": source_policy_revision,
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
        "forbidden_boundaries": safe_boundaries,
        "provenance_report_status": provenance_report_status,
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
    result["provenance_report_decision_id"] = "10FT-" + _hash_canonical(
        _provenance_report_decision_material(result)
    )[:32]
    return result


def create_minimal_inert_model_routing_provenance_report(
    routing_provenance_artifact: dict | None,
) -> dict[str, Any]:
    """Report one supplied routing policy without source-system access."""

    try:
        source = _validated_policy_snapshot(routing_provenance_artifact)
    except Exception:
        source = None
    if source is None:
        return _provenance_report(
            provenance_report_status="invalid_report",
            errors=[_INVALID_SOURCE_ERROR],
        )

    return _provenance_report(
        source_policy_schema_version=source["policy_schema_version"],
        source_policy_revision=source["policy_revision"],
        source_policy_decision_id=source["policy_decision_id"],
        artifact_class=source["artifact_class"],
        artifact_family=source["artifact_family"],
        authorized_lane=source["authorized_lane"],
        authority_id=source["authority_id"],
        authority_basis=source["authority_basis"],
        provider_id=source["provider_id"],
        provider_name=source["provider_name"],
        pinned_model_id=source["pinned_model_id"],
        pinned_model_revision=source["pinned_model_revision"],
        forbidden_boundaries=source["forbidden_boundaries"],
        provenance_report_status="verified_provenance",
        errors=[],
    )


def export_minimal_inert_model_routing_provenance_report(
    provenance_report: dict,
) -> str:
    """Export one validated 10FT provenance report as deterministic JSON."""

    error = "provenance report must have the exact 10FT provenance report shape"
    if type(provenance_report) is not dict:
        raise ValueError(error)
    report = dict(provenance_report)
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
        report["provenance_report_schema_version"] != _SCHEMA_VERSION
        or report["provenance_report_type"] != _REPORT_TYPE
        or report["provenance_report_scope"] != _REPORT_SCOPE
        or report["claim_boundary"] != _REPORT_CLAIM_BOUNDARY
        or not _is_decision_id(
            report["provenance_report_decision_id"],
            "10FT-",
        )
        or type(report["source_policy_revision"]) is not int
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

    status = report["provenance_report_status"]
    if status == "invalid_report":
        expected_errors = [_INVALID_SOURCE_ERROR]
        source_is_valid = not any(
            (
                report["source_policy_schema_version"] != "",
                report["source_policy_revision"] != 0,
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
                bool(forbidden_boundaries),
            )
        )
    elif status == "verified_provenance":
        expected_errors = []
        source_is_valid = not any(
            (
                report["source_policy_schema_version"] != _POLICY_SCHEMA_VERSION,
                report["source_policy_revision"] != _POLICY_REVISION,
                not _is_decision_id(
                    report["source_policy_decision_id"],
                    "10FT-POLICY-",
                ),
                any(
                    not _is_safe_text(report[field])
                    for field in _OUTPUT_SAFE_METADATA_FIELDS
                ),
                not _is_prefixed_id(report["authorized_lane"], "lane:"),
                not _is_prefixed_id(report["authority_id"], "authority:"),
                not _is_prefixed_id(report["provider_id"], "provider:"),
                not _is_prefixed_id(report["pinned_model_id"], "model:"),
                report["provider_id"]
                != "provider:" + report["provider_name"],
                forbidden_boundaries != list(_FORBIDDEN_BOUNDARIES),
            )
        )
    else:
        raise ValueError(error)

    if (
        not source_is_valid
        or report_errors != expected_errors
        or report["ok"] is not (status == "verified_provenance")
    ):
        raise ValueError(error)

    expected_decision_id = "10FT-" + _hash_canonical(
        _provenance_report_decision_material(report)
    )[:32]
    if report["provenance_report_decision_id"] != expected_decision_id:
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
