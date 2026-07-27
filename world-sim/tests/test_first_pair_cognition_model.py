"""Tests for the model-backed First Pair cognition backend.

Uses a mocked OpenAI client to avoid actual network calls.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.world.first_pair_cognition_interface import (
    AgentContext,
    CognitionBackend,
    CognitionOutput,
)
from backend.world.first_pair_cognition_model import (
    ModelCognitionBackend,
    _is_safe_id,
    _resolve_provider,
    _validate_model_output,
    build_system_prompt,
)
from backend.world.first_pair_cognition_stub import (
    DeterministicStubBackend,
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
    )


def _make_mock_response(content: str) -> MagicMock:
    """Build a mock OpenAI chat completion response."""
    choice = MagicMock()
    choice.message.content = content
    choice.message.role = "assistant"
    mock_resp = MagicMock()
    mock_resp.choices = [choice]
    return mock_resp


# ---------------------------------------------------------------------------
# Provider resolution tests
# ---------------------------------------------------------------------------


class TestProviderResolution:
    def test_env_vars_take_precedence(self):
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "https://custom.example.com"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "custom-key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "custom-model"
        try:
            cfg = _resolve_provider()
            assert cfg["base_url"] == "https://custom.example.com/v1"
            assert cfg["api_key"] == "custom-key"
            assert cfg["model"] == "custom-model"
        finally:
            for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                      "GENESIS_FIRST_PAIR_MODEL", "OLLAMA_HOST"):
                os.environ.pop(k, None)

    def test_nvidia_fallback(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "OLLAMA_HOST"):
            os.environ.pop(k, None)
        os.environ["NVIDIA_API_KEY"] = "nv-key"
        try:
            cfg = _resolve_provider()
            assert "nvidia.com" in cfg["base_url"]
            assert cfg["api_key"] == "nv-key"
        finally:
            os.environ.pop("NVIDIA_API_KEY", None)

    def test_ollama_fallback(self):
        for k in ("GENESIS_FIRST_PAIR_BASE_URL", "GENESIS_FIRST_PAIR_API_KEY",
                  "GENESIS_FIRST_PAIR_MODEL", "NVIDIA_API_KEY", "OPENROUTER_API_KEY",
                  "OLLAMA_HOST"):
            os.environ.pop(k, None)
        cfg = _resolve_provider()
        assert "localhost" in cfg["base_url"]
        assert cfg["api_key"] is None


# ---------------------------------------------------------------------------
# Safe ID validation
# ---------------------------------------------------------------------------


class TestSafeId:
    def test_valid_ids(self):
        for vid in ("abc123", "goal_explore", "object.a-1", "a"):
            assert _is_safe_id(vid), f"Expected valid: {vid}"

    def test_invalid_ids(self):
        for iid in ("", "a" * 129, "hello world", "obj/123", "obj\nid", None, 42):
            if iid is not None:
                assert not _is_safe_id(iid), f"Expected invalid: {iid}"
            assert not _is_safe_id("")


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------


class TestOutputValidation:
    def test_valid_minimal_output(self):
        raw = {
            "observation_summary": "I see an empty room.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "uncertainty": "Nothing yet.",
            "decision_summary": "Wait and observe.",
            "confidence": 0.5,
        }
        result = _validate_model_output(raw)
        assert result.is_valid, f"Expected valid: {result.validation_errors}"

    def test_missing_observation_summary(self):
        raw = {
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "confidence": 0.0,
        }
        result = _validate_model_output(raw)
        assert not result.is_valid
        assert any("observation_summary" in e for e in result.validation_errors)

    def test_contaminated_text_rejected(self):
        raw = {
            "observation_summary": "I see the secret true_map tokens.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "confidence": 0.0,
        }
        result = _validate_model_output(raw)
        assert not result.is_valid
        assert any("contaminated" in e for e in result.validation_errors)

    def test_valid_action_create(self):
        raw = {
            "observation_summary": "Empty room.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "proposed_action": {
                "action_type": "create_public_object",
                "object_id": "adam-stone-1",
                "object_type": "stone",
                "description": "A small grey stone.",
                "tile_id": "tile-alpha",
            },
            "confidence": 0.8,
        }
        result = _validate_model_output(raw)
        assert result.is_valid, f"Expected valid: {result.validation_errors}"
        assert result.proposed_action is not None
        assert result.proposed_action.action_type == "create_public_object"

    def test_valid_action_ask_human(self):
        raw = {
            "observation_summary": "Need help.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "proposed_action": {
                "action_type": "ask_human",
                "question_id": "q-what-am-i",
                "question": "What am I?",
                "reason_for_asking": "I seek my purpose.",
                "requested_human_capability": "answer_philosophical",
                "urgency": "high",
            },
            "confidence": 0.9,
        }
        result = _validate_model_output(raw)
        assert result.is_valid, f"Expected valid: {result.validation_errors}"

    def test_invalid_confidence_range(self):
        raw = {
            "observation_summary": "Test.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "confidence": 5.0,
        }
        result = _validate_model_output(raw)
        assert result.is_valid  # Confidence is not required; invalid values are dropped
        assert result.confidence == 0.0  # default

    def test_unsafe_goal_id_rejected(self):
        raw = {
            "observation_summary": "Test.",
            "goal_updates": [
                {
                    "goal_id": "../secret",
                    "agent_id": "test",
                    "description": "hack",
                    "status": "active",
                }
            ],
            "memory_candidates": [],
            "questions_for_humans": [],
            "confidence": 0.5,
        }
        result = _validate_model_output(raw)
        assert not result.is_valid
        assert any("unsafe_goal_id" in e for e in result.validation_errors)

    def test_invalid_urgency_rejected(self):
        raw = {
            "observation_summary": "Test.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [
                {
                    "question_id": "q-test",
                    "question": "Why?",
                    "reason_for_asking": "Curiosity.",
                    "urgency": "critical",
                }
            ],
            "confidence": 0.5,
        }
        result = _validate_model_output(raw)
        assert not result.is_valid
        assert any("invalid_urgency" in e for e in result.validation_errors)

    def test_invalid_action_type(self):
        raw = {
            "observation_summary": "Test.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "proposed_action": {
                "action_type": "delete_everything",
            },
            "confidence": 0.5,
        }
        result = _validate_model_output(raw)
        assert not result.is_valid
        assert any("invalid_or_unknown_action" in e for e in result.validation_errors)

    def test_no_action_is_valid(self):
        raw = {
            "observation_summary": "Nothing to do.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "proposed_action": {
                "action_type": "no_action",
            },
            "confidence": 1.0,
        }
        result = _validate_model_output(raw)
        assert result.is_valid
        assert result.proposed_action is not None
        assert result.proposed_action.action_type == "no_action"

    def test_valid_move_action(self):
        raw = {
            "observation_summary": "I want to move.",
            "goal_updates": [],
            "memory_candidates": [],
            "questions_for_humans": [],
            "proposed_action": {
                "action_type": "move",
                "target_tile": "tile-beta",
                "reason": "Exploring",
            },
            "confidence": 0.7,
        }
        result = _validate_model_output(raw)
        assert result.is_valid
        assert result.proposed_action.action_type == "move"
        assert result.proposed_action.target_tile == "tile-beta"


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


class TestJsonExtraction:
    def test_simple_json(self):
        text = '{"key": "value"}'
        assert ModelCognitionBackend._extract_json(text) == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is my response:\n\n{"observation_summary": "test"}\n\nThat is all.'
        assert ModelCognitionBackend._extract_json(text) == {"observation_summary": "test"}

    def test_no_braces(self):
        assert ModelCognitionBackend._extract_json("just some text") is None

    def test_malformed_json(self):
        assert ModelCognitionBackend._extract_json("{broken json") is None


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
        assert "empty room" in prompt

    def test_prompt_contains_memory(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "I see an empty room" in prompt

    def test_prompt_no_eve_memory_in_adam_prompt(self, sample_context, sample_eve_context):
        adam_prompt = build_system_prompt(sample_context)
        eve_prompt = build_system_prompt(sample_eve_context)
        assert "Eve's private memory" not in adam_prompt
        assert "Eve's private memory" in eve_prompt

    def test_prompt_json_format(self, sample_context):
        prompt = build_system_prompt(sample_context)
        assert "observation_summary" in prompt
        assert "confidence" in prompt
        assert "proposed_action" in prompt


# ---------------------------------------------------------------------------
# Mocked model backend — full cycle tests
# ---------------------------------------------------------------------------


class TestModelBackendMocked:
    def _make_backend(self) -> ModelCognitionBackend:
        for k in ("OLLAMA_HOST", "NVIDIA_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "http://localhost:99999"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "test-key"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "test-model"
        backend = ModelCognitionBackend("east_adam")
        return backend

    def _make_valid_response(self) -> dict:
        return {
            "observation_summary": "I see an empty tile with no objects.",
            "goal_updates": [],
            "memory_candidates": [
                {"type": "observation", "content": "Tile-alpha is empty."}
            ],
            "questions_for_humans": [],
            "uncertainty": "Whether any other agents exist nearby.",
            "decision_summary": "Chose no_action because there is nothing to interact with.",
            "confidence": 0.6,
        }

    def test_valid_output_returns_cognition_result(self, sample_context):
        backend = self._make_backend()
        backend._client.chat.completions.create = MagicMock(
            return_value=_make_mock_response(json.dumps(self._make_valid_response()))
        )
        result = backend.observe_and_orient(sample_context)
        assert isinstance(result, CognitionOutput)
        assert result.confidence == 0.6
        assert len(result.memory_write) == 1
        assert result.memory_write[0]["type"] == "observation"

    def test_action_create_object(self, sample_context):
        backend = self._make_backend()
        resp = self._make_valid_response()
        resp["proposed_action"] = {
            "action_type": "create_public_object",
            "object_id": "adam-stone-1",
            "object_type": "stone",
            "description": "A grey stone marker.",
            "tile_id": "tile-alpha",
        }
        backend._client.chat.completions.create = MagicMock(
            return_value=_make_mock_response(json.dumps(resp))
        )
        result = backend.observe_and_orient(sample_context)
        assert result.action is not None
        assert result.action["action_type"] == "create_public_object"
        assert result.action["object_id"] == "adam-stone-1"

    def test_action_ask_human(self, sample_context):
        backend = self._make_backend()
        resp = self._make_valid_response()
        resp["proposed_action"] = {
            "action_type": "ask_human",
            "question_id": "q-purpose",
            "question": "What is my purpose?",
            "reason_for_asking": "I need direction.",
            "requested_human_capability": "philosophical_guidance",
            "urgency": "medium",
        }
        resp["questions_for_humans"] = [
            {
                "question_id": "q-purpose",
                "question": "What is my purpose?",
                "reason_for_asking": "I need direction.",
                "requested_human_capability": "philosophical_guidance",
                "urgency": "medium",
            }
        ]
        backend._client.chat.completions.create = MagicMock(
            return_value=_make_mock_response(json.dumps(resp))
        )
        result = backend.observe_and_orient(sample_context)
        assert result.action is not None
        assert result.action["action_type"] == "ask_human"
        assert result.action["question_id"] == "q-purpose"
        assert result.questions_raised is not None
        assert len(result.questions_raised) == 1

    def test_gibberish_response_is_handled(self, sample_context):
        backend = self._make_backend()
        backend._client.chat.completions.create = MagicMock(
            return_value=_make_mock_response("This is not JSON at all. Nothing useful here.")
        )
        result = backend.observe_and_orient(sample_context)
        assert isinstance(result, CognitionOutput)
        assert result.action is None
        assert result.confidence == 0.0

    def test_repair_attempt_on_validation_error(self, sample_context):
        """First response invalid, repair attempt succeeds."""
        backend = self._make_backend()
        first_bad = json.dumps({"bad_key": "no_observation_summary", "confidence": 0.5})
        second_good = json.dumps(self._make_valid_response())

        mock_create = MagicMock()
        mock_create.side_effect = [
            _make_mock_response(first_bad),
            _make_mock_response(second_good),
        ]
        backend._client.chat.completions.create = mock_create

        result = backend.observe_and_orient(sample_context)
        assert result.confidence == 0.6
        assert result.action is None  # no_action
        assert mock_create.call_count == 2

    def test_double_failure_returns_no_action(self, sample_context):
        backend = self._make_backend()
        mock_create = MagicMock()
        mock_create.side_effect = [
            _make_mock_response('{"bad": "data"}'),
            _make_mock_response('{"still": "bad"}'),
        ]
        backend._client.chat.completions.create = mock_create

        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert result.confidence == 0.0
        assert mock_create.call_count == 2

    def test_network_error_returns_fallback(self, sample_context):
        backend = self._make_backend()
        backend._client.chat.completions.create = MagicMock(
            side_effect=ConnectionError("Connection refused")
        )
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert result.confidence == 0.0
        assert len(result.memory_write) == 1
        assert "error" in result.memory_write[0]["type"]


# ---------------------------------------------------------------------------
# Cross-agent memory leakage test
# ---------------------------------------------------------------------------


class TestNoMemoryLeakage:
    """Adam's model request must never contain Eve's private memory and vice versa."""

    def _make_backend(self, agent_ref: str) -> ModelCognitionBackend:
        for k in ("OLLAMA_HOST", "NVIDIA_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(k, None)
        os.environ["GENESIS_FIRST_PAIR_BASE_URL"] = "http://localhost:99998"
        os.environ["GENESIS_FIRST_PAIR_API_KEY"] = "test-key-2"
        os.environ["GENESIS_FIRST_PAIR_MODEL"] = "test-model-2"
        return ModelCognitionBackend(agent_ref)

    def test_adam_prompt_no_eve_memory(self, sample_context, sample_eve_context):
        """Adam's system prompt must not contain Eve's memory."""
        backend = self._make_backend("east_adam")
        prompt = build_system_prompt(sample_context)
        assert "Eve's private memory" not in prompt

    def test_eve_prompt_no_adam_memory(self, sample_context, sample_eve_context):
        backend = self._make_backend("east_eve")
        prompt = build_system_prompt(sample_eve_context)
        assert "I see an empty room" not in prompt

    def test_adam_context_has_correct_memory(self, sample_context, sample_eve_context):
        assert any("I see an empty room" in str(m) for m in sample_context.memory)
        assert not any("Eve's private memory" in str(m) for m in sample_context.memory)

    def test_eve_context_has_correct_memory(self, sample_context, sample_eve_context):
        assert any("Eve's private memory" in str(m) for m in sample_eve_context.memory)
        assert not any("I see an empty room" in str(m) for m in sample_eve_context.memory)


# ---------------------------------------------------------------------------
# Model output integration with runtime
# ---------------------------------------------------------------------------


class TestModelBackendRuntimeIntegration:
    @patch("backend.world.first_pair_runtime.ModelCognitionBackend")
    def test_runtime_accepts_model_backend(self, mock_backend_cls):
        mock_backend = MagicMock(spec=CognitionBackend)
        mock_backend.observe_and_orient.return_value = CognitionOutput(
            action=None,
            memory_write=[{"type": "observation", "content": "Nothing to report."}],
            goal_updates=None,
            questions_raised=None,
            internal_reasoning="Test cognition cycle.",
            confidence=0.5,
        )
        mock_backend.reflect_on_outcome.return_value = "Mock reflection: no action taken."
        mock_backend_cls.return_value = mock_backend

        from backend.world.first_pair_runtime import FirstPairRuntime
        import tempfile
        runtime = FirstPairRuntime(
            persistence_root=Path(tempfile.mkdtemp()),
            heartbeat_limit=1,
            backend="model",
        )
        results = runtime.run()
        assert results["heartbeats_completed"] == 1
        assert mock_backend_cls.called
