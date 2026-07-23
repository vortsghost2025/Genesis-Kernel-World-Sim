"""Phase 10IE - pure in-memory first-pair memory boundary.

Associates a verified Phase 10ID habitat boundary with separate Adam and Eve
memory-reference lists. Each list is agent-scoped, only explicitly public
references may cross identities, private references belonging to the other
identity are rejected, and the complete boundary fails closed when either side
is invalid. Does not create runtime entities, persist state, write a ledger,
or perform external work.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.local_first_pair_birth_candidate import (
    create_first_pair_birth_candidate,
)
from backend.world.local_first_pair_habitat_boundary import (
    create_first_pair_habitat_boundary,
)


_MEMORY_BOUNDARY_SCHEMA_VERSION = "10IE.1"
_MEMORY_BOUNDARY_TYPE = "first_pair_memory_boundary"
_MEMORY_BOUNDARY_SCOPE = "pure_in_memory_boundary_only"
_PAIR_ID = "genesis-first-pair"

_REQUEST_FIELDS = frozenset(
    {
        "memory_boundary_schema_version",
        "habitat_boundary",
        "authorized_declaration",
        "adam_memory_refs",
        "eve_memory_refs",
    }
)

_IDENTITY_REF_FIELDS = frozenset(
    {
        "agent_id",
        "canonical_name",
        "canonical_agent_ref",
    }
)

_MEMORY_REF_FIELDS = frozenset(
    {
        "ref_id",
        "owner_agent_id",
        "ref_type",
        "is_public",
    }
)

_VALID_REF_TYPES = frozenset(
    {
        "public_observation",
        "public_evidence",
        "identity_provenance",
        "habitat_boundary",
        "rollback_anchor",
    }
)

_SAFE_IDENTIFIER_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
)
_FORBIDDEN_IDENTIFIER_MARKERS = (
    "true_map",
    "known_map",
    "hidden_substrate",
    "world-sim/data",
    "[redacted",
)
_FORBIDDEN_PATH_MARKERS = ("/", "%2f", "%5c", "\\")
_SENSITIVE_IDENTIFIER_MARKERS = (
    "api_key",
    "access_token",
    "password",
    "secret",
    "private_config",
    ".env",
)

_CLAIM_BOUNDARY = (
    "memory boundary contract only; no runtime entity, memory write, "
    "ledger write, persistence, model, provider, network, background service, "
    "or gate activity"
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


def _has_exact_string_keys(value: Any, expected: frozenset[str] | set[str]) -> bool:
    if type(value) is not dict:
        return False
    keys = list(value.keys())
    if not all(type(key) is str for key in keys):
        return False
    return len(keys) == len(expected) and frozenset(keys) == frozenset(expected)


def _is_safe_identifier(value: Any) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 128:
        return False
    if not all(character in _SAFE_IDENTIFIER_CHARACTERS for character in value):
        return False
    lowered = value.lower()
    collapsed = "".join(
        character for character in lowered if character.isalnum()
    )
    if ".." in value or any(
        marker in lowered for marker in _FORBIDDEN_IDENTIFIER_MARKERS
    ):
        return False
    if any(
        marker in collapsed
        for marker in ("truemap", "knownmap", "hiddensubstrate")
    ):
        return False
    if any(marker in value for marker in _FORBIDDEN_PATH_MARKERS):
        return False
    return True


def _contains_private_path_marker(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in value or marker in lowered for marker in ("/", "\\"))


def _finalize_id(result: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    material = dict(result)
    material.pop(field, None)
    result[field] = prefix + _hash_canonical(material)[:32]
    return result


def _extract_identity_ref(identity: Any) -> dict[str, Any] | None:
    if type(identity) is not dict:
        return None
    if not _has_exact_string_keys(identity, _IDENTITY_REF_FIELDS):
        return None
    agent_id = identity["agent_id"]
    canonical_name = identity["canonical_name"]
    canonical_agent_ref = identity["canonical_agent_ref"]
    if type(agent_id) is not str or not _is_safe_identifier(agent_id):
        return None
    if type(canonical_name) is not str or not _is_safe_identifier(canonical_name):
        return None
    if (
        type(canonical_agent_ref) is not str
        or not _is_safe_identifier(canonical_agent_ref)
    ):
        return None
    return {
        "agent_id": agent_id,
        "canonical_name": canonical_name,
        "canonical_agent_ref": canonical_agent_ref,
    }


def _is_habitat_boundary_intact(boundary: Any) -> bool:
    if type(boundary) is not dict:
        return False
    if boundary.get("ok") is not True:
        return False
    expected_fields = {
        "ok",
        "habitat_boundary_schema_version",
        "habitat_boundary_type",
        "habitat_boundary_scope",
        "habitat_boundary_id",
        "status",
        "pair_id",
        "birth_candidate_id",
        "adam_identity_ref",
        "eve_identity_ref",
        "habitat",
        "rollback_anchor",
        "observation_radius",
        "boundary_tile_ids",
        "within_bounds",
        "executed",
        "runtime_entity_created",
        "persisted",
        "memory_written",
        "ledger_written",
        "write_attempted",
        "model_called",
        "provider_called",
        "network_called",
        "daemon_started",
        "scheduler_started",
        "container_started",
        "docker_started",
        "runtime_allowed",
        "daemon_allowed",
        "scheduler_allowed",
        "network_allowed",
        "world_sim_data_accessed",
        "gate7_activity_allowed",
        "claim_boundary",
        "errors",
    }
    if not _has_exact_string_keys(boundary, expected_fields):
        return False
    if boundary.get("status") != "habitat_boundary_verified":
        return False
    if boundary.get("within_bounds") is not True:
        return False
    if boundary.get("pair_id") != _PAIR_ID:
        return False
    if type(boundary.get("habitat_boundary_id")) is not str:
        return False
    if not boundary["habitat_boundary_id"].startswith("10ID-"):
        return False
    material = dict(boundary)
    material.pop("habitat_boundary_id", None)
    expected_id = "10ID-" + _hash_canonical(material)[:32]
    if boundary["habitat_boundary_id"] != expected_id:
        return False
    return True


def _validate_memory_ref(
    ref: Any,
    *,
    self_agent_id: str,
    other_agent_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if type(ref) is not dict:
        return None, "invalid_memory_ref"
    if not _has_exact_string_keys(ref, _MEMORY_REF_FIELDS):
        return None, "invalid_memory_ref"

    ref_id = ref["ref_id"]
    owner_agent_id = ref["owner_agent_id"]
    ref_type = ref["ref_type"]
    is_public = ref["is_public"]

    if type(ref_id) is not str:
        return None, "invalid_memory_ref"
    lowered = ref_id.lower()
    collapsed = "".join(c for c in lowered if c.isalnum())
    if any(marker in lowered for marker in _FORBIDDEN_IDENTIFIER_MARKERS):
        return None, "hidden_substrate_leakage"
    if any(
        marker in collapsed
        for marker in ("truemap", "knownmap", "hiddensubstrate")
    ):
        return None, "hidden_substrate_leakage"
    if any(marker in ref_id for marker in _FORBIDDEN_PATH_MARKERS):
        return None, "private_path_leakage"
    if any(marker in lowered for marker in _SENSITIVE_IDENTIFIER_MARKERS):
        return None, "sensitive_identifier_leakage"
    if not _is_safe_identifier(ref_id):
        return None, "invalid_memory_ref"
    if type(owner_agent_id) is not str or not _is_safe_identifier(owner_agent_id):
        return None, "invalid_memory_ref"
    if type(ref_type) is not str or ref_type not in _VALID_REF_TYPES:
        return None, "invalid_memory_ref"
    if type(is_public) is not bool:
        return None, "invalid_memory_ref"
    if owner_agent_id != self_agent_id and owner_agent_id != other_agent_id:
        return None, "invalid_memory_ref"
    if (
        owner_agent_id == other_agent_id
        and is_public is not True
    ):
        return None, "cross_agent_memory_leak"

    validated = {
        "ref_id": ref_id,
        "owner_agent_id": owner_agent_id,
        "ref_type": ref_type,
        "is_public": is_public,
    }
    return validated, None


def _validate_memory_refs(
    refs: Any,
    *,
    self_agent_id: str,
    other_agent_id: str,
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    if type(refs) is not list:
        return None, ["invalid_memory_ref"]
    validated_refs: list[dict[str, Any]] = []
    errors: list[str] = []
    for ref in refs:
        validated, error = _validate_memory_ref(
            ref,
            self_agent_id=self_agent_id,
            other_agent_id=other_agent_id,
        )
        if validated is None:
            if error is not None and error not in errors:
                errors.append(error)
            return None, errors
        validated_refs.append(validated)
    return validated_refs, []


def _boundary_result(
    *,
    errors: list[str],
    within_bounds: bool,
    habitat_boundary_id: str | None = None,
    birth_candidate_id: str | None = None,
    adam_identity_ref: dict[str, Any] | None = None,
    eve_identity_ref: dict[str, Any] | None = None,
    habitat: dict[str, Any] | None = None,
    rollback_anchor: dict[str, Any] | None = None,
    observation_radius: int | None = None,
    adam_memory_refs: list[dict[str, Any]] | None = None,
    eve_memory_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ok = not errors
    result: dict[str, Any] = {
        "ok": ok,
        "memory_boundary_schema_version": _MEMORY_BOUNDARY_SCHEMA_VERSION,
        "memory_boundary_type": _MEMORY_BOUNDARY_TYPE,
        "memory_boundary_scope": _MEMORY_BOUNDARY_SCOPE,
        "status": (
            "memory_boundary_verified" if ok else "invalid_memory_boundary"
        ),
        "pair_id": _PAIR_ID,
        "habitat_boundary_id": habitat_boundary_id,
        "birth_candidate_id": birth_candidate_id,
        "adam_identity_ref": adam_identity_ref,
        "eve_identity_ref": eve_identity_ref,
        "habitat": habitat,
        "rollback_anchor": rollback_anchor,
        "observation_radius": observation_radius,
        "adam_memory_refs": adam_memory_refs if adam_memory_refs is not None else [],
        "eve_memory_refs": eve_memory_refs if eve_memory_refs is not None else [],
        "within_bounds": within_bounds,
        "executed": False,
        "runtime_entity_created": False,
        "persisted": False,
        "memory_written": False,
        "ledger_written": False,
        "write_attempted": False,
        "model_called": False,
        "provider_called": False,
        "network_called": False,
        "daemon_started": False,
        "scheduler_started": False,
        "container_started": False,
        "docker_started": False,
        "runtime_allowed": False,
        "daemon_allowed": False,
        "scheduler_allowed": False,
        "network_allowed": False,
        "world_sim_data_accessed": False,
        "gate7_activity_allowed": False,
        "claim_boundary": _CLAIM_BOUNDARY,
        "errors": errors,
    }
    return _finalize_id(result, "memory_boundary_id", "10IE-")


def create_first_pair_memory_boundary(request: dict) -> dict[str, Any]:
    """Create a pure in-memory memory boundary over a verified 10ID habitat boundary."""

    if not _has_exact_string_keys(request, _REQUEST_FIELDS):
        return _boundary_result(
            errors=["invalid_request"],
            within_bounds=False,
        )

    schema_version = request["memory_boundary_schema_version"]
    if (
        type(schema_version) is not str
        or schema_version != _MEMORY_BOUNDARY_SCHEMA_VERSION
    ):
        return _boundary_result(
            errors=["invalid_request"],
            within_bounds=False,
        )

    habitat_boundary = request["habitat_boundary"]
    authorized_declaration = request["authorized_declaration"]

    if not _is_habitat_boundary_intact(habitat_boundary):
        return _boundary_result(
            errors=["invalid_habitat_boundary"],
            within_bounds=False,
        )

    adam_ref = _extract_identity_ref(habitat_boundary["adam_identity_ref"])
    eve_ref = _extract_identity_ref(habitat_boundary["eve_identity_ref"])
    if adam_ref is None or eve_ref is None:
        return _boundary_result(
            errors=["invalid_habitat_boundary"],
            within_bounds=False,
        )
    if adam_ref["agent_id"] == eve_ref["agent_id"]:
        return _boundary_result(
            errors=["invalid_habitat_boundary"],
            within_bounds=False,
        )

    if type(authorized_declaration) is not dict:
        return _boundary_result(
            errors=["invalid_request"],
            within_bounds=False,
        )

    authorized_candidate = create_first_pair_birth_candidate(authorized_declaration)
    if authorized_candidate.get("ok") is not True:
        return _boundary_result(
            errors=["candidate_declaration_drift"],
            within_bounds=False,
            habitat_boundary_id=habitat_boundary["habitat_boundary_id"],
            birth_candidate_id=habitat_boundary["birth_candidate_id"],
            adam_identity_ref=adam_ref,
            eve_identity_ref=eve_ref,
        )

    reconstructed_habitat_request = {
        "habitat_boundary_schema_version": "10ID.1",
        "birth_candidate": authorized_candidate,
        "authorized_declaration": authorized_declaration,
        "observation_radius": habitat_boundary["observation_radius"],
    }
    recreated_habitat_boundary = create_first_pair_habitat_boundary(
        reconstructed_habitat_request
    )
    if recreated_habitat_boundary.get("ok") is not True:
        return _boundary_result(
            errors=["candidate_declaration_drift"],
            within_bounds=False,
        )
    recreated_clean = dict(recreated_habitat_boundary)
    supplied_clean = dict(habitat_boundary)
    recreated_clean.pop("habitat_boundary_id", None)
    supplied_clean.pop("habitat_boundary_id", None)
    if recreated_clean != supplied_clean:
        return _boundary_result(
            errors=["candidate_declaration_drift"],
            within_bounds=False,
        )

    adam_agent_id = adam_ref["agent_id"]
    eve_agent_id = eve_ref["agent_id"]

    adam_memory_refs = request["adam_memory_refs"]
    eve_memory_refs = request["eve_memory_refs"]

    adam_validated, adam_errors = _validate_memory_refs(
        adam_memory_refs,
        self_agent_id=adam_agent_id,
        other_agent_id=eve_agent_id,
    )
    eve_validated, eve_errors = _validate_memory_refs(
        eve_memory_refs,
        self_agent_id=eve_agent_id,
        other_agent_id=adam_agent_id,
    )

    all_errors = sorted(set(adam_errors + eve_errors))
    if all_errors:
        return _boundary_result(
            errors=all_errors,
            within_bounds=False,
            habitat_boundary_id=habitat_boundary["habitat_boundary_id"],
            birth_candidate_id=habitat_boundary["birth_candidate_id"],
            adam_identity_ref=adam_ref,
            eve_identity_ref=eve_ref,
        )

    return _boundary_result(
        errors=[],
        within_bounds=True,
        habitat_boundary_id=habitat_boundary["habitat_boundary_id"],
        birth_candidate_id=habitat_boundary["birth_candidate_id"],
        adam_identity_ref=adam_ref,
        eve_identity_ref=eve_ref,
        habitat=habitat_boundary["habitat"],
        rollback_anchor=habitat_boundary["rollback_anchor"],
        observation_radius=habitat_boundary["observation_radius"],
        adam_memory_refs=adam_validated,
        eve_memory_refs=eve_validated,
    )
