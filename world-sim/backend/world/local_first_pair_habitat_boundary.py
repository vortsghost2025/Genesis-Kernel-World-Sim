"""Phase 10ID - pure in-memory first-pair habitat boundary.

Associates an authorized Phase 10IC birth candidate with a bounded habitat
declaration. Validates that identity and habitat inputs are exact, deterministic,
and within the declared observation boundary. Does not create runtime entities,
persist state, perform movement, memory writes, or external work.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.local_first_pair_birth_candidate import (
    create_first_pair_birth_candidate,
)


_HABITAT_BOUNDARY_SCHEMA_VERSION = "10ID.1"
_HABITAT_BOUNDARY_TYPE = "first_pair_habitat_boundary"
_HABITAT_BOUNDARY_SCOPE = "pure_in_memory_boundary_only"
_PAIR_ID = "genesis-first-pair"
_MIN_OBSERVATION_RADIUS = 1
_MAX_OBSERVATION_RADIUS = 1

_REQUEST_FIELDS = frozenset(
    {
        "habitat_boundary_schema_version",
        "birth_candidate",
        "authorized_declaration",
        "observation_radius",
    }
)
_IDENTITY_REF_FIELDS = frozenset(
    {
        "agent_id",
        "canonical_name",
        "canonical_agent_ref",
    }
)

_CLAIM_BOUNDARY = (
    "habitat boundary contract only; no runtime entity, movement, memory write, "
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


def _extract_identity_ref(identity: Any) -> dict[str, Any] | None:
    if type(identity) is not dict:
        return None
    if not all(field in identity for field in _IDENTITY_REF_FIELDS):
        return None
    agent_id = identity["agent_id"]
    canonical_name = identity["canonical_name"]
    canonical_agent_ref = identity["canonical_agent_ref"]
    if type(agent_id) is not str:
        return None
    if type(canonical_name) is not str:
        return None
    if type(canonical_agent_ref) is not str:
        return None
    return {
        "agent_id": agent_id,
        "canonical_name": canonical_name,
        "canonical_agent_ref": canonical_agent_ref,
    }


def _is_valid_observation_radius(value: Any) -> bool:
    if type(value) is not int:
        return False
    if isinstance(value, bool):
        return False
    return _MIN_OBSERVATION_RADIUS <= value <= _MAX_OBSERVATION_RADIUS


def _finalize_id(result: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    material = dict(result)
    material.pop(field, None)
    result[field] = prefix + _hash_canonical(material)[:32]
    return result


def _is_birth_candidate_intact(candidate: dict) -> bool:
    birth_candidate_id = candidate.get("birth_candidate_id")
    if type(birth_candidate_id) is not str or not birth_candidate_id.startswith("10IC-"):
        return False
    material = dict(candidate)
    material.pop("birth_candidate_id", None)
    expected = "10IC-" + _hash_canonical(material)[:32]
    return birth_candidate_id == expected


def create_first_pair_habitat_boundary(request: dict) -> dict[str, Any]:
    """Create a pure in-memory habitat boundary over an authorized birth candidate."""

    errors: list[str] = []

    if not _has_exact_string_keys(request, _REQUEST_FIELDS):
        return _boundary_result(
            errors=["invalid_request"],
            within_bounds=False,
        )

    schema_version = request["habitat_boundary_schema_version"]
    if (
        type(schema_version) is not str
        or schema_version != _HABITAT_BOUNDARY_SCHEMA_VERSION
    ):
        errors += ["invalid_request"]

    observation_radius = request["observation_radius"]
    radius_valid = _is_valid_observation_radius(observation_radius)
    if not radius_valid:
        errors += ["invalid_observation_radius"]

    birth_candidate = request["birth_candidate"]
    authorized_declaration = request["authorized_declaration"]

    adam_ref: dict[str, Any] | None = None
    eve_ref: dict[str, Any] | None = None
    habitat: dict[str, Any] | None = None
    rollback_anchor: dict[str, Any] | None = None
    boundary_tile_ids: list[str] = []

    if type(birth_candidate) is not dict:
        errors += ["invalid_birth_candidate"]
    elif birth_candidate.get("ok") is not True:
        errors += ["invalid_birth_candidate"]
    else:
        adam_identity = birth_candidate.get("adam_identity")
        eve_identity = birth_candidate.get("eve_identity")
        adam_ref = _extract_identity_ref(adam_identity)
        eve_ref = _extract_identity_ref(eve_identity)
        if adam_ref is None or eve_ref is None:
            errors += ["invalid_birth_candidate"]
        elif adam_ref["agent_id"] == eve_ref["agent_id"]:
            errors += ["duplicate_identity"]
        elif not _is_birth_candidate_intact(birth_candidate):
            errors += ["invalid_birth_candidate"]
        else:
            habitat = birth_candidate.get("habitat")
            rollback_anchor = birth_candidate.get("rollback_anchor")
            if not _has_exact_string_keys(
                habitat,
                {
                    "habitat_valid",
                    "habitat_schema_version",
                    "habitat_id",
                    "allowed_tile_ids",
                    "starting_tile_ids",
                    "observation_boundaries",
                    "movement_allowed",
                },
            ):
                errors += ["invalid_birth_candidate"]
                habitat = None
            elif habitat.get("habitat_valid") is not True:
                errors += ["habitat_drift"]
            elif habitat.get("movement_allowed") is not False:
                errors += ["habitat_drift"]
            else:
                if type(rollback_anchor) is not dict:
                    errors += ["invalid_birth_candidate"]
                    rollback_anchor = None
                else:
                    boundary_tile_ids = sorted(habitat["allowed_tile_ids"])

    if errors:
        return _boundary_result(
            errors=sorted(set(errors)),
            within_bounds=False,
        )

    if type(authorized_declaration) is not dict:
        errors += ["candidate_declaration_drift"]
    else:
        authorized_candidate = create_first_pair_birth_candidate(
            authorized_declaration
        )
        if authorized_candidate.get("ok") is not True:
            errors += ["invalid_birth_candidate"]
        elif authorized_candidate != birth_candidate:
            errors += ["candidate_declaration_drift"]

    if errors:
        return _boundary_result(
            errors=sorted(set(errors)),
            within_bounds=False,
        )

    assert adam_ref is not None
    assert eve_ref is not None
    assert habitat is not None
    assert rollback_anchor is not None

    return _boundary_result(
        errors=[],
        within_bounds=True,
        birth_candidate_id=birth_candidate.get("birth_candidate_id"),
        adam_identity_ref=adam_ref,
        eve_identity_ref=eve_ref,
        habitat=habitat,
        rollback_anchor=rollback_anchor,
        observation_radius=observation_radius,
        boundary_tile_ids=boundary_tile_ids,
    )


def _boundary_result(
    *,
    errors: list[str],
    within_bounds: bool,
    birth_candidate_id: str | None = None,
    adam_identity_ref: dict[str, Any] | None = None,
    eve_identity_ref: dict[str, Any] | None = None,
    habitat: dict[str, Any] | None = None,
    rollback_anchor: dict[str, Any] | None = None,
    observation_radius: int | None = None,
    boundary_tile_ids: list[str] | None = None,
) -> dict[str, Any]:
    ok = not errors
    result: dict[str, Any] = {
        "ok": ok,
        "habitat_boundary_schema_version": _HABITAT_BOUNDARY_SCHEMA_VERSION,
        "habitat_boundary_type": _HABITAT_BOUNDARY_TYPE,
        "habitat_boundary_scope": _HABITAT_BOUNDARY_SCOPE,
        "status": (
            "habitat_boundary_verified" if ok else "invalid_habitat_boundary"
        ),
        "pair_id": _PAIR_ID,
        "birth_candidate_id": birth_candidate_id,
        "adam_identity_ref": adam_identity_ref,
        "eve_identity_ref": eve_identity_ref,
        "habitat": habitat,
        "rollback_anchor": rollback_anchor,
        "observation_radius": observation_radius,
        "boundary_tile_ids": boundary_tile_ids if boundary_tile_ids is not None else [],
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
    return _finalize_id(result, "habitat_boundary_id", "10ID-")
