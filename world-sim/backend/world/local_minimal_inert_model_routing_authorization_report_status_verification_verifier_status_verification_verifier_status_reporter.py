"""Phase 10GR - inert model-routing authorization meta-verification.

Consumes one caller-supplied 10GL dictionary and returns a sanitized
meta-verification artifact. No source service, file, process, or world state is
used.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


_SCHEMA_VERSION = "10GR.1"
_META_VERIFICATION_TYPE = (
    "minimal_inert_model_routing_authorization_report_status_verification_"
    "verifier_status_verification_verifier_status_report"
)
_META_VERIFICATION_SCOPE = (
    "model_routing_authorization_report_status_verification_verifier_status_"
    "verification_only"
)

_SOURCE_SCHEMA_VERSION = "10GL.1"
_SOURCE_TYPE = (
    "minimal_inert_model_routing_authorization_report_status_verification_"
    "verifier_status_report"
)
_SOURCE_SCOPE = (
    "model_routing_authorization_report_status_verification_only"
)
_SOURCE_STATUS_REPORT_SCHEMA_VERSION = "10GF.1"
_SOURCE_AUTHORIZATION_SCHEMA_VERSION = "10FZ.1"
_APPROVAL_STATUSES = frozenset({"operator_approved", "operator_denied"})
_SOURCE_VERIFICATION_STATUSES = frozenset(
    {"verified_authorized_status", "verified_not_authorized_status"}
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
        "authorization_status_verification_schema_version",
        "authorization_status_verification_type",
        "authorization_status_verification_scope",
        "authorization_status_verification_decision_id",
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
        "authorization_status_verification_status",
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
)

_SOURCE_STRING_FIELDS = (
    "authorization_status_verification_schema_version",
    "authorization_status_verification_type",
    "authorization_status_verification_scope",
    "authorization_status_verification_decision_id",
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
    "authorization_status_verification_status",
    "claim_boundary",
)

_SAFE_METADATA_FIELDS = (
    "artifact_class",
    "artifact_family",
    "authorized_lane",
    "provider_id",
    "provider_name",
    "pinned_model_id",
    "pinned_model_revision",
)

_OUTPUT_STRING_FIELDS = (
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

_OUTPUT_SOURCE_STRING_FIELDS = (
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

_SOURCE_CLAIM_BOUNDARY = (
    "verify one 10GF model routing authorization status report only; no runtime "
    "execution, provider call, model invocation, filesystem scan, config "
    "mutation, agent launch, world-data access, ledger access, write, repair, "
    "re-authorization, source verification, or gate-7 activity"
)

_CLAIM_BOUNDARY = (
    "verify one 10GL model routing authorization status verification report "
    "only; no runtime execution, provider call, model invocation, filesystem "
    "scan, config mutation, agent launch, world-data access, ledger access, "
    "write, repair, re-authorization, source verification, status-report "
    "re-verification, or gate-7 activity"
)

_INVALID_SOURCE_ERROR = (
    "verification_report is not a valid 10GL authorization status verification "
    "report"
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
    "gl" + "pat",
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
    sorted(_SOURCE_FIELDS - {"authorization_status_verification_decision_id"})
)
_META_MATERIAL_FIELDS = tuple(
    sorted(
        _OUTPUT_FIELDS
        - {"authorization_status_meta_verification_decision_id"}
    )
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
            len(value) >= 2 and value[1] == ":",
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
        type(value) is str
        and value.startswith(prefix)
        and len(value) > len(prefix)
        and _is_safe_text(value[len(prefix) :])
    )


def _source_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {field: report[field] for field in _SOURCE_MATERIAL_FIELDS}


def _meta_decision_material(report: dict[str, Any]) -> dict[str, Any]:
    return {field: report[field] for field in _META_MATERIAL_FIELDS}


def _validated_verification_snapshot(
    source: object,
) -> dict[str, Any] | None:
    if type(source) is not dict:
        return None
    snapshot = dict(source)
    if any(type(key) is not str for key in snapshot):
        return None
    if set(snapshot) != _SOURCE_FIELDS:
        return None

    source_errors = snapshot["errors"]
    if type(source_errors) is not list:
        return None
    source_errors = list(source_errors)
    snapshot["errors"] = source_errors

    for field in _SOURCE_STRING_FIELDS:
        if type(snapshot[field]) is not str:
            return None
    verification_status = snapshot["authorization_status_verification_status"]
    report_status = snapshot["source_status_report_status"]
    authorization_status = snapshot["source_authorization_status"]
    approval_status = snapshot["approval_status"]
    authorized = verification_status == "verified_authorized_status"
    if (
        snapshot["ok"] is not True
        or snapshot["source_status_report_ok"] is not True
        or snapshot["source_authorization_ok"] is not True
        or snapshot["authorization_status_verification_schema_version"]
        != _SOURCE_SCHEMA_VERSION
        or snapshot["authorization_status_verification_type"] != _SOURCE_TYPE
        or snapshot["authorization_status_verification_scope"] != _SOURCE_SCOPE
        or snapshot["source_status_report_schema_version"]
        != _SOURCE_STATUS_REPORT_SCHEMA_VERSION
        or snapshot["source_authorization_schema_version"]
        != _SOURCE_AUTHORIZATION_SCHEMA_VERSION
        or verification_status not in _SOURCE_VERIFICATION_STATUSES
        or report_status
        != ("authorized_status" if authorized else "not_authorized_status")
        or authorization_status
        != ("authorized" if authorized else "not_authorized")
        or approval_status not in _APPROVAL_STATUSES
        or authorized
        and approval_status != "operator_approved"
        or snapshot["claim_boundary"] != _SOURCE_CLAIM_BOUNDARY
        or not _is_decision_id(
            snapshot["authorization_status_verification_decision_id"],
            "10GL-",
        )
        or not _is_decision_id(
            snapshot["source_status_report_decision_id"],
            "10GF-",
        )
        or not _is_decision_id(
            snapshot["source_authorization_decision_id"],
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
        for field in _SAFE_METADATA_FIELDS
    ):
        return None
    if (
        not _is_prefixed_id(snapshot["authorized_lane"], "lane:")
        or not _is_prefixed_id(snapshot["provider_id"], "provider:")
        or not _is_prefixed_id(snapshot["pinned_model_id"], "model:")
        or snapshot["provider_id"]
        != "provider:" + snapshot["provider_name"]
    ):
        return None

    for field in _GATE_FLAGS:
        if snapshot[field] is not False:
            return None
    if any(type(error) is not str for error in source_errors) or source_errors != []:
        return None

    expected_decision_id = "10GL-" + _hash_canonical(
        _source_decision_material(snapshot)
    )[:32]
    if (
        snapshot["authorization_status_verification_decision_id"]
        != expected_decision_id
    ):
        return None
    return snapshot


def _meta_verification_report(
    *,
    source_verification_schema_version: str = "",
    source_verification_decision_id: str = "",
    source_verification_status: str = "",
    source_verification_ok: bool = False,
    source_status_report_schema_version: str = "",
    source_status_report_decision_id: str = "",
    source_status_report_status: str = "",
    source_status_report_ok: bool = False,
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
    authorization_status_meta_verification_status: str,
    errors: list[str],
) -> dict[str, Any]:
    safe_errors = list(errors)
    result = {
        "ok": authorization_status_meta_verification_status
        in {
            "verified_authorized_verification_status",
            "verified_not_authorized_verification_status",
        },
        "authorization_status_meta_verification_schema_version": (
            _SCHEMA_VERSION
        ),
        "authorization_status_meta_verification_type": _META_VERIFICATION_TYPE,
        "authorization_status_meta_verification_scope": (
            _META_VERIFICATION_SCOPE
        ),
        "authorization_status_meta_verification_decision_id": "",
        "source_verification_schema_version": source_verification_schema_version,
        "source_verification_decision_id": source_verification_decision_id,
        "source_verification_status": source_verification_status,
        "source_verification_ok": source_verification_ok,
        "source_status_report_schema_version": source_status_report_schema_version,
        "source_status_report_decision_id": source_status_report_decision_id,
        "source_status_report_status": source_status_report_status,
        "source_status_report_ok": source_status_report_ok,
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
        "authorization_status_meta_verification_status": (
            authorization_status_meta_verification_status
        ),
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
    result["authorization_status_meta_verification_decision_id"] = (
        "10GR-" + _hash_canonical(_meta_decision_material(result))[:32]
    )
    return result


def create_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report(
    verification_report: dict | None,
) -> dict[str, Any]:
    """Meta-verify one supplied 10GL report without source access."""

    try:
        source = _validated_verification_snapshot(verification_report)
    except Exception:
        source = None
    if source is None:
        return _meta_verification_report(
            authorization_status_meta_verification_status=(
                "invalid_verification_report"
            ),
            errors=[_INVALID_SOURCE_ERROR],
        )

    source_status = source["authorization_status_verification_status"]
    meta_status = (
        "verified_authorized_verification_status"
        if source_status == "verified_authorized_status"
        else "verified_not_authorized_verification_status"
    )
    return _meta_verification_report(
        source_verification_schema_version=source[
            "authorization_status_verification_schema_version"
        ],
        source_verification_decision_id=source[
            "authorization_status_verification_decision_id"
        ],
        source_verification_status=source_status,
        source_verification_ok=source["ok"],
        source_status_report_schema_version=source[
            "source_status_report_schema_version"
        ],
        source_status_report_decision_id=source[
            "source_status_report_decision_id"
        ],
        source_status_report_status=source["source_status_report_status"],
        source_status_report_ok=source["source_status_report_ok"],
        source_authorization_schema_version=source[
            "source_authorization_schema_version"
        ],
        source_authorization_decision_id=source[
            "source_authorization_decision_id"
        ],
        source_authorization_status=source["source_authorization_status"],
        source_authorization_ok=source["source_authorization_ok"],
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
        authorization_status_meta_verification_status=meta_status,
        errors=[],
    )


def export_minimal_inert_model_routing_authorization_report_status_verification_verifier_status_verification_verifier_status_report(
    meta_verification_report: dict,
) -> str:
    """Export one validated 10GR meta-verification report as sorted JSON."""

    error = "meta-verification report must have the exact 10GR meta-verification report shape"
    if type(meta_verification_report) is not dict:
        raise ValueError(error)
    report = dict(meta_verification_report)
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
        report["authorization_status_meta_verification_schema_version"]
        != _SCHEMA_VERSION
        or report["authorization_status_meta_verification_type"]
        != _META_VERIFICATION_TYPE
        or report["authorization_status_meta_verification_scope"]
        != _META_VERIFICATION_SCOPE
        or report["claim_boundary"] != _CLAIM_BOUNDARY
        or not _is_decision_id(
            report["authorization_status_meta_verification_decision_id"],
            "10GR-",
        )
        or type(report["ok"]) is not bool
        or type(report["source_verification_ok"]) is not bool
        or type(report["source_status_report_ok"]) is not bool
        or type(report["source_authorization_ok"]) is not bool
    ):
        raise ValueError(error)
    for field in _GATE_FLAGS:
        if report[field] is not False:
            raise ValueError(error)
    if any(type(item) is not str for item in report_errors):
        raise ValueError(error)

    status = report["authorization_status_meta_verification_status"]
    if status == "invalid_verification_report":
        expected_errors = [_INVALID_SOURCE_ERROR]
        source_is_valid = not any(
            (
                any(
                    report[field] != ""
                    for field in _OUTPUT_SOURCE_STRING_FIELDS
                ),
                report["source_verification_ok"] is not False,
                report["source_status_report_ok"] is not False,
                report["source_authorization_ok"] is not False,
            )
        )
        expected_ok = False
    elif status in {
        "verified_authorized_verification_status",
        "verified_not_authorized_verification_status",
    }:
        expected_errors = []
        authorized = status == "verified_authorized_verification_status"
        expected_source_status = (
            "verified_authorized_status"
            if authorized
            else "verified_not_authorized_status"
        )
        expected_status_report_status = (
            "authorized_status" if authorized else "not_authorized_status"
        )
        expected_authorization_status = (
            "authorized" if authorized else "not_authorized"
        )
        source_is_valid = not any(
            (
                report["source_verification_schema_version"]
                != _SOURCE_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_verification_decision_id"],
                    "10GL-",
                ),
                report["source_verification_status"] != expected_source_status,
                report["source_verification_ok"] is not True,
                report["source_status_report_schema_version"]
                != _SOURCE_STATUS_REPORT_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_status_report_decision_id"],
                    "10GF-",
                ),
                report["source_status_report_status"]
                != expected_status_report_status,
                report["source_status_report_ok"] is not True,
                report["source_authorization_schema_version"]
                != _SOURCE_AUTHORIZATION_SCHEMA_VERSION,
                not _is_decision_id(
                    report["source_authorization_decision_id"],
                    "10FZ-",
                ),
                report["source_authorization_status"]
                != expected_authorization_status,
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
                authorized
                and report["approval_status"] != "operator_approved",
                any(
                    not _is_safe_text(report[field])
                    for field in _SAFE_METADATA_FIELDS
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

    expected_decision_id = "10GR-" + _hash_canonical(
        _meta_decision_material(report)
    )[:32]
    if (
        report["authorization_status_meta_verification_decision_id"]
        != expected_decision_id
    ):
        raise ValueError(error)
    return json.dumps(report, sort_keys=True, ensure_ascii=False)
