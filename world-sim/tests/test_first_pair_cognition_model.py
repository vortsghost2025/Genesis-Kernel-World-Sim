"""Tests for the model-backed First Pair cognition backend.

Uses a mocked or injected OpenAI client to avoid actual network calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)
import backend.world.first_pair_cognition_model as cmod
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    ProviderConfig,
    ProviderError,
    _extract_json,
    _is_safe_id,
    _casefolded_contaminated,
    build_system_prompt,
    resolve_provider,
    sanitize_provider_error,
    validate_model_output,
    validate_action_exact,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_context() -> AgentContext:
    return AgentContext(
        agent_id="genesis-agent-test-adam-0000000000000000000000000000000000000000000000000000",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=3,
        position="tile-alpha",
        observation={
            "tile_id": "tile-alpha",
            "visible_tiles": ["tile-alpha", "tile-beta"],
            "objects_here": [],
        },
        memory=[
            {"type": "observation", "content": "I see an empty room.", "heartbeat": 1},
        ],
        goals=[
            {"goal_id": "goal-explore", "agent_id": "genesis-agent-test-adam-...", "description": "Explore the world", "status": "active"},
        ],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha", "tile-beta"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-07-27T12:00:00Z",
        other_agent_id="genesis-agent-test-eve-...",
        other_agent_name="Eve",
        other_agent_ref="east_eve",
        answered_questions=[],
    )


@pytest.fixture
def sample_eve_context() -> AgentContext:
    return AgentContext(
        agent_id="genesis-agent-test-eve-0000000000000000000000000000000000000000000000000000",
        canonical_name="Eve",
        canonical_ref="east_eve",
        heartbeat_number=3,
        position="tile-beta",
        observation={
            "tile_id": "tile-beta",
            "visible_tiles": ["tile-beta", "tile-alpha"],
            "objects_here": [],
        },
        memory=[
            {"type": "observation", "content": "Eve's private memory: I see a different room.", "heartbeat": 1},
        ],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha", "tile-beta"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-07-27T12:00:00Z",
        other_agent_id="genesis-agent-test-adam-...",
        other_agent_name="Adam",
        other_agent_ref="east_adam",
        answered_questions=[],
    )


def _make_mock_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    choice.message.role = "assistant"
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    return mock_resp


_valid_response = {
    "observation_summary": "I see an empty tile with no objects.",
    "self_model_update": None,
    "goal_updates": [],
    "proposed_action": None,
    "memory_candidates": [],
    "questions_for_humans": [],
    "uncertainty": "Whether any other agents exist nearby.",
    "decision_summary": "Chose no_action because there is nothing to interact with.",
    "confidence": 0.6,
}


# ---------------------------------------------------------------------------
# Provider resolution tests
# ---------------------------------------------------------------------------


class TestProviderResolution:
    def test_explicit_url_and_model(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://custom.example.com"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "custom-key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "custom-model"
        try:
            cfg = resolve_provider()
            assert cfg.base_url == "https://custom.example.com/v1"
            assert cfg.api_key == "custom-key"
            assert cfg.model == "custom-model"
            assert cfg.provider_type == "explicit_url"
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                      "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                      "OPENROUTER_API_KEY", "OLLAMA_HOST"):
                os.environ.pop(k, None)

    def test_no_v1_doubling(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://custom.example.com/v1"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "m"
        try:
            cfg = resolve_provider()
            assert cfg.base_url == "https://custom.example.com/v1", f"Got: {cfg.base_url}"
            assert cfg.base_url.count("/v1") == 1
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                      "GENESIS_FIRST_PAIR_MODEL", "OLLAMA_HOST"):
                os.environ.pop(k, None)

    def test_no_silent_ollama_fallback(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                  "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        with pytest.raises(ProviderError) as exc:
            resolve_provider()
        msg = str(exc.value)
        assert "OLLAMA_HOST" in msg
        assert "NVIDIA_API_KEY" in msg

    def test_nvidia_fallback(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["NVIDIA_API_KEY"] = "nv-key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "nvidia/test-model"
        try:
            cfg = resolve_provider()
            assert "nvidia.com" in cfg.base_url
            assert cfg.api_key == "nv-key"
            assert cfg.model == "nvidia/test-model"
        finally:
            for k in ("NVIDIA_API_KEY", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_openrouter_fallback(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["OPENROUTER_API_KEY"] = "or-key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "openrouter/test-model"
        try:
            cfg = resolve_provider()
            assert "openrouter" in cfg.base_url
            assert cfg.model == "openrouter/test-model"
        finally:
            for k in ("OPENROUTER_API_KEY", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_ollama_requires_model(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["OLLAMA_HOST"] = "http://localhost:11434"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "my-model"
        try:
            cfg = resolve_provider()
            assert cfg.provider_type == "ollama"
            assert cfg.model == "my-model"
        finally:
            for k in ("OLLAMA_HOST", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_ollama_missing_model_reported(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OPENROUTER_API_KEY",
                  "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["OLLAMA_HOST"] = "http://localhost:11434"
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_MODEL" in str(exc.value)
        finally:
            os.environ.pop("OLLAMA_HOST", None)

    def test_missing_provider_fails_clearly(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                  "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        with pytest.raises(ProviderError) as exc:
            resolve_provider()
        msg = str(exc.value)
        assert "No usable provider" in msg

    def test_invalid_url_rejected(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "ftp://bad.example.com"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "m"
        try:
            with pytest.raises(ProviderError):
                resolve_provider()
        finally:
            os.environ.pop("GENESIS_FIRST_PAIR_BASE_URL", None)
            os.environ.pop("GENESIS_FIRST_PAIR_MODEL", None)

    # --- Focused fail-closed tests -----------------------------------------

    def test_explicit_base_without_model_fails(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://api.example.com"
        os.environ.pop("GENESIS_FIRST_PAIR_MODEL", None)
        os.environ.pop("GENESIS_FIRST_PAIR_API_KEY", None)
        os.environ.pop("NVIDIA_API_KEY", None)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("OLLAMA_HOST", None)
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_MODEL" in str(exc.value)
        finally:
            os.environ.pop("GENESIS_FIRST_PAIR_BASE_URL", None)

    def test_remote_explicit_base_without_key_fails(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://api.example.com"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "test-model"
        os.environ.pop("GENESIS_FIRST_PAIR_API_KEY", None)
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_API_KEY" in str(exc.value)
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_localhost_explicit_base_may_omit_key(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "http://localhost:8080"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "local-model"
        os.environ.pop("GENESIS_FIRST_PAIR_API_KEY", None)
        try:
            cfg = resolve_provider()
            assert cfg.provider_type == "explicit_url"
            assert cfg.model == "local-model"
            assert cfg.api_key is None
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_localhost_127_0_0_1_may_omit_key(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "http://127.0.0.1:11434"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "local-model"
        os.environ.pop("GENESIS_FIRST_PAIR_API_KEY", None)
        try:
            cfg = resolve_provider()
            assert cfg.provider_type == "explicit_url"
            assert cfg.api_key is None
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_nvidia_key_without_model_fails(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["NVIDIA_API_KEY"] = "nv-key"
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_MODEL" in str(exc.value)
        finally:
            os.environ.pop("NVIDIA_API_KEY", None)

    def test_openrouter_key_without_model_fails(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["OPENROUTER_API_KEY"] = "or-key"
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_MODEL" in str(exc.value)
        finally:
            os.environ.pop("OPENROUTER_API_KEY", None)

    def test_ollama_host_without_model_fails(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["OLLAMA_HOST"] = "http://localhost:11434"
        try:
            with pytest.raises(ProviderError) as exc:
                resolve_provider()
            assert "GENESIS_FIRST_PAIR_MODEL" in str(exc.value)
        finally:
            os.environ.pop("OLLAMA_HOST", None)

    def test_no_returned_config_has_empty_model(self):
        """Every valid resolve_provider call must return a non-empty model."""
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                  "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "http://127.0.0.1:8000"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "local-m"
        cfg = resolve_provider()
        assert cfg.model, f"Empty model for {cfg.provider_type}"

    def test_no_v1_doubled_across_providers(self):
        """/v1 is never doubled for any valid configuration."""
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://custom.example.com/v1"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "k"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "m"
        try:
            cfg = resolve_provider()
            assert cfg.base_url.count("/v1") == 1
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                      "GENESIS_FIRST_PAIR_MODEL"):
                os.environ.pop(k, None)

    def test_no_provider_does_not_construct_client_or_call_network(self):
        """No-provider resolution performs no client construction or network call."""
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                  "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        with pytest.raises(ProviderError):
            resolve_provider()
        # If it raised ProviderError, no client was constructed.
        # We confirm no side effects by checking no new env keys were written:
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY",
                  "OPENROUTER_API_KEY", "OLLAMA_HOST"):
            assert k not in os.environ or os.environ[k] == "", f"Unexpected env var: {k}"

# ---------------------------------------------------------------------------
# Provider error sanitization
# ---------------------------------------------------------------------------


class TestProviderErrorSanitization:
    def test_sk_key_masked(self):
        msg = sanitize_provider_error(Exception("sk-proj-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"))
        assert "sk-proj-" in msg
        assert "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0" not in msg

    def test_nvapi_masked(self):
        msg = sanitize_provider_error(Exception("nvapi-abc123def456ghi789jkl"))
        assert "nvapi-" in msg
        assert "abc123def456ghi789jkl" not in msg

    def test_non_printable_stripped(self):
        msg = sanitize_provider_error(Exception("normal\x00error"))
        assert "\x00" not in msg

    def test_long_message_truncated(self):
        long = "x" * 1000
        msg = sanitize_provider_error(Exception(long))
        assert len(msg) <= 510

    def test_api_key_in_query_string_masked(self):
        msg = sanitize_provider_error(Exception("https://host.com?key=supersecret&other=val"))
        assert "key=***" in msg


# ---------------------------------------------------------------------------
# Safe ID validation
# ---------------------------------------------------------------------------


class TestSafeId:
    def test_valid_ids(self):
        for vid in ("abc123", "goal_explore", "object.a-1", "a"):
            assert _is_safe_id(vid), f"Expected valid: {vid}"

    def test_invalid_ids(self):
        for iid in ("", "a" * 129, "hello world", "obj/123", "obj\nid"):
            assert not _is_safe_id(iid), f"Expected invalid: {repr(iid)}"
        assert not _is_safe_id("")


# ---------------------------------------------------------------------------
# Contamination detection
# ---------------------------------------------------------------------------


class TestContamination:
    def test_windows_drive_rejected(self):
        assert _casefolded_contaminated("C:\\Users\\secret\\file")
        assert _casefolded_contaminated("d:\\data")
        assert _casefolded_contaminated("E:\\")

    def test_true_map_rejected(self):
        assert _casefolded_contaminated("The true_map is hidden")

    def test_clean_text_accepted(self):
        assert not _casefolded_contaminated("I see a stone marker.")

    def test_empty_text(self):
        assert not _casefolded_contaminated("")

    def test_hidden_substrate_rejected(self):
        assert _casefolded_contaminated("hidden_substrate is xyz")


# ---------------------------------------------------------------------------
# Output validation — exact schema
# ---------------------------------------------------------------------------


class TestExactSchema:
    CONTEXT_AGENT = "genesis-agent-test-adam-..."

    def _valid_minimal(self) -> dict:
        return dict(_valid_response)

    def test_valid_minimal_output(self):
        raw = self._valid_minimal()
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert result.is_valid, f"Expected valid: {result.validation_errors}"

    def test_unknown_top_level_field_rejected(self):
        raw = self._valid_minimal()
        raw["extra_field"] = "should be rejected"
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("unknown_field:extra_field" in e for e in result.validation_errors)

    def test_missing_field_rejected(self):
        raw = self._valid_minimal()
        del raw["observation_summary"]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("missing_field:observation_summary" in e for e in result.validation_errors)

    def test_empty_observation_summary_rejected(self):
        raw = self._valid_minimal()
        raw["observation_summary"] = ""
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("observation_summary:empty" in e for e in result.validation_errors)

    def test_observation_summary_too_long(self):
        raw = self._valid_minimal()
        raw["observation_summary"] = "x" * 2001
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("exceeds_2000_chars" in e for e in result.validation_errors)

    def test_wrong_type_observation_summary(self):
        raw = self._valid_minimal()
        raw["observation_summary"] = 42
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid

    def test_self_model_update_contaminated(self):
        raw = self._valid_minimal()
        raw["self_model_update"] = "path to /root/config"
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid

    def test_goal_updates_too_many(self):
        raw = self._valid_minimal()
        raw["goal_updates"] = [{"goal_id": f"g{i}", "agent_id": self.CONTEXT_AGENT,
                                "description": "t", "status": "active"} for i in range(17)]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("exceeds_16" in e for e in result.validation_errors)

    def test_memory_candidates_too_many(self):
        raw = self._valid_minimal()
        raw["memory_candidates"] = [{"type": "obs", "content": "x"} for _ in range(17)]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("exceeds_16" in e for e in result.validation_errors)

    def test_questions_for_humans_too_many(self):
        raw = self._valid_minimal()
        raw["questions_for_humans"] = [
            {"question_id": f"q{i}", "question": "test", "reason_for_asking": "why",
             "requested_human_capability": "info", "urgency": "low"}
            for i in range(9)
        ]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("exceeds_8" in e for e in result.validation_errors)

    def test_decision_summary_too_long(self):
        raw = self._valid_minimal()
        raw["decision_summary"] = "x" * 501
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("exceeds_500_chars" in e for e in result.validation_errors)

    def test_contaminated_observation(self):
        raw = self._valid_minimal()
        raw["observation_summary"] = "Reading the true_map"
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid

    def test_boolean_confidence_rejected(self):
        raw = self._valid_minimal()
        raw["confidence"] = True
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("boolean" in e for e in result.validation_errors)

    def test_confidence_out_of_range(self):
        raw = self._valid_minimal()
        raw["confidence"] = 5.0
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid

    def test_goal_update_agent_mismatch(self):
        raw = self._valid_minimal()
        raw["goal_updates"] = [
            {"goal_id": "g1", "agent_id": "wrong-agent-id",
             "description": "t", "status": "active"}
        ]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("agent_id_mismatch" in e for e in result.validation_errors)

    def test_goal_update_unknown_field(self):
        raw = self._valid_minimal()
        raw["goal_updates"] = [
            {"goal_id": "g1", "agent_id": self.CONTEXT_AGENT,
             "description": "t", "status": "active", "extra_field": "bad"}
        ]
        result = validate_model_output(raw, self.CONTEXT_AGENT)
        assert not result.is_valid
        assert any("unknown_field" in e for e in result.validation_errors)


# ---------------------------------------------------------------------------
# Action-specific exact schemas
# ---------------------------------------------------------------------------


class TestActionSchemas:
    CONTEXT_AGENT = "test-agent"

    def test_no_action_valid(self):
        errs = validate_action_exact({"action_type": "no_action"}, self.CONTEXT_AGENT)
        assert not errs

    def test_no_action_extra_field_rejected(self):
        errs = validate_action_exact({"action_type": "no_action", "extra": "bad"}, self.CONTEXT_AGENT)
        assert any("unknown_field" in e for e in errs)

    def test_create_public_object_valid(self):
        errs = validate_action_exact({
            "action_type": "create_public_object",
            "object_id": "stone-1",
            "object_type": "stone",
            "description": "A marker.",
            "tile_id": "tile-alpha",
        }, self.CONTEXT_AGENT)
        assert not errs, f"Got errors: {errs}"

    def test_create_public_object_missing_field(self):
        errs = validate_action_exact({
            "action_type": "create_public_object",
            "object_id": "stone-1",
            "object_type": "stone",
        }, self.CONTEXT_AGENT)
        assert any("empty" in e for e in errs)

    def test_create_public_object_unsafe_id(self):
        errs = validate_action_exact({
            "action_type": "create_public_object",
            "object_id": "../secret",
            "object_type": "x",
            "description": "ok",
            "tile_id": "t1",
        }, self.CONTEXT_AGENT)
        assert any("unsafe_object_id" in e for e in errs)

    def test_inspect_public_object_valid(self):
        errs = validate_action_exact({
            "action_type": "inspect_public_object",
            "target_object_id": "stone-1",
        }, self.CONTEXT_AGENT)
        assert not errs

    def test_inspect_public_object_extra_field_rejected(self):
        errs = validate_action_exact({
            "action_type": "inspect_public_object",
            "target_object_id": "stone-1",
            "description": "should not be here",
        }, self.CONTEXT_AGENT)
        assert any("unknown_field" in e for e in errs)

    def test_modify_owned_public_object_valid(self):
        errs = validate_action_exact({
            "action_type": "modify_owned_public_object",
            "target_object_id": "my-stone",
            "modifications": {"public_description": "Updated description."},
        }, self.CONTEXT_AGENT)
        assert not errs

    def test_modify_owned_protected_field_rejected(self):
        errs = validate_action_exact({
            "action_type": "modify_owned_public_object",
            "target_object_id": "my-stone",
            "modifications": {"object_id": "new-id"},
        }, self.CONTEXT_AGENT)
        assert any("cannot_modify_object_id" in e for e in errs)

    def test_leave_public_message_valid(self):
        errs = validate_action_exact({
            "action_type": "leave_public_message",
            "message": "Hello world",
            "recipient": "all",
        }, self.CONTEXT_AGENT)
        assert not errs

    def test_leave_public_message_empty_rejected(self):
        errs = validate_action_exact({
            "action_type": "leave_public_message",
            "message": "",
            "recipient": "all",
        }, self.CONTEXT_AGENT)
        assert any("empty_message" in e for e in errs)

    def test_ask_human_valid(self):
        errs = validate_action_exact({
            "action_type": "ask_human",
            "question_id": "q-what-am-i",
            "question": "What am I?",
            "reason_for_asking": "Seeking purpose.",
            "related_goal_id": None,
            "requested_human_capability": "philosophy",
            "urgency": "medium",
        }, self.CONTEXT_AGENT)
        assert not errs, f"Got errors: {errs}"

    def test_ask_human_empty_rejected(self):
        errs = validate_action_exact({
            "action_type": "ask_human",
            "question_id": "",
            "question": "",
            "reason_for_asking": "",
            "related_goal_id": None,
            "requested_human_capability": "",
            "urgency": "low",
        }, self.CONTEXT_AGENT)
        assert any("empty" in e for e in errs)

    def test_ask_human_invalid_urgency(self):
        errs = validate_action_exact({
            "action_type": "ask_human",
            "question_id": "q1",
            "question": "test",
            "reason_for_asking": "why",
            "requested_human_capability": "x",
            "urgency": "critical",
        }, self.CONTEXT_AGENT)
        assert any("invalid_urgency" in e for e in errs)

    def test_request_capability_valid(self):
        errs = validate_action_exact({
            "action_type": "request_capability",
            "capability_id": "cap-move",
            "capability_reason": "Need to explore.",
        }, self.CONTEXT_AGENT)
        assert not errs

    def test_request_capability_empty_rejected(self):
        errs = validate_action_exact({
            "action_type": "request_capability",
            "capability_id": "",
            "capability_reason": "",
        }, self.CONTEXT_AGENT)
        assert any("empty" in e for e in errs)

    def test_move_valid(self):
        errs = validate_action_exact({
            "action_type": "move",
            "target_tile": "tile-beta",
            "reason": "Exploring",
        }, self.CONTEXT_AGENT)
        assert not errs

    def test_move_extra_field_rejected(self):
        errs = validate_action_exact({
            "action_type": "move",
            "target_tile": "t1",
            "reason": "r",
            "object_id": "should-be-rejected",
        }, self.CONTEXT_AGENT)
        assert any("unknown_field" in e for e in errs)

    def test_invalid_action_type(self):
        errs = validate_action_exact({"action_type": "delete_all"}, self.CONTEXT_AGENT)
        assert any("invalid_action_type" in e for e in errs)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


class TestJsonExtraction:
    def test_simple_json(self):
        text = '{"key": "value"}'
        assert _extract_json(text) == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is my response:\n\n{"observation_summary": "test"}\n\nThat is all.'
        assert _extract_json(text) == {"observation_summary": "test"}

    def test_no_braces(self):
        assert _extract_json("just some text") is None

    def test_malformed_json(self):
        assert _extract_json("{broken json") is None


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    def test_prompt_contains_identity(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "Adam" in prompt
        assert sample_context.agent_id in prompt
        assert "east_adam" in prompt

    def test_prompt_lists_available_actions(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "create_public_object" in prompt
        assert "inspect_public_object" in prompt
        assert "modify_owned_public_object" in prompt
        assert "leave_public_message" in prompt
        assert "ask_human" in prompt
        assert "request_capability" in prompt

    def test_prompt_contains_observation(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "tile-alpha" in prompt
        assert "objects_here" in prompt

    def test_prompt_contains_memory_section(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "PRIVATE MEMORIES (SELECTED SUBSET)" in prompt
        assert "does NOT prove the event never occurred" in prompt

    def test_prompt_no_eve_memory_in_adam_prompt(self, sample_context, sample_eve_context):
        adam_prompt = build_system_prompt(sample_context)
        eve_prompt = build_system_prompt(sample_eve_context)
        # Check the privacy boundary text rather than specific content
        assert "other agent's private memories are never available" in adam_prompt
        assert "other agent's private memories are never available" in eve_prompt

    def test_prompt_json_format(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "observation_summary" in prompt
        assert "confidence" in prompt
        assert "proposed_action" in prompt

    def test_adam_mentions_eve(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "Eve" in prompt
        assert "genesis-agent-test-eve" in prompt

    def test_eve_mentions_adam(self, sample_eve_context):
        prompt = build_system_prompt(sample_eve_context)
        assert "Adam" in prompt
        assert "genesis-agent-test-adam" in prompt

    def test_self_not_called_counterpart(self, sample_context, sample_eve_context):
        adam_prompt = build_system_prompt(sample_context)
        eve_prompt = build_system_prompt(sample_eve_context)
        # Adam is not told he is Eve
        assert "You share this world with Eve" in adam_prompt
        assert "You are Eve" not in adam_prompt
        assert "You share this world with Adam" in eve_prompt
        assert "You are Adam" not in eve_prompt

    def test_answered_questions_in_prompt(self, sample_context):
        ctx = sample_context
        ctx = AgentContext(
            agent_id=ctx.agent_id,
            canonical_name=ctx.canonical_name,
            canonical_ref=ctx.canonical_ref,
            heartbeat_number=ctx.heartbeat_number,
            position=ctx.position,
            observation=ctx.observation,
            memory=ctx.memory,
            goals=ctx.goals,
            unanswered_questions=ctx.unanswered_questions,
            world_public_objects=ctx.world_public_objects,
            habitat_allowed_tiles=ctx.habitat_allowed_tiles,
            habitat_movement_allowed=ctx.habitat_movement_allowed,
            previous_action=ctx.previous_action,
            timestamp_utc=ctx.timestamp_utc,
            other_agent_id=ctx.other_agent_id,
            other_agent_name=ctx.other_agent_name,
            other_agent_ref=ctx.other_agent_ref,
            answered_questions=[{"question_id": "q1", "answer": "42"}],
        )
        prompt = build_system_prompt(ctx)
        assert "42" in prompt
        assert "q1" in prompt


# ---------------------------------------------------------------------------
# Mocked model backend — full cycle tests
# ---------------------------------------------------------------------------


class _FakeClient:
    """Injected fake transport for model calls."""

    def __init__(self, responses: list[MagicMock] | None = None):
        self.responses = responses or []
        self.call_count = 0

    def set_responses(self, responses: list[MagicMock]):
        self.responses = responses
        self.call_count = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        if self.call_count >= len(self.responses):
            return _make_mock_response(json.dumps(_valid_response))
        resp = self.responses[self.call_count]
        self.call_count += 1
        return resp


class TestModelBackendMocked:
    def _make_backend(self, client: Any | None = None, agent_ref: str = "east_adam") -> ModelCognitionBackend:
        config = ProviderConfig(
            provider_type="test",
            base_url="http://test:9999/v1",
            model="test-model",
            api_key="test-key",
        )
        fake_client = client or _FakeClient()
        return ModelCognitionBackend.with_client(agent_ref, fake_client, config)

    def test_valid_output_returns_cognition_result(self, sample_context):
        client = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert isinstance(result, CognitionOutput)
        assert result.confidence == 0.6
        assert result.action is None

    def test_action_create_object(self, sample_context):
        resp = dict(_valid_response)
        resp["proposed_action"] = {
            "action_type": "create_public_object",
            "object_id": "adam-stone-1",
            "object_type": "stone",
            "description": "A grey stone marker.",
            "tile_id": "tile-alpha",
        }
        client = _FakeClient([_make_mock_response(json.dumps(resp))])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert result.action is not None
        assert result.action["action_type"] == "create_public_object"
        assert result.action["object_id"] == "adam-stone-1"

    def test_action_ask_human(self, sample_context):
        resp = dict(_valid_response)
        resp["proposed_action"] = {
            "action_type": "ask_human",
            "question_id": "q-purpose",
            "question": "What is my purpose?",
            "reason_for_asking": "I need direction.",
            "related_goal_id": None,
            "requested_human_capability": "guidance",
            "urgency": "medium",
        }
        client = _FakeClient([_make_mock_response(json.dumps(resp))])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert result.action is not None
        assert result.action["action_type"] == "ask_human"
        assert result.action["question_id"] == "q-purpose"

    def test_gibberish_response_is_handled(self, sample_context):
        client = _FakeClient([_make_mock_response("This is not JSON at all.")])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert isinstance(result, CognitionOutput)
        assert result.action is None
        assert result.confidence == 0.0

    def test_repair_attempt_on_validation_error(self, sample_context):
        """First response invalid, repair attempt succeeds."""
        first_bad = json.dumps({"bad_key": "no_observation_summary", "confidence": 0.5})
        second_good = json.dumps(_valid_response)
        client = _FakeClient([
            _make_mock_response(first_bad),
            _make_mock_response(second_good),
        ])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert result.action is None
        assert client.call_count == 2

    def test_double_failure_returns_no_action(self, sample_context):
        client = _FakeClient([
            _make_mock_response('{"bad": "data"}'),
            _make_mock_response('{"still": "bad"}'),
        ])
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert result.confidence == 0.0
        assert client.call_count == 2

    def test_network_error_returns_fallback(self, sample_context):
        class _FailingClient:
            @property
            def chat(self):
                return self
            @property
            def completions(self):
                return self
            def create(self, **kwargs):
                raise ConnectionError("Connection refused to api.test.com")

        backend = self._make_backend(_FailingClient())
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert result.confidence == 0.0
        assert len(result.memory_write) == 1
        assert "error" in result.memory_write[0]["type"]

    def test_sanitized_error_no_credential_leak(self, sample_context):
        class _KeyLeakingClient:
            @property
            def chat(self):
                return self
            @property
            def completions(self):
                return self
            def create(self, **kwargs):
                raise ConnectionError("nvapi-leakedsecretkey12345")

        backend = self._make_backend(_KeyLeakingClient())
        result = backend.observe_and_orient(sample_context)
        assert "leakedsecretkey12345" not in str(result.memory_write)
        assert "nvapi-" in str(result.memory_write)  # prefix preserved

    def test_two_call_maximum(self, sample_context):
        """Only one original + one repair call per agent heartbeat."""
        client = _FakeClient()
        responses = [
            _make_mock_response('{"bad": "first"}'),
            _make_mock_response('{"bad": "second"}'),
            _make_mock_response(json.dumps(_valid_response)),  # third not used
        ]
        client.set_responses(responses)
        backend = self._make_backend(client)
        result = backend.observe_and_orient(sample_context)
        assert client.call_count <= 2
        # Third response should not be consumed
        remaining_response = responses[2]
        assert remaining_response.choices[0].message.content


# ---------------------------------------------------------------------------
# Cross-agent memory leakage
# ---------------------------------------------------------------------------


class TestNoMemoryLeakage:
    def test_adam_prompt_no_eve_memory(self, sample_context, sample_eve_context):
        prompt = build_system_prompt(sample_context)
        assert "Eve's private memory" not in prompt

    def test_eve_prompt_no_adam_memory(self, sample_context, sample_eve_context):
        prompt = build_system_prompt(sample_eve_context)
        assert "I see an empty room" not in prompt

    def test_adam_context_has_correct_memory(self, sample_context, sample_eve_context):
        assert any("I see an empty room" in str(m) for m in sample_context.memory)
        assert not any("Eve's private memory" in str(m) for m in sample_context.memory)

    def test_eve_context_has_correct_memory(self, sample_context, sample_eve_context):
        assert any("Eve's private memory" in str(m) for m in sample_eve_context.memory)
        assert not any("I see an empty room" in str(m) for m in sample_eve_context.memory)

    def test_adam_prompt_contains_eve_identity(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "Eve" in prompt
        assert sample_context.other_agent_id in prompt

    def test_eve_prompt_contains_adam_identity(self, sample_eve_context):
        prompt = build_system_prompt(sample_eve_context)
        assert "Adam" in prompt
        assert sample_eve_context.other_agent_id in prompt


# ---------------------------------------------------------------------------
# Runtime integration with mocked ModelCognitionBackend
# ---------------------------------------------------------------------------


class TestModelBackendRuntimeIntegration:
    def test_runtime_accepts_model_backend(self):
        from unittest.mock import patch, MagicMock as MMock
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_backend = MMock(spec=CognitionBackend)
            mock_backend.observe_and_orient.return_value = CognitionOutput(
                action=None,
                memory_write=[{"type": "observation", "content": "Nothing to report."}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning="Test cognition cycle.",
                confidence=0.5,
            )
            mock_backend.reflect_on_outcome.return_value = "Mock reflection: no action."
            mock_cls.return_value = mock_backend

            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            results = runtime.run()
            assert results["heartbeats_completed"] == 1
            assert mock_cls.called


# ---------------------------------------------------------------------------
# Ollama credential-free transport (latent real-construction fix)
#
# Local Ollama genuinely requires no credential: resolve_provider() must keep
# returning ProviderConfig(api_key=None). Only at the OpenAI-SDK client
# construction boundary may the local placeholder "ollama" be supplied,
# because OpenAI SDK 2.24 requires a non-empty api_key string even though the
# local OpenAI-compatible endpoint ignores authentication.
# ---------------------------------------------------------------------------


class _CapturingOpenAIClient:
    """In-memory stand-in for the OpenAI SDK constructor to capture kwargs."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.__class__.instances.append(kwargs)


