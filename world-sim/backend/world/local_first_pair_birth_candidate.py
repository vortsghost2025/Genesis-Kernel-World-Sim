"""Phase 10IC - pure in-memory first-pair birth candidate and heartbeat.

Defines deterministic Adam/Eve identity candidates, a bounded declared
habitat, and one caller-driven observation-only heartbeat proof. The module
does not create runtime entities, persist state, or perform external work.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.world.world_event_sanitizer import sanitize_public_text


_BIRTH_SCHEMA_VERSION = "10IC.1"
_BIRTH_TYPE = "first_pair_birth_candidate"
_BIRTH_SCOPE = "pure_in_memory_candidate_only"
_HEARTBEAT_SCHEMA_VERSION = "10IC.HB.1"
_HEARTBEAT_TYPE = "first_pair_observation_heartbeat_proof"
_HEARTBEAT_SCOPE = "observation_only_verification"
_OBSERVATION_SCHEMA_VERSION = "10IC.OBS.1"

_IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"
_ID_DERIVATION_VERSION = "sha256-full-v1"
_IDENTITY_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_IDENTITY_V1"
_PAIR_ID = "genesis-first-pair"
_HABITAT_SCHEMA_VERSION = "first_habitat.1"
_ROLLBACK_SCHEMA_VERSION = "first_rollback_anchor.1"

_IDENTITY_INPUT_FIELDS = frozenset(
    {
        "canonical_name",
        "canonical_agent_ref",
        "founding_role",
        "provenance_commitment",
    }
)
_HABITAT_INPUT_FIELDS = frozenset(
    {
        "habitat_schema_version",
        "habitat_id",
        "allowed_tile_ids",
        "starting_tile_ids",
        "observation_boundaries",
        "movement_allowed",
    }
)
_ROLLBACK_INPUT_FIELDS = frozenset(
    {
        "rollback_anchor_schema_version",
        "rollback_anchor_id",
        "habitat_id",
        "claim_scope",
        "state_commitment",
    }
)
_DECLARATION_FIELDS = frozenset(
    {
        "identity_schema_version",
        "id_derivation_version",
        "pair_id",
        "adam_identity",
        "eve_identity",
        "habitat",
        "rollback_anchor",
    }
)
_IDENTITY_OUTPUT_FIELDS = frozenset(
    {
        "identity_valid",
        "canonical_name",
        "canonical_agent_ref",
        "pair_id",
        "founding_role",
        "provenance_commitment",
        "agent_id",
    }
)
_HABITAT_OUTPUT_FIELDS = frozenset({"habitat_valid"}) | _HABITAT_INPUT_FIELDS
_ROLLBACK_OUTPUT_FIELDS = frozenset({"rollback_anchor_valid"}) | _ROLLBACK_INPUT_FIELDS
_BIRTH_OUTPUT_FIELDS = frozenset(
    {
        "ok",
        "birth_candidate_schema_version",
        "birth_candidate_type",
        "birth_candidate_scope",
        "birth_candidate_id",
        "status",
        "pair_id",
        "adam_identity",
        "eve_identity",
        "habitat",
        "rollback_anchor",
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
)
_OBSERVATION_INPUT_FIELDS = frozenset(
    {
        "observation_schema_version",
        "agent_id",
        "habitat_id",
        "rollback_anchor_id",
        "tick",
        "action",
        "claim_scope",
        "current_tile_id",
        "visible_tile_ids",
        "summary",
    }
)

_BIRTH_INERT_FLAGS = (
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
)
_HEARTBEAT_INERT_FLAGS = (
    "runtime_executed",
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
)

_SAFE_IDENTIFIER_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
)
_FORBIDDEN_IDENTIFIER_MARKERS = (
    "true_map",
    "known_map",
    "world-sim/data",
    "[redacted",
)
_MAX_TICK = (1 << 63) - 1
_BIRTH_CLAIM_BOUNDARY = (
    "caller declaration is authority; candidate ID is an integrity fingerprint "
    "only; no runtime entity, persistence, memory write, ledger write, model, "
    "provider, network, background service, or gate activity"
)
_HEARTBEAT_CLAIM_BOUNDARY = (
    "observation verification only; no creation, movement, route planning, "
    "memory write, ledger write, persistence, external call, or gate activity"
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


def _is_hex64(value: Any) -> bool:
    if type(value) is not str or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


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
    collapsed = "".join(character for character in lowered if character.isalnum())
    if ".." in value or any(
        marker in lowered for marker in _FORBIDDEN_IDENTIFIER_MARKERS
    ):
        return False
    if any(marker in collapsed for marker in ("truemap", "knownmap", "hiddensubstrate")):
        return False
    return sanitize_public_text(value) == value


def _is_artifact_id(value: Any, prefix: str) -> bool:
    if type(value) is not str or not value.startswith(prefix):
        return False
    suffix = value.removeprefix(prefix)
    return len(suffix) == 32 and all(
        character in "0123456789abcdef" for character in suffix
    )


def _plain_string_list(value: Any, *, maximum: int = 64) -> list[str] | None:
    if type(value) is not list or not 1 <= len(value) <= maximum:
        return None
    if not all(_is_safe_identifier(item) for item in value):
        return None
    if len(set(value)) != len(value):
        return None
    return sorted(value)


def _invalid_identity(expected_name: str, expected_ref: str) -> dict[str, Any]:
    return {
        "identity_valid": False,
        "canonical_name": expected_name,
        "canonical_agent_ref": expected_ref,
        "pair_id": None,
        "founding_role": None,
        "provenance_commitment": None,
        "agent_id": None,
    }


def _derive_identity(
    value: Any,
    *,
    expected_name: str,
    expected_ref: str,
    shared_identity_material_valid: bool,
) -> dict[str, Any]:
    invalid = _invalid_identity(expected_name, expected_ref)
    if not _has_exact_string_keys(value, _IDENTITY_INPUT_FIELDS):
        return invalid
    if not shared_identity_material_valid:
        return invalid
    if type(value["canonical_name"]) is not str or value["canonical_name"] != expected_name:
        return invalid
    if (
        type(value["canonical_agent_ref"]) is not str
        or value["canonical_agent_ref"] != expected_ref
    ):
        return invalid
    if type(value["founding_role"]) is not str or value["founding_role"] != "founding_agent":
        return invalid
    if not _is_hex64(value["provenance_commitment"]):
        return invalid

    material = {
        "domain_separator": _IDENTITY_DOMAIN_SEPARATOR,
        "identity_schema_version": _IDENTITY_SCHEMA_VERSION,
        "id_derivation_version": _ID_DERIVATION_VERSION,
        "canonical_name": expected_name,
        "canonical_agent_ref": expected_ref,
        "pair_id": _PAIR_ID,
        "founding_role": "founding_agent",
        "provenance_commitment": value["provenance_commitment"],
    }
    return {
        "identity_valid": True,
        "canonical_name": expected_name,
        "canonical_agent_ref": expected_ref,
        "pair_id": _PAIR_ID,
        "founding_role": "founding_agent",
        "provenance_commitment": value["provenance_commitment"],
        "agent_id": "genesis-agent-" + _hash_canonical(material),
    }


def _invalid_habitat() -> dict[str, Any]:
    return {
        "habitat_valid": False,
        "habitat_schema_version": None,
        "habitat_id": None,
        "allowed_tile_ids": [],
        "starting_tile_ids": {},
        "observation_boundaries": {},
        "movement_allowed": False,
    }


def _validate_habitat(value: Any) -> dict[str, Any]:
    invalid = _invalid_habitat()
    if not _has_exact_string_keys(value, _HABITAT_INPUT_FIELDS):
        return invalid
    if (
        type(value["habitat_schema_version"]) is not str
        or value["habitat_schema_version"] != _HABITAT_SCHEMA_VERSION
    ):
        return invalid
    if not _is_safe_identifier(value["habitat_id"]):
        return invalid
    if value["movement_allowed"] is not False:
        return invalid

    allowed_tile_ids = _plain_string_list(value["allowed_tile_ids"])
    starting_tile_ids = value["starting_tile_ids"]
    observation_boundaries = value["observation_boundaries"]
    expected_refs = {"east_adam", "east_eve"}
    if allowed_tile_ids is None:
        return invalid
    if not _has_exact_string_keys(starting_tile_ids, expected_refs):
        return invalid
    if (
        not _has_exact_string_keys(observation_boundaries, expected_refs)
    ):
        return invalid

    safe_starting: dict[str, str] = {}
    safe_boundaries: dict[str, list[str]] = {}
    allowed = set(allowed_tile_ids)
    for canonical_ref in sorted(expected_refs):
        starting_tile_id = starting_tile_ids[canonical_ref]
        boundary = _plain_string_list(observation_boundaries[canonical_ref])
        if not _is_safe_identifier(starting_tile_id):
            return invalid
        if starting_tile_id not in allowed or boundary is None:
            return invalid
        if not set(boundary).issubset(allowed) or starting_tile_id not in boundary:
            return invalid
        safe_starting[canonical_ref] = starting_tile_id
        safe_boundaries[canonical_ref] = boundary

    return {
        "habitat_valid": True,
        "habitat_schema_version": _HABITAT_SCHEMA_VERSION,
        "habitat_id": value["habitat_id"],
        "allowed_tile_ids": allowed_tile_ids,
        "starting_tile_ids": safe_starting,
        "observation_boundaries": safe_boundaries,
        "movement_allowed": False,
    }


def _invalid_rollback_anchor() -> dict[str, Any]:
    return {
        "rollback_anchor_valid": False,
        "rollback_anchor_schema_version": None,
        "rollback_anchor_id": None,
        "habitat_id": None,
        "claim_scope": None,
        "state_commitment": None,
    }


def _validate_rollback_anchor(value: Any, habitat_id: str | None) -> dict[str, Any]:
    invalid = _invalid_rollback_anchor()
    if not _has_exact_string_keys(value, _ROLLBACK_INPUT_FIELDS):
        return invalid
    if (
        type(value["rollback_anchor_schema_version"]) is not str
        or value["rollback_anchor_schema_version"] != _ROLLBACK_SCHEMA_VERSION
    ):
        return invalid
    if not _is_safe_identifier(value["rollback_anchor_id"]):
        return invalid
    if not _is_safe_identifier(value["habitat_id"]):
        return invalid
    if not _is_safe_identifier(habitat_id) or value["habitat_id"] != habitat_id:
        return invalid
    if type(value["claim_scope"]) is not str or value["claim_scope"] != "operator_proof":
        return invalid
    if not _is_hex64(value["state_commitment"]):
        return invalid
    return {
        "rollback_anchor_valid": True,
        "rollback_anchor_schema_version": _ROLLBACK_SCHEMA_VERSION,
        "rollback_anchor_id": value["rollback_anchor_id"],
        "habitat_id": habitat_id,
        "claim_scope": "operator_proof",
        "state_commitment": value["state_commitment"],
    }


def _finalize_id(result: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    material = dict(result)
    material.pop(field, None)
    result[field] = prefix + _hash_canonical(material)[:32]
    return result


def create_first_pair_birth_candidate(declaration: dict) -> dict[str, Any]:
    """Create a deterministic, inert Adam/Eve birth candidate in memory."""

    exact_declaration = _has_exact_string_keys(declaration, _DECLARATION_FIELDS)
    source = declaration if exact_declaration else {}
    identity_schema_version = source.get("identity_schema_version")
    id_derivation_version = source.get("id_derivation_version")
    pair_id = source.get("pair_id")
    shared_identity_material_valid = (
        type(identity_schema_version) is str
        and identity_schema_version == _IDENTITY_SCHEMA_VERSION
        and type(id_derivation_version) is str
        and id_derivation_version == _ID_DERIVATION_VERSION
        and type(pair_id) is str
        and pair_id == _PAIR_ID
    )

    adam_identity = _derive_identity(
        source.get("adam_identity"),
        expected_name="Adam",
        expected_ref="east_adam",
        shared_identity_material_valid=shared_identity_material_valid,
    )
    eve_identity = _derive_identity(
        source.get("eve_identity"),
        expected_name="Eve",
        expected_ref="east_eve",
        shared_identity_material_valid=shared_identity_material_valid,
    )
    habitat = _validate_habitat(source.get("habitat"))
    rollback_anchor = _validate_rollback_anchor(
        source.get("rollback_anchor"),
        habitat["habitat_id"] if habitat["habitat_valid"] else None,
    )

    errors: list[str] = []
    if not exact_declaration:
        errors += ["invalid_birth_declaration"]
    if not adam_identity["identity_valid"]:
        errors += ["adam_identity_drift"]
    if not eve_identity["identity_valid"]:
        errors += ["eve_identity_drift"]
    if not habitat["habitat_valid"]:
        errors += ["habitat_drift"]
    if not rollback_anchor["rollback_anchor_valid"]:
        errors += ["invalid_rollback_anchor"]

    ok = not errors
    result: dict[str, Any] = {
        "ok": ok,
        "birth_candidate_schema_version": _BIRTH_SCHEMA_VERSION,
        "birth_candidate_type": _BIRTH_TYPE,
        "birth_candidate_scope": _BIRTH_SCOPE,
        "status": (
            "ready_for_observation_verification" if ok else "invalid_birth_candidate"
        ),
        "pair_id": _PAIR_ID,
        "adam_identity": adam_identity,
        "eve_identity": eve_identity,
        "habitat": habitat,
        "rollback_anchor": rollback_anchor,
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
        "claim_boundary": _BIRTH_CLAIM_BOUNDARY,
        "errors": errors,
    }
    return _finalize_id(result, "birth_candidate_id", "10IC-")


def _identity_output_is_valid(
    value: Any,
    *,
    expected_name: str,
    expected_ref: str,
) -> bool:
    if not _has_exact_string_keys(value, _IDENTITY_OUTPUT_FIELDS):
        return False
    if value["identity_valid"] is not True:
        return False
    if type(value["canonical_name"]) is not str or value["canonical_name"] != expected_name:
        return False
    if (
        type(value["canonical_agent_ref"]) is not str
        or value["canonical_agent_ref"] != expected_ref
    ):
        return False
    if type(value["pair_id"]) is not str or value["pair_id"] != _PAIR_ID:
        return False
    if type(value["founding_role"]) is not str or value["founding_role"] != "founding_agent":
        return False
    if not _is_hex64(value["provenance_commitment"]):
        return False
    derived = _derive_identity(
        {
            "canonical_name": expected_name,
            "canonical_agent_ref": expected_ref,
            "founding_role": "founding_agent",
            "provenance_commitment": value["provenance_commitment"],
        },
        expected_name=expected_name,
        expected_ref=expected_ref,
        shared_identity_material_valid=True,
    )
    return value == derived


def _habitat_output_is_valid(value: Any) -> bool:
    if not _has_exact_string_keys(value, _HABITAT_OUTPUT_FIELDS):
        return False
    if value["habitat_valid"] is not True:
        return False
    source = {field: value[field] for field in _HABITAT_INPUT_FIELDS}
    return _validate_habitat(source) == value


def _rollback_output_is_valid(value: Any, habitat_id: str) -> bool:
    if not _has_exact_string_keys(value, _ROLLBACK_OUTPUT_FIELDS):
        return False
    if value["rollback_anchor_valid"] is not True:
        return False
    source = {field: value[field] for field in _ROLLBACK_INPUT_FIELDS}
    return _validate_rollback_anchor(source, habitat_id) == value


def _birth_candidate_is_valid(value: Any) -> bool:
    if not _has_exact_string_keys(value, _BIRTH_OUTPUT_FIELDS):
        return False
    if value["ok"] is not True:
        return False
    if type(value["status"]) is not str or value["status"] != "ready_for_observation_verification":
        return False
    if (
        type(value["birth_candidate_schema_version"]) is not str
        or value["birth_candidate_schema_version"] != _BIRTH_SCHEMA_VERSION
    ):
        return False
    if type(value["birth_candidate_type"]) is not str or value["birth_candidate_type"] != _BIRTH_TYPE:
        return False
    if type(value["birth_candidate_scope"]) is not str or value["birth_candidate_scope"] != _BIRTH_SCOPE:
        return False
    if type(value["pair_id"]) is not str or value["pair_id"] != _PAIR_ID:
        return False
    if not _is_artifact_id(value["birth_candidate_id"], "10IC-"):
        return False
    if type(value["claim_boundary"]) is not str or value["claim_boundary"] != _BIRTH_CLAIM_BOUNDARY:
        return False
    if type(value["errors"]) is not list or value["errors"] != []:
        return False
    if not all(value[field] is False for field in _BIRTH_INERT_FLAGS):
        return False
    if not _identity_output_is_valid(
        value["adam_identity"],
        expected_name="Adam",
        expected_ref="east_adam",
    ):
        return False
    if not _identity_output_is_valid(
        value["eve_identity"],
        expected_name="Eve",
        expected_ref="east_eve",
    ):
        return False
    if not _habitat_output_is_valid(value["habitat"]):
        return False
    if not _rollback_output_is_valid(
        value["rollback_anchor"],
        value["habitat"]["habitat_id"],
    ):
        return False

    declaration = {
        "identity_schema_version": _IDENTITY_SCHEMA_VERSION,
        "id_derivation_version": _ID_DERIVATION_VERSION,
        "pair_id": _PAIR_ID,
        "adam_identity": {
            field: value["adam_identity"][field] for field in _IDENTITY_INPUT_FIELDS
        },
        "eve_identity": {
            field: value["eve_identity"][field] for field in _IDENTITY_INPUT_FIELDS
        },
        "habitat": {
            field: value["habitat"][field] for field in _HABITAT_INPUT_FIELDS
        },
        "rollback_anchor": {
            field: value["rollback_anchor"][field]
            for field in _ROLLBACK_INPUT_FIELDS
        },
    }
    return create_first_pair_birth_candidate(declaration) == value


def _contains_hidden_substrate_marker(value: str) -> bool:
    collapsed = "".join(
        character for character in value.casefold() if character.isalnum()
    )
    return any(
        marker in collapsed for marker in ("truemap", "knownmap", "hiddensubstrate")
    )


def _contains_private_path_marker(value: str) -> bool:
    lowered = value.casefold()
    return "/" in value or "%2f" in lowered or "%5c" in lowered


def _is_bounded_public_text(value: Any, *, maximum: int) -> bool:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        return False
    return all(0x20 <= ord(character) <= 0x7E for character in value)


def _sanitize_summary(value: str) -> str:
    token_sanitized = " ".join(
        sanitize_public_text(token) for token in value.split(" ")
    )
    return sanitize_public_text(token_sanitized)


def _heartbeat_result(
    *,
    errors: list[str],
    birth_candidate_id: str | None = None,
    agent_id: str | None = None,
    canonical_agent_ref: str | None = None,
    habitat_id: str | None = None,
    rollback_anchor_id: str | None = None,
    tick: int | None = None,
    action: str | None = None,
    claim_scope: str | None = None,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok = not errors
    result: dict[str, Any] = {
        "ok": ok,
        "heartbeat_schema_version": _HEARTBEAT_SCHEMA_VERSION,
        "heartbeat_type": _HEARTBEAT_TYPE,
        "heartbeat_scope": _HEARTBEAT_SCOPE,
        "status": "verified_observation_only" if ok else "rejected",
        "birth_candidate_id": birth_candidate_id,
        "agent_id": agent_id if ok else None,
        "canonical_agent_ref": canonical_agent_ref if ok else None,
        "habitat_id": habitat_id if ok else None,
        "rollback_anchor_id": rollback_anchor_id if ok else None,
        "tick": tick if ok else None,
        "action": action if ok else None,
        "claim_scope": claim_scope if ok else None,
        "observation": (
            observation
            if ok and observation is not None
            else {"current_tile_id": None, "visible_tile_ids": [], "summary": None}
        ),
        "heartbeat_verified": ok,
        "runtime_executed": False,
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
        "claim_boundary": _HEARTBEAT_CLAIM_BOUNDARY,
        "errors": errors,
    }
    return _finalize_id(result, "heartbeat_proof_id", "10IC-HB-")


def verify_first_pair_observation_heartbeat(
    birth_candidate: dict,
    observation: dict,
    authorized_declaration: dict,
) -> dict[str, Any]:
    """Verify one observation against the caller-authorized declaration."""

    if not _birth_candidate_is_valid(birth_candidate):
        return _heartbeat_result(errors=["invalid_birth_candidate"])
    authorized_candidate = create_first_pair_birth_candidate(authorized_declaration)
    if authorized_candidate["ok"] is not True or authorized_candidate != birth_candidate:
        return _heartbeat_result(errors=["invalid_birth_candidate"])
    birth_candidate_id = birth_candidate["birth_candidate_id"]
    if not _has_exact_string_keys(observation, _OBSERVATION_INPUT_FIELDS):
        return _heartbeat_result(
            errors=["invalid_observation"],
            birth_candidate_id=birth_candidate_id,
        )

    tick = observation["tick"]
    visible_tile_ids = _plain_string_list(observation["visible_tile_ids"])
    summary = observation["summary"]
    sanitized_summary: str | None = None
    errors: list[str] = []
    if (
        type(observation["observation_schema_version"]) is not str
        or observation["observation_schema_version"] != _OBSERVATION_SCHEMA_VERSION
    ):
        errors += ["invalid_observation"]
    if type(tick) is not int or not 0 <= tick <= _MAX_TICK:
        errors += ["invalid_observation"]
    if type(observation["action"]) is not str or observation["action"] != "observe":
        errors += ["invalid_observation"]
    if (
        type(observation["claim_scope"]) is not str
        or observation["claim_scope"] != "observed"
    ):
        errors += ["invalid_observation"]
    if not _is_safe_identifier(observation["agent_id"]):
        errors += ["invalid_observation"]
    if not _is_safe_identifier(observation["habitat_id"]):
        errors += ["invalid_observation"]
    if not _is_safe_identifier(observation["rollback_anchor_id"]):
        errors += ["invalid_observation"]
    if not _is_safe_identifier(observation["current_tile_id"]):
        errors += ["invalid_observation"]
    if visible_tile_ids is None:
        errors += ["invalid_observation"]
    if not _is_bounded_public_text(summary, maximum=512):
        errors += ["invalid_observation"]
    elif _contains_hidden_substrate_marker(summary):
        errors += ["hidden_substrate_leakage"]
    elif _contains_private_path_marker(summary):
        errors += ["private_path_leakage"]
    else:
        sanitized_summary = _sanitize_summary(summary)
        if "/" in sanitized_summary or "\\" in sanitized_summary:
            errors += ["private_path_leakage"]
    if errors:
        return _heartbeat_result(
            errors=sorted(set(errors)),
            birth_candidate_id=birth_candidate_id,
        )

    identity = None
    for member in (birth_candidate["adam_identity"], birth_candidate["eve_identity"]):
        if member["agent_id"] == observation["agent_id"]:
            identity = member
    if identity is None:
        return _heartbeat_result(
            errors=["identity_drift"],
            birth_candidate_id=birth_candidate_id,
        )

    habitat = birth_candidate["habitat"]
    rollback_anchor = birth_candidate["rollback_anchor"]
    canonical_ref = identity["canonical_agent_ref"]
    boundary = habitat["observation_boundaries"][canonical_ref]
    starting_tile_id = habitat["starting_tile_ids"][canonical_ref]
    if observation["habitat_id"] != habitat["habitat_id"]:
        errors += ["habitat_drift"]
    if observation["rollback_anchor_id"] != rollback_anchor["rollback_anchor_id"]:
        errors += ["missing_rollback_anchor"]
    if observation["current_tile_id"] != starting_tile_id:
        errors += ["habitat_drift"]
    if visible_tile_ids is None or not set(visible_tile_ids).issubset(set(boundary)):
        errors += ["habitat_drift"]
    if errors:
        return _heartbeat_result(
            errors=sorted(set(errors)),
            birth_candidate_id=birth_candidate_id,
        )

    public_observation = {
        "current_tile_id": observation["current_tile_id"],
        "visible_tile_ids": visible_tile_ids,
        "summary": sanitized_summary,
    }
    return _heartbeat_result(
        errors=[],
        birth_candidate_id=birth_candidate_id,
        agent_id=identity["agent_id"],
        canonical_agent_ref=canonical_ref,
        habitat_id=habitat["habitat_id"],
        rollback_anchor_id=rollback_anchor["rollback_anchor_id"],
        tick=tick,
        action="observe",
        claim_scope="observed",
        observation=public_observation,
    )
