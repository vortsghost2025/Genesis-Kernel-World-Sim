"""Phase 10IE - pure first-pair memory boundary tests.

Tests that a verified 10ID habitat boundary can be associated with separate
Adam and Eve memory-reference lists, where each list is agent-scoped, only
explicitly public references may cross identities, private references are
rejected when they belong to the other identity, and the complete boundary
fails closed when either side is invalid.

Strict TDD: this test file is written first and must fail (RED) before the
module exists.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

MODULE_NAME = "backend.world.local_first_pair_memory_boundary"
MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_first_pair_memory_boundary.py"
)

BIRTH_MODULE_NAME = "backend.world.local_first_pair_birth_candidate"
HABITAT_MODULE_NAME = "backend.world.local_first_pair_habitat_boundary"

MEMORY_BOUNDARY_SCHEMA_VERSION = "10IE.1"
MEMORY_BOUNDARY_TYPE = "first_pair_memory_boundary"
MEMORY_BOUNDARY_SCOPE = "pure_in_memory_boundary_only"

IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"
ID_DERIVATION_VERSION = "sha256-full-v1"
PAIR_ID = "genesis-first-pair"
HABITAT_ID = "genesis-first-habitat"
ROLLBACK_ANCHOR_ID = "genesis-first-pair-anchor"

MEMORY_BOUNDARY_OUTPUT_FIELDS = {
    "ok",
    "memory_boundary_schema_version",
    "memory_boundary_type",
    "memory_boundary_scope",
    "memory_boundary_id",
    "status",
    "pair_id",
    "habitat_boundary_id",
    "birth_candidate_id",
    "adam_identity_ref",
    "eve_identity_ref",
    "habitat",
    "rollback_anchor",
    "observation_radius",
    "adam_memory_refs",
    "eve_memory_refs",
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

INERT_FLAGS = {
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
}

IDENTITY_REF_FIELDS = {
    "agent_id",
    "canonical_name",
    "canonical_agent_ref",
}

MEMORY_REF_FIELDS = {
    "ref_id",
    "owner_agent_id",
    "ref_type",
    "is_public",
}

VALID_REF_TYPES = {
    "public_observation",
    "public_evidence",
    "identity_provenance",
    "habitat_boundary",
    "rollback_anchor",
}


def _module():
    import importlib

    return importlib.import_module(MODULE_NAME)


def _birth_module():
    import importlib

    return importlib.import_module(BIRTH_MODULE_NAME)


def _habitat_module():
    import importlib

    return importlib.import_module(HABITAT_MODULE_NAME)


def _valid_declaration() -> dict:
    return {
        "identity_schema_version": IDENTITY_SCHEMA_VERSION,
        "id_derivation_version": ID_DERIVATION_VERSION,
        "pair_id": PAIR_ID,
        "adam_identity": {
            "canonical_name": "Adam",
            "canonical_agent_ref": "east_adam",
            "founding_role": "founding_agent",
            "provenance_commitment": "a" * 64,
        },
        "eve_identity": {
            "canonical_name": "Eve",
            "canonical_agent_ref": "east_eve",
            "founding_role": "founding_agent",
            "provenance_commitment": "b" * 64,
        },
        "habitat": {
            "habitat_schema_version": "first_habitat.1",
            "habitat_id": HABITAT_ID,
            "allowed_tile_ids": ["public-start-adam", "public-start-eve"],
            "starting_tile_ids": {
                "east_adam": "public-start-adam",
                "east_eve": "public-start-eve",
            },
            "observation_boundaries": {
                "east_adam": ["public-start-adam"],
                "east_eve": ["public-start-eve"],
            },
            "movement_allowed": False,
        },
        "rollback_anchor": {
            "rollback_anchor_schema_version": "first_rollback_anchor.1",
            "rollback_anchor_id": ROLLBACK_ANCHOR_ID,
            "habitat_id": HABITAT_ID,
            "claim_scope": "operator_proof",
            "state_commitment": "c" * 64,
        },
    }


def _create_candidate(declaration: dict | None = None) -> dict:
    return _birth_module().create_first_pair_birth_candidate(
        declaration if declaration is not None else _valid_declaration()
    )


def _valid_habitat_boundary_request(candidate: dict | None = None) -> dict:
    if candidate is None:
        candidate = _create_candidate()
    declaration = _valid_declaration()
    return {
        "habitat_boundary_schema_version": "10ID.1",
        "birth_candidate": candidate,
        "authorized_declaration": declaration,
        "observation_radius": 1,
    }


def _create_habitat_boundary(request: dict | None = None) -> dict:
    if request is None:
        request = _valid_habitat_boundary_request()
    return _habitat_module().create_first_pair_habitat_boundary(request)


def _adam_agent_id() -> str:
    return _create_candidate()["adam_identity"]["agent_id"]


def _eve_agent_id() -> str:
    return _create_candidate()["eve_identity"]["agent_id"]


def _valid_memory_boundary_request(
    habitat_boundary: dict | None = None,
    adam_memory_refs: list | None = None,
    eve_memory_refs: list | None = None,
) -> dict:
    if habitat_boundary is None:
        habitat_boundary = _create_habitat_boundary()
    return {
        "memory_boundary_schema_version": MEMORY_BOUNDARY_SCHEMA_VERSION,
        "habitat_boundary": habitat_boundary,
        "authorized_declaration": _valid_declaration(),
        "adam_memory_refs": (
            adam_memory_refs if adam_memory_refs is not None else []
        ),
        "eve_memory_refs": (
            eve_memory_refs if eve_memory_refs is not None else []
        ),
    }


def _create_memory_boundary(request: dict | None = None) -> dict:
    if request is None:
        request = _valid_memory_boundary_request()
    return _module().create_first_pair_memory_boundary(request)


def _assert_inert(result: dict) -> None:
    for field in INERT_FLAGS:
        assert result[field] is False, f"{field} should be False"


def _own_ref(agent_id: str, ref_type: str = "public_observation") -> dict:
    return {
        "ref_id": "10K-abcdef0123456789abcdef0123456789",
        "owner_agent_id": agent_id,
        "ref_type": ref_type,
        "is_public": True,
    }


def _own_private_ref(agent_id: str, ref_type: str = "public_observation") -> dict:
    return {
        "ref_id": "10K-0123456789abcdef0123456789abcdef",
        "owner_agent_id": agent_id,
        "ref_type": ref_type,
        "is_public": False,
    }


class _EqualString(str):
    pass


class _EqualInt(int):
    pass


class _EqualDict(dict):
    pass


class _EqualList(list):
    pass


class _EqualBool(int):
    pass


# === Phase 1: module existence ===


def test_phase10ie_module_exists_before_import():
    assert MODULE_PATH.is_file()


# === Phase 2: empty initial memory ===


def test_valid_empty_memory_lists_for_both_agents():
    request = _valid_memory_boundary_request(adam_memory_refs=[], eve_memory_refs=[])
    original = copy.deepcopy(request)

    result = _create_memory_boundary(request)

    assert request == original
    assert result["ok"] is True
    assert result["status"] == "memory_boundary_verified"
    assert result["adam_memory_refs"] == []
    assert result["eve_memory_refs"] == []
    assert result["within_bounds"] is True
    _assert_inert(result)


# === Phase 3: deterministic output and ID ===


def test_memory_boundary_is_deterministic_and_id_commits_to_envelope():
    request = _valid_memory_boundary_request()
    first = _create_memory_boundary(request)
    second = _create_memory_boundary(copy.deepcopy(request))

    assert first == second
    assert first["memory_boundary_id"].startswith("10IE-")

    material = dict(first)
    material.pop("memory_boundary_id")
    canonical = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    import hashlib

    expected = "10IE-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    assert first["memory_boundary_id"] == expected


def test_memory_boundary_id_changes_when_refs_change():
    adam_id = _adam_agent_id()
    base = _valid_memory_boundary_request()
    base_result = _create_memory_boundary(base)

    request_with_ref = _valid_memory_boundary_request(
        adam_memory_refs=[_own_ref(adam_id)]
    )
    ref_result = _create_memory_boundary(request_with_ref)

    assert base_result["memory_boundary_id"] != ref_result["memory_boundary_id"]


# === Phase 4: exact output envelope ===


def test_output_has_exact_field_set():
    result = _create_memory_boundary()
    assert set(result) == MEMORY_BOUNDARY_OUTPUT_FIELDS
    assert result["memory_boundary_schema_version"] == MEMORY_BOUNDARY_SCHEMA_VERSION
    assert result["memory_boundary_type"] == MEMORY_BOUNDARY_TYPE
    assert result["memory_boundary_scope"] == MEMORY_BOUNDARY_SCOPE
    assert result["pair_id"] == PAIR_ID
    assert result["errors"] == []


# === Phase 5: identity ref preservation from 10ID ===


def test_preserves_adam_and_eve_identity_refs_from_habitat_boundary():
    habitat_boundary = _create_habitat_boundary()
    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["adam_identity_ref"] == habitat_boundary["adam_identity_ref"]
    assert result["eve_identity_ref"] == habitat_boundary["eve_identity_ref"]
    assert set(result["adam_identity_ref"]) == IDENTITY_REF_FIELDS
    assert set(result["eve_identity_ref"]) == IDENTITY_REF_FIELDS


def test_preserves_habitat_boundary_id_and_birth_candidate_id():
    habitat_boundary = _create_habitat_boundary()
    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["habitat_boundary_id"] == habitat_boundary["habitat_boundary_id"]
    assert (
        result["birth_candidate_id"] == habitat_boundary["birth_candidate_id"]
    )


def test_preserves_habitat_and_rollback_anchor_from_habitat_boundary():
    habitat_boundary = _create_habitat_boundary()
    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["habitat"] == habitat_boundary["habitat"]
    assert result["rollback_anchor"] == habitat_boundary["rollback_anchor"]
    assert result["observation_radius"] == habitat_boundary["observation_radius"]


# === Phase 6: valid own private references ===


def test_adam_can_hold_own_private_reference():
    adam_id = _adam_agent_id()
    ref = _own_private_ref(adam_id)
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["adam_memory_refs"] == [ref]
    assert result["eve_memory_refs"] == []


def test_eve_can_hold_own_private_reference():
    eve_id = _eve_agent_id()
    ref = _own_private_ref(eve_id)
    request = _valid_memory_boundary_request(eve_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["eve_memory_refs"] == [ref]
    assert result["adam_memory_refs"] == []


def test_adam_can_hold_own_public_reference():
    adam_id = _adam_agent_id()
    ref = _own_ref(adam_id, "public_evidence")
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["adam_memory_refs"] == [ref]


# === Phase 7: valid explicitly public cross-identity references ===


def test_eve_can_hold_adam_public_reference():
    adam_id = _adam_agent_id()
    ref = _own_ref(adam_id, "public_observation")
    request = _valid_memory_boundary_request(eve_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["eve_memory_refs"] == [ref]


def test_adam_can_hold_eve_public_reference():
    eve_id = _eve_agent_id()
    ref = _own_ref(eve_id, "identity_provenance")
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["adam_memory_refs"] == [ref]


# === Phase 8: reject cross-identity private memory ===


def test_adam_receives_eve_private_memory_rejected():
    eve_id = _eve_agent_id()
    ref = _own_private_ref(eve_id)
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]
    _assert_inert(result)


def test_eve_receives_adam_private_memory_rejected():
    adam_id = _adam_agent_id()
    ref = _own_private_ref(adam_id)
    request = _valid_memory_boundary_request(eve_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]
    _assert_inert(result)


# === Phase 9: ownership mismatch ===


def test_ownership_mismatch_unknown_owner_agent_id_rejected():
    ref = {
        "ref_id": "10K-ffffffffffffffffffffffffffffffff",
        "owner_agent_id": "genesis-agent-unknownnotreal",
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]
    _assert_inert(result)


def test_ownership_mismatch_adam_ref_with_eve_owner_on_adam_side():
    eve_id = _eve_agent_id()
    ref = _own_private_ref(eve_id)
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]


# === Phase 10: public/private classification mismatch ===


def test_eve_private_ref_marked_public_still_crosses_to_adam():
    """A private ref with is_public=True is treated as public and allowed to cross."""
    eve_id = _eve_agent_id()
    ref = {
        "ref_id": "10K-11111111111111111111111111111111",
        "owner_agent_id": eve_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["adam_memory_refs"] == [ref]


def test_adam_public_ref_marked_private_cannot_cross_to_eve():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-22222222222222222222222222222222",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": False,
    }
    request = _valid_memory_boundary_request(eve_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]


# === Phase 11: tampered 10ID envelope ===


def test_tampered_habitat_boundary_id_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["habitat_boundary_id"] = "10ID-tampered00000000000000000000"

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]
    _assert_inert(result)


def test_habitat_boundary_ok_false_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["ok"] = False

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


def test_habitat_boundary_missing_identity_ref_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["adam_identity_ref"] = None

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


def test_habitat_boundary_status_not_verified_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["status"] = "invalid_habitat_boundary"

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


# === Phase 12: wrong 10ID boundary ID ===


def test_wrong_habitat_boundary_schema_version_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["habitat_boundary_schema_version"] = "10ID.999"

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


def test_habitat_boundary_non_dict_rejected():
    request = _valid_memory_boundary_request()
    request["habitat_boundary"] = "not a dict"

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


# === Phase 13: mismatched authorized declaration ===


def test_mismatched_authorized_declaration_rejected():
    habitat_boundary = _create_habitat_boundary()
    wrong_declaration = _valid_declaration()
    wrong_declaration["habitat"]["habitat_id"] = "different-habitat-id"

    request = _valid_memory_boundary_request(habitat_boundary)
    request["authorized_declaration"] = wrong_declaration

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "candidate_declaration_drift" in result["errors"]
    _assert_inert(result)


def test_non_dict_authorized_declaration_rejected():
    request = _valid_memory_boundary_request()
    request["authorized_declaration"] = "not a dict"

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_request" in result["errors"] or (
        "candidate_declaration_drift" in result["errors"]
    )


# === Phase 14: invalid identity refs ===


def test_adam_identity_ref_agent_id_does_not_match_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["adam_identity_ref"]["agent_id"] = "genesis-agent-wrong"

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


def test_eve_identity_ref_agent_id_does_not_match_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["eve_identity_ref"]["agent_id"] = "genesis-agent-wrong"

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


# === Phase 15: duplicate identity refs ===


def test_duplicate_identity_refs_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["eve_identity_ref"]["agent_id"] = (
        habitat_boundary["adam_identity_ref"]["agent_id"]
    )

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


# === Phase 16: unknown and missing fields ===


def test_unknown_request_field_rejected():
    request = _valid_memory_boundary_request()
    request["true_map"] = {"hidden": "substrate"}

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


def test_missing_request_field_rejected():
    request = _valid_memory_boundary_request()
    del request["adam_memory_refs"]

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert result["errors"]


def test_extra_request_field_rejected():
    request = _valid_memory_boundary_request()
    request["extra_field"] = "forbidden"

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert result["errors"]


# === Phase 17: wrong schema versions ===


def test_wrong_memory_boundary_schema_version_rejected():
    request = _valid_memory_boundary_request()
    request["memory_boundary_schema_version"] = "10IE.999"

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert result["errors"]


# === Phase 18: non-dict request ===


def test_non_dict_request_rejected():
    result = _create_memory_boundary(request="not a dict")  # type: ignore

    assert result["ok"] is False
    assert result["errors"]


def test_non_dict_request_list_rejected():
    result = _create_memory_boundary(request=[])  # type: ignore

    assert result["ok"] is False
    assert result["errors"]


# === Phase 19: non-list memory refs ===


def test_non_list_adam_memory_refs_rejected():
    request = _valid_memory_boundary_request()
    request["adam_memory_refs"] = "not a list"

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_non_list_eve_memory_refs_rejected():
    request = _valid_memory_boundary_request()
    request["eve_memory_refs"] = {"not": "a list"}

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


# === Phase 20: malformed event/public refs ===


def test_memory_ref_missing_fields_rejected():
    ref = {"ref_id": "10K-aaaa", "owner_agent_id": _adam_agent_id()}
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_memory_ref_extra_fields_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-aaaa",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
        "extra_field": "forbidden",
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_memory_ref_invalid_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_memory_ref_invalid_ref_type_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-test",
        "owner_agent_id": adam_id,
        "ref_type": "forbidden_type",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_memory_ref_non_string_owner_agent_id_rejected():
    ref = {
        "ref_id": "10K-test",
        "owner_agent_id": 12345,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_memory_ref_is_public_not_bool_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-test",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": "true",
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


# === Phase 21: exact-type and subclass rejection ===


def test_string_subclass_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": _EqualString("10K-test"),
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_dict_subclass_in_memory_ref_rejected():
    adam_id = _adam_agent_id()
    ref = _EqualString(
        "10K-test"
    )
    request = _valid_memory_boundary_request(
        adam_memory_refs=[
            ref  # type: ignore  # string, not dict
        ]
    )

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_list_subclass_in_memory_refs_rejected():
    adam_id = _adam_agent_id()
    ref = _own_ref(adam_id)
    refs = _EqualList([ref])
    request = _valid_memory_boundary_request(adam_memory_refs=refs)

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_memory_ref" in result["errors"]


def test_string_subclass_in_request_key_rejected():
    request = _valid_memory_boundary_request()
    tampered = {}
    for key, value in request.items():
        tampered[_EqualString(key)] = value
    result = _create_memory_boundary(tampered)

    assert result["ok"] is False
    assert result["errors"]


# === Phase 22: bool-as-int rejection (observation_radius) ===


def test_bool_as_int_observation_radius_in_habitat_boundary_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["observation_radius"] = True

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]


# === Phase 23: no partial success ===


def test_adam_fails_eve_succeeds_still_returns_ok_false():
    eve_id = _eve_agent_id()
    adam_id = _adam_agent_id()
    adam_bad_ref = _own_private_ref(eve_id)
    eve_good_ref = _own_ref(eve_id, "public_evidence")

    request = _valid_memory_boundary_request(
        adam_memory_refs=[adam_bad_ref],
        eve_memory_refs=[eve_good_ref],
    )

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]
    assert result["adam_memory_refs"] == []
    assert result["eve_memory_refs"] == []
    _assert_inert(result)


def test_eve_fails_adam_succeeds_still_returns_ok_false():
    eve_id = _eve_agent_id()
    adam_id = _adam_agent_id()
    adam_good_ref = _own_ref(adam_id, "public_evidence")
    eve_bad_ref = _own_private_ref(adam_id)

    request = _valid_memory_boundary_request(
        adam_memory_refs=[adam_good_ref],
        eve_memory_refs=[eve_bad_ref],
    )

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "cross_agent_memory_leak" in result["errors"]
    assert result["adam_memory_refs"] == []
    assert result["eve_memory_refs"] == []


# === Phase 24: all inert flags hard-coded False ===


def test_all_inert_flags_are_false_on_success():
    result = _create_memory_boundary()
    _assert_inert(result)


def test_all_inert_flags_are_false_on_failure():
    request = _valid_memory_boundary_request()
    request["memory_boundary_schema_version"] = "WRONG"

    result = _create_memory_boundary(request)

    _assert_inert(result)


# === Phase 25: input immutability ===


def test_input_not_mutated_after_call():
    request = _valid_memory_boundary_request(
        adam_memory_refs=[_own_ref(_adam_agent_id())]
    )
    original = copy.deepcopy(request)

    _create_memory_boundary(request)

    assert request == original


# === Phase 26: output detachment from input mutation ===


def test_output_detached_from_input_mutation():
    request = _valid_memory_boundary_request(
        adam_memory_refs=[_own_ref(_adam_agent_id())]
    )

    result = _create_memory_boundary(request)
    request["adam_memory_refs"][0]["ref_id"] = "10K-mutated"

    assert result["adam_memory_refs"][0]["ref_id"] != "10K-mutated"


# === Phase 27: claim boundary text ===


def test_claim_boundary_does_not_authorize_runtime():
    result = _create_memory_boundary()

    assert "memory boundary" in result["claim_boundary"]
    assert "no runtime" in result["claim_boundary"]


# === Phase 28: hidden-substrate / private-path leakage rejection ===


def test_hidden_substrate_marker_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-true_map-hidden",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "hidden_substrate_leakage" in result["errors"]


def test_private_path_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-/etc/passwd",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "private_path_leakage" in result["errors"]


def test_no_hidden_substrate_leakage_in_output():
    result = _create_memory_boundary()
    serialized = json.dumps(result, sort_keys=True)

    assert "true_map" not in serialized.lower()
    assert "known_map" not in serialized.lower()
    assert "hidden_substrate" not in serialized.lower()


# === Phase 29: source-level import audit ===


def test_module_has_only_safe_imports():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_modules = {
        "__future__",
        "hashlib",
        "json",
        "typing",
        "backend.world.local_first_pair_birth_candidate",
        "backend.world.local_first_pair_habitat_boundary",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_modules, (
                    f"forbidden import: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") in allowed_modules, (
                f"forbidden import: {node.module}"
            )


def test_module_does_not_import_forbidden_modules():
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        "backend.memory",
        "persistent_memory",
        "event_log",
        "dual_sim",
        "10hd",
        "world_event_ledger",
        "local_runtime_adapter_inert_ledger_writer",
        "import os",
        "import shutil",
        "import subprocess",
        "import socket",
        "import requests",
        "import urllib",
        "import asyncio",
        "import threading",
        "import multiprocessing",
        "import sqlite3",
        "import pickle",
        "import pathlib",
        "from pathlib",
        "environ",
    )
    for token in forbidden:
        assert token not in source, f"forbidden token: {token}"


# === Phase 30: source-level forbidden-call audit ===


def test_module_has_no_file_runtime_provider_model_or_network_calls():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_calls = {
        "open",
        "read",
        "write",
        "read_text",
        "write_text",
        "read_bytes",
        "write_bytes",
        "mkdir",
        "makedirs",
        "rmdir",
        "unlink",
        "remove",
        "rename",
        "replace",
        "touch",
        "glob",
        "rglob",
        "listdir",
        "walk",
        "scandir",
        "getenv",
        "system",
        "popen",
        "run",
        "connect",
        "request",
        "urlopen",
        "schedule",
        "start",
        "__import__",
        "eval",
        "exec",
    }
    allowed_list_methods = {"append"}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in allowed_list_methods:
                continue
            assert attr not in forbidden_calls, (
                f"forbidden call: {attr}"
            )
        elif isinstance(node.func, ast.Name):
            name = node.func.id
            assert name not in forbidden_calls, (
                f"forbidden call: {name}"
            )


def test_module_source_has_no_clock_environment_random_or_seed_input():
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    forbidden_tokens = {
        "import os",
        "import random",
        "import time",
        "datetime",
        "environ",
        "provenance_seed",
        "raw_secret",
    }
    for token in forbidden_tokens:
        assert token not in source, f"forbidden token: {token}"


# === Phase 31: all valid ref_type values ===


@pytest.mark.parametrize(
    "ref_type",
    sorted(VALID_REF_TYPES),
)
def test_all_valid_ref_types_accepted(adam_agent_id_fixture, ref_type):
    ref = _own_ref(adam_agent_id_fixture, ref_type)
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert result["adam_memory_refs"][0]["ref_type"] == ref_type


@pytest.fixture
def adam_agent_id_fixture():
    return _adam_agent_id()


# === Phase 32: multiple refs, deterministic ordering ===


def test_multiple_refs_stable_order():
    adam_id = _adam_agent_id()
    ref_a = {
        "ref_id": "10K-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    ref_b = {
        "ref_id": "10K-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "owner_agent_id": adam_id,
        "ref_type": "public_evidence",
        "is_public": False,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref_a, ref_b])

    result = _create_memory_boundary(request)

    assert result["ok"] is True
    assert len(result["adam_memory_refs"]) == 2
    assert result["adam_memory_refs"] == [ref_a, ref_b]


# === Phase 33: credential and configuration marker rejection ===


def test_api_key_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-api_key_abcd",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "sensitive_identifier_leakage" in result["errors"]
    _assert_inert(result)


def test_password_secret_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-password-secret",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "sensitive_identifier_leakage" in result["errors"]


def test_access_token_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-access_token_123",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "sensitive_identifier_leakage" in result["errors"]


def test_private_config_value_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-private_config_value",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "sensitive_identifier_leakage" in result["errors"]


def test_dot_env_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-test.env",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "sensitive_identifier_leakage" in result["errors"]


# === Phase 34: filesystem path rejection including drive letters ===


def test_windows_drive_path_with_backslash_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": r"10K-C\Users\Data",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "private_path_leakage" in result["errors"]


def test_posix_path_with_forward_slash_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-S/Genesis/data",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "private_path_leakage" in result["errors"]


def test_url_encoded_path_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-private%2fprivate%2fpath",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "private_path_leakage" in result["errors"]


def test_backslash_encoded_path_in_ref_id_rejected():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-private%5cprivate%5cpath",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "private_path_leakage" in result["errors"]


# === Phase 35: tampered habitat boundary ID (only ID changed) ===


def test_only_habitat_boundary_id_changed_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["habitat_boundary_id"] = (
        "10ID-0000000000000000000000000000000"
    )

    request = _valid_memory_boundary_request(habitat_boundary)
    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]
    _assert_inert(result)


def test_habitat_boundary_id_recomputed_matches_supplied():
    habitat_boundary = _create_habitat_boundary()
    material = dict(habitat_boundary)
    material.pop("habitat_boundary_id", None)
    import hashlib

    canonical = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    expected_id = "10ID-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    assert habitat_boundary["habitat_boundary_id"] == expected_id


# === Phase 36: no rejected ref_id echoed in invalid output ===


def test_rejected_ref_id_not_echoed_in_invalid_output():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-api_key_leaked_value",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    output_text = json.dumps(result, sort_keys=True)
    assert "api_key" not in output_text.lower()
    assert "leaked_value" not in output_text.lower()


def test_rejected_hidden_substrate_not_echoed_in_invalid_output():
    adam_id = _adam_agent_id()
    ref = {
        "ref_id": "10K-true_map_hidden",
        "owner_agent_id": adam_id,
        "ref_type": "public_observation",
        "is_public": True,
    }
    request = _valid_memory_boundary_request(adam_memory_refs=[ref])

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    output_text = json.dumps(result, sort_keys=True)
    assert "true_map_hidden" not in output_text
    assert "adam_memory_refs" in result
    assert result["adam_memory_refs"] == []
    assert result["eve_memory_refs"] == []


# === Phase 37: duplicate identity refs in recreated boundary ===


def test_duplicate_identity_refs_in_boundary_rejected():
    habitat_boundary = _create_habitat_boundary()
    habitat_boundary["eve_identity_ref"]["agent_id"] = (
        habitat_boundary["adam_identity_ref"]["agent_id"]
    )
    request = _valid_memory_boundary_request(habitat_boundary)

    result = _create_memory_boundary(request)

    assert result["ok"] is False
    assert "invalid_habitat_boundary" in result["errors"]
