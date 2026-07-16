"""Phase 10IC - pure first-pair birth candidate and heartbeat tests."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest


MODULE_NAME = "backend.world.local_first_pair_birth_candidate"
MODULE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "world"
    / "local_first_pair_birth_candidate.py"
)

IDENTITY_SCHEMA_VERSION = "first_pair_identity.1"
ID_DERIVATION_VERSION = "sha256-full-v1"
IDENTITY_DOMAIN_SEPARATOR = "GENESIS_FIRST_PAIR_IDENTITY_V1"
PAIR_ID = "genesis-first-pair"
HABITAT_ID = "genesis-first-habitat"
ROLLBACK_ANCHOR_ID = "genesis-first-pair-anchor"

IDENTITY_FIELDS = {
    "identity_valid",
    "canonical_name",
    "canonical_agent_ref",
    "pair_id",
    "founding_role",
    "provenance_commitment",
    "agent_id",
}

HABITAT_FIELDS = {
    "habitat_valid",
    "habitat_schema_version",
    "habitat_id",
    "allowed_tile_ids",
    "starting_tile_ids",
    "observation_boundaries",
    "movement_allowed",
}

ROLLBACK_FIELDS = {
    "rollback_anchor_valid",
    "rollback_anchor_schema_version",
    "rollback_anchor_id",
    "habitat_id",
    "claim_scope",
    "state_commitment",
}

BIRTH_OUTPUT_FIELDS = {
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

HEARTBEAT_OUTPUT_FIELDS = {
    "ok",
    "heartbeat_schema_version",
    "heartbeat_type",
    "heartbeat_scope",
    "heartbeat_proof_id",
    "status",
    "birth_candidate_id",
    "agent_id",
    "canonical_agent_ref",
    "habitat_id",
    "rollback_anchor_id",
    "tick",
    "action",
    "claim_scope",
    "observation",
    "heartbeat_verified",
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
    "claim_boundary",
    "errors",
}

INERT_BIRTH_FLAGS = {
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

INERT_HEARTBEAT_FLAGS = {
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
}


def _module():
    return importlib.import_module(MODULE_NAME)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _expected_agent_id(
    *,
    canonical_name: str,
    canonical_agent_ref: str,
    provenance_commitment: str,
) -> str:
    material = {
        "domain_separator": IDENTITY_DOMAIN_SEPARATOR,
        "identity_schema_version": IDENTITY_SCHEMA_VERSION,
        "id_derivation_version": ID_DERIVATION_VERSION,
        "canonical_name": canonical_name,
        "canonical_agent_ref": canonical_agent_ref,
        "pair_id": PAIR_ID,
        "founding_role": "founding_agent",
        "provenance_commitment": provenance_commitment,
    }
    digest = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
    return "genesis-agent-" + digest


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
    return _module().create_first_pair_birth_candidate(
        declaration if declaration is not None else _valid_declaration()
    )


def _valid_observation(candidate: dict, member: str = "adam") -> dict:
    identity = candidate[f"{member}_identity"]
    canonical_ref = identity["canonical_agent_ref"]
    habitat = candidate["habitat"]
    return {
        "observation_schema_version": "10IC.OBS.1",
        "agent_id": identity["agent_id"],
        "habitat_id": habitat["habitat_id"],
        "rollback_anchor_id": candidate["rollback_anchor"]["rollback_anchor_id"],
        "tick": 0,
        "action": "observe",
        "claim_scope": "observed",
        "current_tile_id": habitat["starting_tile_ids"][canonical_ref],
        "visible_tile_ids": list(
            habitat["observation_boundaries"][canonical_ref]
        ),
        "summary": f"{identity['canonical_name']} observes the public starting tile.",
    }


def _verify(
    candidate: dict,
    observation: dict,
    authorized_declaration: dict | None = None,
) -> dict:
    declaration = (
        authorized_declaration
        if authorized_declaration is not None
        else _valid_declaration()
    )
    return _module().verify_first_pair_observation_heartbeat(
        candidate,
        observation,
        declaration,
    )


def _assert_birth_inert(result: dict) -> None:
    for field in INERT_BIRTH_FLAGS:
        assert result[field] is False


def _assert_heartbeat_inert(result: dict) -> None:
    for field in INERT_HEARTBEAT_FLAGS:
        assert result[field] is False


class _EqualString(str):
    pass


class _ExplodingEquality:
    def __eq__(self, other: object) -> bool:
        raise AssertionError("hostile equality executed")

    def __ne__(self, other: object) -> bool:
        raise AssertionError("hostile inequality executed")


class _HostileIdentitySchemaKey:
    def __hash__(self) -> int:
        return hash("identity_schema_version")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("hostile key equality executed")


def test_phase10ic_module_exists_before_import():
    assert MODULE_PATH.is_file()


def test_birth_candidate_is_deterministic_pure_and_has_exact_envelope():
    declaration = _valid_declaration()
    original = copy.deepcopy(declaration)

    first = _create_candidate(declaration)
    second = _create_candidate(copy.deepcopy(declaration))

    assert declaration == original
    assert first == second
    assert first["ok"] is True
    assert first["status"] == "ready_for_observation_verification"
    assert set(first) == BIRTH_OUTPUT_FIELDS
    assert set(first["adam_identity"]) == IDENTITY_FIELDS
    assert set(first["eve_identity"]) == IDENTITY_FIELDS
    assert set(first["habitat"]) == HABITAT_FIELDS
    assert set(first["rollback_anchor"]) == ROLLBACK_FIELDS
    assert first["birth_candidate_id"].startswith("10IC-")
    assert first["errors"] == []
    _assert_birth_inert(first)


def test_identity_derivation_uses_full_deterministic_sha256_ids():
    result = _create_candidate()

    expected_adam = _expected_agent_id(
        canonical_name="Adam",
        canonical_agent_ref="east_adam",
        provenance_commitment="a" * 64,
    )
    expected_eve = _expected_agent_id(
        canonical_name="Eve",
        canonical_agent_ref="east_eve",
        provenance_commitment="b" * 64,
    )

    assert result["adam_identity"]["agent_id"] == expected_adam
    assert result["eve_identity"]["agent_id"] == expected_eve
    assert len(result["adam_identity"]["agent_id"].removeprefix("genesis-agent-")) == 64
    assert len(result["eve_identity"]["agent_id"].removeprefix("genesis-agent-")) == 64
    assert result["adam_identity"]["agent_id"] != result["eve_identity"]["agent_id"]


@pytest.mark.parametrize(
    ("invalid_member", "valid_member", "bad_field", "bad_value"),
    [
        ("adam", "eve", "canonical_name", "Not Adam"),
        ("eve", "adam", "canonical_name", "Not Eve"),
    ],
)
def test_one_identity_failure_does_not_invalidate_the_other(
    invalid_member: str,
    valid_member: str,
    bad_field: str,
    bad_value: str,
):
    valid_result = _create_candidate()
    declaration = _valid_declaration()
    declaration[f"{invalid_member}_identity"][bad_field] = bad_value

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result[f"{invalid_member}_identity"]["identity_valid"] is False
    assert result[f"{valid_member}_identity"] == valid_result[f"{valid_member}_identity"]
    assert result[f"{valid_member}_identity"]["identity_valid"] is True
    _assert_birth_inert(result)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.pop("rollback_anchor"),
        lambda value: value["habitat"]["observation_boundaries"].update(
            {"east_adam": []}
        ),
        lambda value: value["habitat"]["starting_tile_ids"].update(
            {"east_adam": "unknown-tile"}
        ),
        lambda value: value["habitat"].update({"movement_allowed": True}),
        lambda value: value.update({"true_map": {"hidden": "world"}}),
    ],
)
def test_birth_candidate_fails_closed_on_boundary_drift(mutate):
    declaration = _valid_declaration()
    mutate(declaration)

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result["status"] == "invalid_birth_candidate"
    assert result["errors"]
    _assert_birth_inert(result)


def test_birth_candidate_rejects_raw_secret_seed_fields():
    declaration = _valid_declaration()
    declaration["adam_identity"]["provenance_seed"] = "raw-secret-seed"

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert "raw-secret-seed" not in json.dumps(result, sort_keys=True)
    assert "provenance_seed" not in json.dumps(result, sort_keys=True)
    _assert_birth_inert(result)


def test_birth_candidate_rejects_string_subclasses_in_contract_fields():
    declaration = _valid_declaration()
    declaration["identity_schema_version"] = _EqualString(IDENTITY_SCHEMA_VERSION)

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result["adam_identity"]["identity_valid"] is False
    assert result["eve_identity"]["identity_valid"] is False
    _assert_birth_inert(result)


def test_birth_candidate_rejects_string_subclasses_as_contract_keys():
    declaration = _valid_declaration()
    declaration["adam_identity"] = {
        _EqualString(key): value
        for key, value in declaration["adam_identity"].items()
    }

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result["adam_identity"]["identity_valid"] is False
    assert result["eve_identity"]["identity_valid"] is True
    _assert_birth_inert(result)


def test_birth_candidate_rejects_secret_like_identifiers_without_reflection():
    declaration = _valid_declaration()
    declaration["habitat"]["habitat_id"] = "API_KEY:example"
    declaration["rollback_anchor"]["habitat_id"] = "API_KEY:example"

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert "API_KEY" not in json.dumps(result, sort_keys=True)
    assert "example" not in json.dumps(result, sort_keys=True)
    _assert_birth_inert(result)


@pytest.mark.parametrize("habitat_id", ["true-map", "true.map", "known-map"])
def test_birth_candidate_rejects_hidden_substrate_identifier_variants(
    habitat_id: str,
):
    declaration = _valid_declaration()
    declaration["habitat"]["habitat_id"] = habitat_id
    declaration["rollback_anchor"]["habitat_id"] = habitat_id

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert habitat_id not in json.dumps(result, sort_keys=True)
    _assert_birth_inert(result)


@pytest.mark.parametrize(
    "habitat_id",
    [_EqualString(HABITAT_ID), _ExplodingEquality()],
    ids=["string-subclass", "hostile-equality"],
)
def test_birth_candidate_rejects_non_plain_rollback_habitat_id(
    habitat_id: object,
):
    declaration = _valid_declaration()
    declaration["rollback_anchor"]["habitat_id"] = habitat_id

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result["rollback_anchor"]["rollback_anchor_valid"] is False
    _assert_birth_inert(result)


def test_birth_candidate_rejects_hostile_top_level_key_without_executing_it():
    declaration = _valid_declaration()
    declaration.pop("identity_schema_version")
    declaration[_HostileIdentitySchemaKey()] = IDENTITY_SCHEMA_VERSION

    result = _create_candidate(declaration)

    assert result["ok"] is False
    assert result["errors"]
    _assert_birth_inert(result)


def test_birth_candidate_id_commits_to_the_safe_output_envelope():
    result = _create_candidate()
    material = dict(result)
    material.pop("birth_candidate_id")
    expected = "10IC-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]

    assert result["birth_candidate_id"] == expected


@pytest.mark.parametrize("member", ["adam", "eve"])
def test_observation_only_heartbeat_verifies_each_identity_independently(member: str):
    candidate = _create_candidate()
    observation = _valid_observation(candidate, member)

    result = _verify(candidate, observation)

    assert result["ok"] is True
    assert result["heartbeat_verified"] is True
    assert result["status"] == "verified_observation_only"
    assert result["action"] == "observe"
    assert result["claim_scope"] == "observed"
    assert result["agent_id"] == candidate[f"{member}_identity"]["agent_id"]
    assert set(result) == HEARTBEAT_OUTPUT_FIELDS
    assert result["errors"] == []
    _assert_heartbeat_inert(result)


def test_heartbeat_returns_sanitized_public_observation_and_proof():
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation["summary"] = r"Adam sees C:\Users\Sean\secret.txt API_KEY=example"

    first = _verify(candidate, observation)
    second = _verify(
        copy.deepcopy(candidate),
        copy.deepcopy(observation),
    )

    assert first == second
    assert first["ok"] is True
    serialized = json.dumps(first, sort_keys=True)
    assert r"C:\Users" not in first["observation"]["summary"]
    assert "API_KEY" not in serialized
    assert "example" not in serialized
    assert "[REDACTED_PATH]" in first["observation"]["summary"]
    assert "[REDACTED_SECRET]" in first["observation"]["summary"]
    assert first["heartbeat_proof_id"].startswith("10IC-HB-")
    _assert_heartbeat_inert(first)


def test_heartbeat_proof_id_commits_to_the_safe_output_envelope():
    candidate = _create_candidate()
    result = _verify(candidate, _valid_observation(candidate))
    material = dict(result)
    material.pop("heartbeat_proof_id")
    expected = "10IC-HB-" + hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()[:32]

    assert result["heartbeat_proof_id"] == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("action", "gather"),
        ("action", "whisper"),
        ("action", "move"),
        ("action", "route_plan"),
        ("claim_scope", "memory"),
        ("tick", True),
        ("tick", -1),
        ("rollback_anchor_id", "missing-anchor"),
        ("habitat_id", "unknown-habitat"),
    ],
)
def test_heartbeat_fails_closed_on_invalid_required_input(field: str, value: object):
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation[field] = value

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    assert result["status"] == "rejected"
    assert result["errors"]
    _assert_heartbeat_inert(result)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "write_requested",
        "memory_write_requested",
        "ledger_write_requested",
        "model_call_requested",
        "provider_call_requested",
        "network_call_requested",
        "daemon_start_requested",
        "scheduler_start_requested",
        "container_start_requested",
        "docker_start_requested",
        "true_map",
    ],
)
def test_heartbeat_fails_closed_on_attempted_side_effect(forbidden_field: str):
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation[forbidden_field] = True

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    assert forbidden_field not in result
    _assert_heartbeat_inert(result)


def test_heartbeat_rejects_hidden_true_map_leakage_in_summary():
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation["summary"] = "The hidden true_map contains another region."

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert "true_map" not in json.dumps(result, sort_keys=True).lower()
    _assert_heartbeat_inert(result)


@pytest.mark.parametrize(
    "summary",
    [
        "The hidden true-map contains another region.",
        "The hidden true map contains another region.",
        "The hidden truemap contains another region.",
        "The hidden-substrate contains another region.",
        "The hidden true.map contains another region.",
        "The hidden true\tmap contains another region.",
        "The hidden true\u200bmap contains another region.",
        "The known-map contains another region.",
        "The hidden ＴＲＵＥ＿ＭＡＰ contains another region.",
        "The hidden truеmap contains another region.",
    ],
)
def test_heartbeat_rejects_hidden_substrate_spelling_variants(summary: str):
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation["summary"] = summary

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    assert summary not in json.dumps(result, sort_keys=True)
    _assert_heartbeat_inert(result)


@pytest.mark.parametrize(
    "private_path",
    [
        "/home/sean/private-proof.txt",
        "/opt/private/proof.txt",
        "/root/.ssh/id_rsa",
        r"folder\private\proof.txt",
        r"C:private\proof.txt",
        r"\root\proof.txt",
        "folder%2Fprivate%2Fproof.txt",
        "folder%5Cprivate%5Cproof.txt",
        "folder／private／proof.txt",
    ],
)
def test_heartbeat_rejects_unredacted_private_path_in_summary(private_path: str):
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation["summary"] = f"Adam sees {private_path}"

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert private_path not in json.dumps(result, sort_keys=True)
    _assert_heartbeat_inert(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tick", 10**5000),
        ("summary", "invalid-surrogate-\ud800"),
    ],
    ids=["unbounded-tick", "non-utf8-summary"],
)
def test_heartbeat_fails_closed_on_unbounded_or_non_utf8_scalar(
    field: str,
    value: object,
):
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation[field] = value

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    _assert_heartbeat_inert(result)


def test_heartbeat_rejects_string_subclasses_in_contract_fields():
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    observation["action"] = _EqualString("observe")

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    _assert_heartbeat_inert(result)


def test_heartbeat_rejects_tile_outside_member_observation_boundary():
    candidate = _create_candidate()
    observation = _valid_observation(candidate, "adam")
    observation["visible_tile_ids"] = ["public-start-eve"]

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["heartbeat_verified"] is False
    _assert_heartbeat_inert(result)


def test_heartbeat_rejects_tampered_birth_candidate():
    candidate = _create_candidate()
    observation = _valid_observation(candidate)
    candidate["adam_identity"]["agent_id"] = "genesis-agent-" + "0" * 64

    result = _verify(candidate, observation)

    assert result["ok"] is False
    assert result["errors"] == ["invalid_birth_candidate"]
    _assert_heartbeat_inert(result)


def test_heartbeat_rejects_recomputed_candidate_drift_from_authorized_declaration():
    authorized_declaration = _valid_declaration()
    drifted_declaration = copy.deepcopy(authorized_declaration)
    drifted_declaration["habitat"]["allowed_tile_ids"].insert(
        0,
        "unauthorized-extra-tile",
    )
    drifted_declaration["habitat"]["observation_boundaries"]["east_adam"].insert(
        0,
        "unauthorized-extra-tile",
    )
    drifted_candidate = _create_candidate(drifted_declaration)
    observation = _valid_observation(drifted_candidate)

    result = _verify(
        drifted_candidate,
        observation,
        authorized_declaration,
    )

    assert drifted_candidate["ok"] is True
    assert result["ok"] is False
    assert result["errors"] == ["invalid_birth_candidate"]
    _assert_heartbeat_inert(result)


def test_candidate_claim_boundary_does_not_claim_authentication():
    result = _create_candidate()

    assert "caller declaration is authority" in result["claim_boundary"]
    assert "integrity fingerprint only" in result["claim_boundary"]


def test_module_has_only_safe_imports_and_no_10cp_or_10hd_dependency():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed_modules = {
        "__future__",
        "hashlib",
        "json",
        "typing",
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