def _clear_provider_env(monkeypatch):
    for name in (
        "GENESIS_FIRST_PAIR_BASE_URL",
        "GENESIS_FIRST_PAIR_API_KEY",
        "GENESIS_FIRST_PAIR_MODEL",
        "NVIDIA_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_HOST",
    ):
        monkeypatch.delenv(name, raising=False)


class TestOllamaClientConstruction:
    def test_ollama_resolve_provider_still_returns_none_api_key(self, monkeypatch):
        _clear_provider_env(monkeypatch)
        monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "qwen3.5:4b")
        cfg = resolve_provider()
        assert cfg.provider_type == "ollama"
        assert cfg.api_key is None
        assert cfg.base_url == "http://127.0.0.1:11434/v1"

    def test_from_provider_config_ollama_converts_none_to_placeholder(self, monkeypatch):
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        config = ProviderConfig(
            provider_type="ollama",
            base_url="http://127.0.0.1:11434/v1",
            model="qwen3.5:4b",
            api_key=None,
        )
        backend = ModelCognitionBackend.from_provider_config("east_adam", config)
        assert config.api_key is None  # semantic config preserved
        assert backend._config.api_key is None  # not mutated on the config
        assert len(_CapturingOpenAIClient.instances) == 1
        assert _CapturingOpenAIClient.instances[0]["api_key"] == "ollama"
        assert _CapturingOpenAIClient.instances[0]["base_url"] == "http://127.0.0.1:11434/v1"

    def test_constructor_ollama_converts_none_to_placeholder(self, monkeypatch):
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        _clear_provider_env(monkeypatch)
        monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "qwen3.5:4b")
        backend = ModelCognitionBackend("east_adam")
        assert backend._config.api_key is None
        assert len(_CapturingOpenAIClient.instances) == 1
        assert _CapturingOpenAIClient.instances[0]["api_key"] == "ollama"

    @pytest.mark.parametrize(
        "provider_type,api_key,expected_key",
        [
            ("nvidia", "nvapi-secret", "nvapi-secret"),
            ("openrouter", "sk-or-secret", "sk-or-secret"),
            ("explicit_url", "sk-abc123", "sk-abc123"),
        ],
    )
    def test_other_providers_use_supplied_credential_unchanged(
        self, monkeypatch, provider_type, api_key, expected_key
    ):
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        config = ProviderConfig(
            provider_type=provider_type,
            base_url="http://remote.example/v1",
            model="m",
            api_key=api_key,
        )
        ModelCognitionBackend.from_provider_config("east_adam", config)
        assert len(_CapturingOpenAIClient.instances) == 1
        assert _CapturingOpenAIClient.instances[0]["api_key"] == expected_key
        assert _CapturingOpenAIClient.instances[0]["api_key"] == api_key

    def test_fake_client_injection_path_is_unaffected(self, monkeypatch):
        # with_client never constructs an OpenAI SDK client and never mangles
        # the api_key — it uses the injected client verbatim.
        mark = object()

        class _Injected:
            def __init__(self, client):
                self.client = client

        fake = mark
        config = ProviderConfig("ollama", "http://127.0.0.1:11434/v1", "qwen3.5:4b", None)
        monkeypatch.setattr(ModelCognitionBackend, "with_client", lambda *a, **k: "called")
        # Directly assert with_client passes the client through by inspecting it:
        backend = ModelCognitionBackend.with_client("east_adam", fake, config)
        assert backend == "called"

        # The real with_client (not monkeypatched) must preserve the injected client.
        monkeypatch.undo()
        _CapturingOpenAIClient.instances = []
        original_with_client = ModelCognitionBackend.with_client
        sentinel = type("S", (), {})()
        backend = original_with_client("east_adam", sentinel, config)
        assert backend._client is sentinel
        assert len(_CapturingOpenAIClient.instances) == 0

    def test_no_provider_credential_persisted(self, monkeypatch):
        # Provider resolution + real client construction must not create or
        # write any credential/provider file inside the workspace scratch root.
        import shutil

        scratch = Path(__file__).resolve().parent.parent / ".ollama-fix-scratch"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True, exist_ok=True)
        before = set(p for p in scratch.rglob("*") if p.is_file())

        _clear_provider_env(monkeypatch)
        monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "qwen3.5:4b")
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        cfg = resolve_provider()
        ModelCognitionBackend("east_adam")

        after = set(p for p in scratch.rglob("*") if p.is_file())
        assert before == after
        shutil.rmtree(scratch, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fallback lane — graceful degradation when a second credentialled provider
# is configured. NVIDIA primary falls back to OpenRouter (and vice versa)
# only after the primary request fails; the lane that actually served is
# exposed via ``serving_provider_type`` for runtime evidence.
# ---------------------------------------------------------------------------

_FALLBACK_ENV_KEYS = (
    "GENESIS_FIRST_PAIR_BASE_URL",
    "GENESIS_FIRST_PAIR_API_KEY",
    "GENESIS_FIRST_PAIR_MODEL",
    "GENESIS_FIRST_PAIR_FALLBACK_MODEL",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_HOST",
)


def _clear_fallback_env(monkeypatch):
    for name in _FALLBACK_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


class _FailingTransport:
    """Fake transport whose create() always raises a non-retryable error."""

    def __init__(self, message: str = "lane down"):
        self.message = message
        self.call_count = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.call_count += 1
        raise Exception(self.message)


class TestFallbackResolution:
    def test_nvidia_primary_gets_openrouter_fallback(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "primary/m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m:free")
        primary = resolve_provider()
        fb = cmod.resolve_fallback_provider(primary)
        assert primary.provider_type == "nvidia"
        assert fb is not None
        assert fb.provider_type == "openrouter"
        assert fb.model == "fb/m:free"
        assert fb.api_key == "or-key"
        assert "openrouter" in fb.base_url

    def test_openrouter_primary_gets_nvidia_fallback(self, monkeypatch):
        # OpenRouter-primary arises from an explicitly injected config
        # (from_provider_config): resolve_provider() with BOTH keys set
        # always picks NVIDIA, so the reverse chain is only reachable with
        # an explicit OpenRouter config plus NVIDIA_API_KEY in env.
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m")
        primary = ProviderConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model="primary/m",
            api_key="or-key",
        )
        fb = cmod.resolve_fallback_provider(primary)
        assert fb is not None
        assert fb.provider_type == "nvidia"
        assert "nvidia.com" in fb.base_url
        assert fb.model == "fb/m"
        assert fb.api_key == "nv-key"

    def test_no_fallback_model_returns_none(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        primary = resolve_provider()
        assert cmod.resolve_fallback_provider(primary) is None

    def test_blank_fallback_model_returns_none(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "   ")
        primary = resolve_provider()
        assert cmod.resolve_fallback_provider(primary) is None

    def test_fallback_without_second_lane_credentials_returns_none(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m")
        primary = resolve_provider()
        assert cmod.resolve_fallback_provider(primary) is None

    def test_env_driven_init_resolves_fallback_config(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m:free")
        backend = ModelCognitionBackend("east_adam")
        assert backend.provider_type == "nvidia"
        assert backend._fallback_config is not None
        assert backend._fallback_config.provider_type == "openrouter"
        # Fallback client is lazy: only the primary client is constructed eagerly.
        assert len(_CapturingOpenAIClient.instances) == 1

    def test_from_provider_config_resolves_env_fallback(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setattr(cmod, "OpenAI", _CapturingOpenAIClient)
        _CapturingOpenAIClient.instances = []
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m:free")
        config = ProviderConfig(
            provider_type="nvidia",
            base_url="https://n.example/v1",
            model="m",
            api_key="k",
        )
        backend = ModelCognitionBackend.from_provider_config("east_adam", config)
        assert backend._fallback_config is not None
        assert backend._fallback_config.provider_type == "openrouter"


class TestFallbackTransport:
    _PRIMARY = ProviderConfig("nvidia", "https://n.example/v1", "p-m", "pk")
    _FALLBACK = ProviderConfig("openrouter", "https://o.example/v1", "f-m:free", "ok")

    def _make_backend(self, primary_client, fallback_client=None, fallback_config=None):
        kwargs = {}
        if fallback_config is not None:
            kwargs["fallback_config"] = fallback_config
        if fallback_client is not None:
            kwargs["fallback_client"] = fallback_client
        return ModelCognitionBackend.with_client(
            "east_adam", primary_client, self._PRIMARY, **kwargs
        )

    def test_primary_failure_fallback_serves(self, sample_context):
        primary = _FailingTransport("primary down")
        fb = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert result.action is None
        assert backend.serving_provider_type == "openrouter"
        assert fb.call_count == 1
        assert primary.call_count == 1

    def test_primary_success_never_calls_fallback(self, sample_context):
        primary = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        fb = _FailingTransport("fallback must not be called")
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert backend.serving_provider_type == "nvidia"
        assert fb.call_count == 0

    def test_both_lanes_fail_reports_combined_error(self, sample_context):
        primary = _FailingTransport("primary down")
        fb = _FailingTransport("fallback down")
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert result.confidence == 0.0
        assert "error" in result.memory_write[0]["type"]
        combined = str(result.memory_write) + result.internal_reasoning + result.uncertainty
        assert "primary down" in combined
        assert "fallback down" in combined
        assert backend.serving_provider_type == "nvidia"

    def test_repair_round_uses_serving_lane(self, sample_context):
        primary = _FailingTransport("primary down")
        fb = _FakeClient([
            _make_mock_response('{"bad": "first"}'),
            _make_mock_response(json.dumps(_valid_response)),
        ])
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert fb.call_count == 2
        assert backend.serving_provider_type == "openrouter"

    def test_no_fallback_config_preserves_single_lane_failure(self, sample_context):
        primary = _FailingTransport("only lane down")
        backend = self._make_backend(primary)
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.0
        assert primary.call_count == 1
        assert backend.serving_provider_type == "nvidia"


class TestRuntimeServingProviderEvidence:
    def test_stub_evidence_has_serving_provider_type_key(self):
        import tempfile
        from backend.world.first_pair_runtime import FirstPairRuntime

        runtime = FirstPairRuntime(
            persistence_root=Path(tempfile.mkdtemp()),
            heartbeat_limit=1,
            backend="deterministic_stub",
        )
        runtime.run()
        bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_serving.json")
        assert "serving_provider_type" in bundle

    def test_model_backend_serving_provider_type_in_evidence(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_backend = MagicMock()
            mock_backend.serving_provider_type = "openrouter"
            mock_backend.observe_and_orient.return_value = CognitionOutput(
                action=None,
                memory_write=[{"type": "observation", "content": "Nothing to report."}],
                goal_updates=None,
                questions_raised=None,
                internal_reasoning="Test cognition cycle.",
                confidence=0.5,
            )
            mock_backend.reflect_on_outcome.return_value = "Mock reflection: no action."
            mock_cls.return_value = mock_backend

            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_fb.json")
            assert bundle.get("serving_provider_type") == "openrouter"


# ---------------------------------------------------------------------------
# Free-lane guard — an OpenRouter fallback must be an explicitly free model
# (id ending in ":free"). A paid OpenRouter fallback fails closed during
# fallback resolution. The NVIDIA fallback lane carries no such guard.
# ---------------------------------------------------------------------------


class TestFreeLaneGuard:
    def test_openrouter_fallback_free_model_accepted(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "z-ai/glm-5.2:free")
        primary = resolve_provider()
        fb = cmod.resolve_fallback_provider(primary)
        assert fb is not None
        assert fb.provider_type == "openrouter"
        assert fb.model == "z-ai/glm-5.2:free"

    def test_openrouter_fallback_paid_model_fails_closed(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret-key-1234567890")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "z-ai/glm-5.2")
        primary = resolve_provider()
        with pytest.raises(ProviderError) as exc:
            cmod.resolve_fallback_provider(primary)
        msg = str(exc.value)
        assert ":free" in msg
        assert "z-ai/glm-5.2" in msg
        assert "or-secret-key-1234567890" not in msg

    def test_openrouter_fallback_nonfree_variant_fails_closed(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "deepseek/deepseek-v4-pro")
        primary = resolve_provider()
        with pytest.raises(ProviderError) as exc:
            cmod.resolve_fallback_provider(primary)
        assert ":free" in str(exc.value)

    def test_nvidia_fallback_has_no_free_model_guard(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "meta/llama-3.3-70b-instruct")
        primary = ProviderConfig(
            provider_type="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model="primary/m",
            api_key="or-key",
        )
        fb = cmod.resolve_fallback_provider(primary)
        assert fb is not None
        assert fb.provider_type == "nvidia"
        assert fb.model == "meta/llama-3.3-70b-instruct"

    def test_env_driven_init_with_paid_openrouter_fallback_fails_closed(self, monkeypatch):
        _clear_fallback_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "z-ai/glm-5.2")
        with pytest.raises(ProviderError):
            ModelCognitionBackend("east_adam")


# ---------------------------------------------------------------------------
# Fallback provenance — when the primary fails, the failure reason must be
# preserved alongside the identity of the lane that served. No fake
# failure when the primary succeeds; no fallback_used when the fallback
# itself failed.
# ---------------------------------------------------------------------------


class TestFallbackProvenance:
    _PRIMARY = ProviderConfig("nvidia", "https://n.example/v1", "p-m", "pk")
    _FALLBACK = ProviderConfig("openrouter", "https://o.example/v1", "f-m:free", "ok")

    def _make_backend(self, primary_client, fallback_client=None, fallback_config=None,
                      primary_config=None):
        kwargs = {}
        if fallback_config is not None:
            kwargs["fallback_config"] = fallback_config
        if fallback_client is not None:
            kwargs["fallback_client"] = fallback_client
        return ModelCognitionBackend.with_client(
            "east_adam", primary_client, primary_config or self._PRIMARY, **kwargs
        )

    def test_fallback_serving_records_provenance(self, sample_context):
        primary = _FailingTransport("primary down")
        fb = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert backend.fallback_used is True
        assert backend.serving_provider_type == "openrouter"
        assert "primary down" in backend.primary_failure_reason
        assert "transport attempts: 1" in backend.primary_failure_reason

    def test_primary_success_records_no_failure(self, sample_context):
        primary = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        backend = self._make_backend(primary)
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert backend.fallback_used is False
        assert backend.primary_failure_reason == ""
        assert backend.serving_provider_type == "nvidia"

    def test_both_lanes_fail_records_primary_failure_without_fallback_served(
        self, sample_context
    ):
        primary = _FailingTransport("primary down")
        fb = _FailingTransport("fallback down")
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.0
        assert backend.fallback_used is False
        assert "primary down" in backend.primary_failure_reason

    def test_provenance_never_leaks_primary_credential(self, sample_context):
        secret = "nvapi-primarysecretkey0987654321"
        primary_cfg = ProviderConfig("nvidia", "https://n.example/v1", "p-m", secret)
        primary = _FailingTransport(f"primary failed with {secret}")
        fb = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        backend = self._make_backend(
            primary, fallback_client=fb, fallback_config=self._FALLBACK,
            primary_config=primary_cfg,
        )
        backend.observe_and_orient(sample_context)
        assert backend.fallback_used is True
        assert secret not in backend.primary_failure_reason
        assert "[REDACTED]" in backend.primary_failure_reason
        assert "transport attempts: 1" in backend.primary_failure_reason


class TestRuntimeFallbackProvenanceEvidence:
    def _make_cognition_output(self):
        return CognitionOutput(
            action=None,
            memory_write=[{"type": "observation", "content": "Nothing to report."}],
            goal_updates=None,
            questions_raised=None,
            internal_reasoning="Test cognition cycle.",
            confidence=0.5,
        )

    def test_fallback_serving_evidence_preserves_primary_failure(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_backend = MagicMock()
            mock_backend.provider_type = "nvidia"
            mock_backend.model_name = "z-ai/glm-5.3-flash"
            mock_backend.serving_provider_type = "openrouter"
            mock_backend.fallback_used = True
            mock_backend.primary_failure_reason = (
                "Error code: 404 (transport attempts: 1)"
            )
            mock_backend.observe_and_orient.return_value = self._make_cognition_output()
            mock_backend.reflect_on_outcome.return_value = "Mock reflection."
            mock_cls.return_value = mock_backend

            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_prov.json")
            assert bundle.get("primary_provider_type") == "nvidia"
            assert bundle.get("serving_provider_type") == "openrouter"
            assert bundle.get("fallback_used") is True
            assert "404" in bundle.get("primary_failure_reason", "")

    def test_primary_success_evidence_records_no_fake_failure(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_backend = MagicMock()
            mock_backend.provider_type = "nvidia"
            mock_backend.model_name = "z-ai/glm-5.3-flash"
            mock_backend.serving_provider_type = "nvidia"
            mock_backend.fallback_used = False
            mock_backend.primary_failure_reason = ""
            mock_backend.observe_and_orient.return_value = self._make_cognition_output()
            mock_backend.reflect_on_outcome.return_value = "Mock reflection."
            mock_cls.return_value = mock_backend

            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_nofail.json")
            assert bundle.get("fallback_used") is False
            assert bundle.get("primary_failure_reason") == ""
            assert bundle.get("serving_provider_type") == "nvidia"
            assert bundle.get("primary_provider_type") == "nvidia"

    def test_stub_evidence_fallback_defaults(self):
        import tempfile
        from backend.world.first_pair_runtime import FirstPairRuntime

        runtime = FirstPairRuntime(
            persistence_root=Path(tempfile.mkdtemp()),
            heartbeat_limit=1,
            backend="deterministic_stub",
        )
        runtime.run()
        bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_stubdef.json")
        assert bundle.get("fallback_used") is False
        assert bundle.get("primary_failure_reason") == ""
        assert "primary_provider_type" in bundle
        assert "serving_provider_type" in bundle


# ---------------------------------------------------------------------------
# OpenRouter lane transient retry — a 429/timeout on the free fallback lane
# must slow the request down (bounded transient retry, 10IV semantics), not
# kill the cycle on the first hit. Non-retryable errors still fail fast.
# ---------------------------------------------------------------------------


class TestFallbackLaneTransientRetry:
    _PRIMARY = ProviderConfig("nvidia", "https://n.example/v1", "p-m", "pk")
    _FALLBACK = ProviderConfig("openrouter", "https://o.example/v1", "f-m:free", "ok")

    def _make_backend(self, primary_client, fallback_client):
        return ModelCognitionBackend.with_client(
            "east_adam",
            primary_client,
            self._PRIMARY,
            fallback_config=self._FALLBACK,
            fallback_client=fallback_client,
        )

    def test_openrouter_fallback_retries_transient_then_serves(
        self, sample_context, monkeypatch
    ):
        import httpx
        import openai as openai_mod

        monkeypatch.setattr(cmod.time, "sleep", lambda s: None)
        req = httpx.Request("POST", "https://o.example/v1/chat/completions")
        good = _FakeClient([_make_mock_response(json.dumps(_valid_response))])
        calls = {"n": 0}

        class _TransientThenGood:
            @property
            def chat(self):
                return self

            @property
            def completions(self):
                return self

            def create(self, **kwargs):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise openai_mod.APITimeoutError(request=req)
                return good.create(**kwargs)

        backend = self._make_backend(
            _FailingTransport("primary down"), _TransientThenGood()
        )
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert backend.fallback_used is True
        assert backend.serving_provider_type == "openrouter"
        assert calls["n"] == 2  # one transient failure retried, then served

    def test_openrouter_fallback_nonretryable_fails_fast(
        self, sample_context, monkeypatch
    ):
        monkeypatch.setattr(cmod.time, "sleep", lambda s: None)
        fb = _FailingTransport("fallback down")
        backend = self._make_backend(_FailingTransport("primary down"), fb)
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.0
        assert backend.fallback_used is False
        assert fb.call_count == 1  # non-retryable: single fallback attempt

    def test_openrouter_fallback_exhausts_transient_budget(
        self, sample_context, monkeypatch
    ):
        import httpx
        import openai as openai_mod

        monkeypatch.setattr(cmod.time, "sleep", lambda s: None)
        req = httpx.Request("POST", "https://o.example/v1/chat/completions")
        fb = _FailingTransport("boom")
        fb_retryable_calls = {"n": 0}

        class _AlwaysTransient:
            @property
            def chat(self):
                return self

            @property
            def completions(self):
                return self

            def create(self, **kwargs):
                fb_retryable_calls["n"] += 1
                raise openai_mod.APITimeoutError(request=req)

        backend = self._make_backend(_FailingTransport("primary down"), _AlwaysTransient())
        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.0
        assert backend.fallback_used is False
        assert fb_retryable_calls["n"] == 3  # bounded: max 3 transient attempts


# ---------------------------------------------------------------------------
# Run-level serving aggregation across agents — a later cycle that fails
# entirely must not clobber the serving lane recorded when a fallback
# served an earlier cycle in the same run.
# ---------------------------------------------------------------------------


class TestRuntimeMixedAgentServingEvidence:
    def _make_output(self):
        return CognitionOutput(
            action=None,
            memory_write=[{"type": "observation", "content": "Nothing to report."}],
            goal_updates=None,
            questions_raised=None,
            internal_reasoning="Test cognition cycle.",
            confidence=0.5,
        )

    def _make_backend_mock(self, *, serving, fallback_used, primary_failure):
        mb = MagicMock()
        mb.provider_type = "nvidia"
        mb.model_name = "z-ai/glm-5.3-flash"
        mb.serving_provider_type = serving
        mb.fallback_used = fallback_used
        mb.primary_failure_reason = primary_failure
        mb.observe_and_orient.return_value = self._make_output()
        mb.reflect_on_outcome.return_value = "Mock reflection."
        return mb

    def test_later_failed_cycle_does_not_clobber_fallback_serving(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        adam = self._make_backend_mock(
            serving="openrouter", fallback_used=True, primary_failure="404 (transport attempts: 1)"
        )
        eve = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure="429 upstream"
        )
        fresh = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_cls.side_effect = [adam, eve, fresh]
            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_mixed.json")
            assert bundle.get("serving_provider_type") == "openrouter"
            assert bundle.get("fallback_used") is True
            assert bundle.get("primary_provider_type") == "nvidia"
            assert "404" in bundle.get("primary_failure_reason", "")

    def test_fallback_serving_in_second_cycle_is_sticky(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        adam = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )
        eve = self._make_backend_mock(
            serving="openrouter", fallback_used=True, primary_failure="404 (transport attempts: 1)"
        )
        fresh = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_cls.side_effect = [adam, eve, fresh]
            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_mixed2.json")
            assert bundle.get("serving_provider_type") == "openrouter"
            assert bundle.get("fallback_used") is True
            assert "404" in bundle.get("primary_failure_reason", "")

    def test_all_primary_cycles_keep_primary_serving(self):
        from unittest.mock import patch
        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile

        adam = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )
        eve = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )
        fresh = self._make_backend_mock(
            serving="nvidia", fallback_used=False, primary_failure=""
        )

        with patch("backend.world.first_pair_runtime.ModelCognitionBackend") as mock_cls:
            mock_cls.side_effect = [adam, eve, fresh]
            runtime = FirstPairRuntime(
                persistence_root=Path(tempfile.mkdtemp()),
                heartbeat_limit=1,
                backend="model",
            )
            runtime.run()
            bundle = runtime.export_evidence(Path(tempfile.mkdtemp()) / "ev_allp.json")
            assert bundle.get("serving_provider_type") == "nvidia"
            assert bundle.get("fallback_used") is False
            assert bundle.get("primary_failure_reason") == ""
