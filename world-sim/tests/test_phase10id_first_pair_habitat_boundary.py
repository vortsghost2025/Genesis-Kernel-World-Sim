"""Phase 10ID - pure first-pair habitat boundary tests.

Tests that an authorized Phase 10IC birth candidate can be associated with a
bounded habitat declaration, with exact deterministic identity and habitat
inputs. Rejects malformed declarations, invalid identity references, duplicate
identities, out-of-bounds positions, invalid observation radius values,
bool-as-int inputs, non-string identifiers, and unknown fields.

Strict TDD: this test file is written first and must fail (RED) before the
module exists.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

MODULE_NAME = "backend.world.local_first_pair_habitat_boundary"
MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_first_pair_habitat_boundary.py"
)

BIRTH_MODULE_NAME = "backend.world.local_first_pair_birth_candidate"

HABITAT_BOUNDARY_SCHEMA_VERSION = "10ID.1"
HABITAT_BOUNDARY_TYPE = "first_pair_habitat_boundary"
HABITAT_BOUNDARY_SCOPE = "pure_in_memory_boundary_only"

IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"
ID_DERIVATION_VERSION = "sha256-full-v1"
PAIR_ID = "genesis-first-pair"
HABITAT_ID = "genesis-first-habitat"
ROLLBACK_ANCHOR_ID = "genesis-first-pair-anchor"

HABITAT_BOUNDARY_OUTPUT_FIELDS = {
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


def _module():
    import importlib

    return importlib.import_module(MODULE_NAME)


def _birth_module():
    import importlib

    return importlib.import_module(BIRTH_MODULE_NAME)


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
        "habitat_boundary_schema_version": HABITAT_BOUNDARY_SCHEMA_VERSION,
        "birth_candidate": candidate,
        "authorized_declaration": declaration,
        "observation_radius": 1,
    }


def _create_boundary(request: dict | None = None) -> dict:
    if request is None:
        request = _valid_habitat_boundary_request()
    return _module().create_first_pair_habitat_boundary(request)


def _assert_inert(result: dict) -> None:
    for field in INERT_FLAGS:
        assert result[field] is False, f"{field} should be False"


class _EqualString(str):
    pass


# --- Phase 1: module existence ---

def test_phase10id_module_exists_before_import():
    assert MODULE_PATH.is_file()


# --- Phase 2: deterministic, pure, exact envelope ---

def test_habitat_boundary_is_deterministic_pure_and_has_exact_envelope():
    request = _valid_habitat_boundary_request()
    original = copy.deepcopy(request)

    first = _create_boundary(request)
    second = _create_boundary(copy.deepcopy(request))

    assert request == original
    assert first == second
    assert first["ok"] is True
    assert first["status"] == "habitat_boundary_verified"
    assert set(first) == HABITAT_BOUNDARY_OUTPUT_FIELDS
    assert first["habitat_boundary_id"].startswith("10ID-")
    assert first["errors"] == []
    _assert_inert(first)


def test_habitat_boundary_id_commits_to_safe_output_envelope():
    import hashlib

    result = _create_boundary()
    material = dict(result)
    material.pop("habitat_boundary_id")
    canonical = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    expected = "10ID-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    assert result["habitat_boundary_id"] == expected


# --- Phase 3: identity reference extraction ---

def test_boundary_extract_identity_refs_from_birth_candidate():
    candidate = _create_candidate()
    result = _create_boundary()

    adam_ref = result["adam_identity_ref"]
    eve_ref = result["eve_identity_ref"]

    assert set(adam_ref) == IDENTITY_REF_FIELDS
    assert set(eve_ref) == IDENTITY_REF_FIELDS
    assert adam_ref["agent_id"] == candidate["adam_identity"]["agent_id"]
    assert adam_ref["canonical_name"] == "Adam"
    assert adam_ref["canonical_agent_ref"] == "east_adam"
    assert eve_ref["agent_id"] == candidate["eve_identity"]["agent_id"]
    assert eve_ref["canonical_name"] == "Eve"
    assert eve_ref["canonical_agent_ref"] == "east_eve"


def test_boundary_rejects_duplicate_identity_agent_ids():
    declaration = _valid_declaration()
    candidate = _create_candidate(declaration)
    candidate["eve_identity"]["agent_id"] = candidate["adam_identity"]["agent_id"]
    request = _valid_habitat_boundary_request(candidate)
    request["authorized_declaration"] = declaration

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "duplicate_identity" in result["errors"]
    _assert_inert(result)


# --- Phase 4: habitat validation ---

def test_boundary_preserves_habitat_surface_from_candidate():
    candidate = _create_candidate()
    result = _create_boundary()

    habitat = result["habitat"]
    assert habitat == candidate["habitat"]
    assert habitat["movement_allowed"] is False


def test_boundary_preserves_rollback_anchor_from_candidate():
    candidate = _create_candidate()
    result = _create_boundary()

    assert result["rollback_anchor"] == candidate["rollback_anchor"]


def test_boundary_tile_ids_match_habitat_allowed_tiles():
    candidate = _create_candidate()
    result = _create_boundary()

    assert set(result["boundary_tile_ids"]) == set(
        candidate["habitat"]["allowed_tile_ids"]
    )


# --- Phase 5: observation radius validation ---

def test_boundary_accepts_valid_observation_radius():
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = 1

    result = _create_boundary(request)

    assert result["ok"] is True
    assert result["observation_radius"] == 1
    assert result["within_bounds"] is True


@pytest.mark.parametrize("radius", [0, 2, 3, 5, 10])
def test_boundary_rejects_observation_radius_outside_allowed(radius: int):
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = radius

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_observation_radius" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_bool_as_int_observation_radius():
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = True

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_observation_radius" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_negative_observation_radius():
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = -1

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_observation_radius" in result["errors"]
    _assert_inert(result)


# --- Phase 6: birth candidate validity ---

def test_boundary_rejects_tampered_birth_candidate():
    candidate = _create_candidate()
    candidate["adam_identity"]["agent_id"] = "genesis-agent-" + "0" * 64

    request = _valid_habitat_boundary_request(candidate)

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_candidate_not_matching_authorized_declaration():
    candidate = _create_candidate()
    authorized = _valid_declaration()
    authorized["habitat"]["allowed_tile_ids"] = [
        "public-start-adam",
        "public-start-eve",
        "unauthorized-extra-tile",
    ]

    request = _valid_habitat_boundary_request(candidate)
    request["authorized_declaration"] = authorized

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "candidate_declaration_drift" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_ok_false_candidate():
    bad_declaration = _valid_declaration()
    bad_declaration["adam_identity"]["canonical_name"] = "Not Adam"
    candidate = _create_candidate(bad_declaration)

    request = _valid_habitat_boundary_request(candidate)
    request["authorized_declaration"] = _valid_declaration()

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    _assert_inert(result)


# --- Phase 7: invalid identity references ---

def test_boundary_rejects_non_string_identity_ref_agent_id():
    candidate = _create_candidate()
    candidate["adam_identity"]["agent_id"] = 12345

    request = _valid_habitat_boundary_request(candidate)

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_string_subclass_in_identity_ref():
    candidate = _create_candidate()
    candidate["adam_identity"]["agent_id"] = _EqualString(
        candidate["adam_identity"]["agent_id"]
    )

    request = _valid_habitat_boundary_request(candidate)

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    _assert_inert(result)


# --- Phase 8: malformed request shapes ---

def test_boundary_rejects_unknown_request_fields():
    request = _valid_habitat_boundary_request()
    request["true_map"] = {"hidden": "world"}

    result = _create_boundary(request)

    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


def test_boundary_rejects_missing_request_fields():
    request = _valid_habitat_boundary_request()
    del request["observation_radius"]

    result = _create_boundary(request)

    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


def test_boundary_rejects_wrong_schema_version():
    request = _valid_habitat_boundary_request()
    request["habitat_boundary_schema_version"] = "10ID.999"

    result = _create_boundary(request)

    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


def test_boundary_rejects_non_dict_birth_candidate():
    request = _valid_habitat_boundary_request()
    request["birth_candidate"] = "not a dict"

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_non_dict_authorized_declaration():
    request = _valid_habitat_boundary_request()
    request["authorized_declaration"] = 42

    result = _create_boundary(request)

    assert result["ok"] is False
    assert result["errors"]
    _assert_inert(result)


# --- Phase 9: within_bounds flag ---

def test_within_bounds_true_when_all_tiles_in_boundary():
    result = _create_boundary()

    assert result["within_bounds"] is True


def test_within_bounds_false_when_candidate_has_tampered_habitat():
    candidate = _create_candidate()
    candidate["habitat"]["allowed_tile_ids"] = [
        "public-start-adam",
        "public-start-eve",
        "rogue-tile",
    ]

    request = _valid_habitat_boundary_request(candidate)

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_birth_candidate" in result["errors"]
    assert result["within_bounds"] is False
    _assert_inert(result)


# --- Phase 10: claim boundary ---

def test_claim_boundary_does_not_authorize_runtime():
    result = _create_boundary()

    assert "boundary contract" in result["claim_boundary"]
    assert "no runtime" in result["claim_boundary"]


# --- Phase 11: source-level safety guarantees ---

def test_module_has_only_safe_imports_and_no_10cp_or_10hd_dependency():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_modules = {
        "__future__",
        "hashlib",
        "json",
        "typing",
        "backend.world.local_first_pair_birth_candidate",
        "backend.world.world_event_sanitizer",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in allowed_modules
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") in allowed_modules

    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    assert "10hd" not in source
    assert "local_runtime_adapter_inert_ledger_writer" not in source
    assert "append_inert_ledger_record" not in source


def test_module_has_no_file_runtime_provider_model_or_network_calls():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_calls = {
        "open",
        "read",
        "write",
        "append",
        "mkdir",
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
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_calls
        elif isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls


def test_module_source_has_no_clock_environment_random_or_raw_seed_input():
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
        assert token not in source


# --- Phase 12: fog-of-war boundary preservation ---

def test_boundary_does_not_leak_hidden_substrate_in_output():
    result = _create_boundary()
    serialized = json.dumps(result, sort_keys=True)

    assert "true_map" not in serialized.lower()
    assert "hidden_substrate" not in serialized.lower()


def test_boundary_observation_radius_must_be_exact_int_not_subclass():
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = _EqualString(1)

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_observation_radius" in result["errors"]
    _assert_inert(result)


def test_boundary_rejects_float_observation_radius():
    request = _valid_habitat_boundary_request()
    request["observation_radius"] = 1.0

    result = _create_boundary(request)

    assert result["ok"] is False
    assert "invalid_observation_radius" in result["errors"]
    _assert_inert(result)
