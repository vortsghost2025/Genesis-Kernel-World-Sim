"""Phase 10IV — transport retry tests for the first-pair cognition backend.

Proves the bounded NVIDIA transport retry (10IV) fails closed and exactly as
specified:
- timeout -> retry -> success
- timeout -> timeout -> timeout -> fail closed (max 3 attempts)
- non-retryable 4xx -> exactly one attempt
- successful first response -> exactly one attempt
- valid cognition with proposed_action=null -> exactly one attempt, no
  re-request (a legitimate no-op is never retried)
- no secret leakage in recorded errors
- non-NVIDIA lanes get no retry
- transport retry and JSON repair compose within one shared budget
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import httpx
import pytest
from openai import APIStatusError, APITimeoutError

import backend.world.first_pair_cognition_model as fpcm
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import ModelCognitionBackend, ProviderConfig

FAKE_KEY = "nvapi-FAKE-SECRET-TEST-123"


def _ctx() -> AgentContext:
    return AgentContext(
        agent_id="genesis-agent-test",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=1,
        position="public-start-adam",
        observation={},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["public-start-adam"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-09-16T00:00:00Z",
    )


def _valid_payload(action=None) -> str:
    return json.dumps({
        "observation_summary": "test observation",
        "self_model_update": "test update",
        "goal_updates": [],
        "proposed_action": action,
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "low",
        "decision_summary": "test decision",
        "confidence": 0.9,
    })


class _Msg:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class FakeCompletions:
    def __init__(self, script: list[str]):
        self._script = list(script)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        behavior = self._script.pop(0) if self._script else "ok"
        req = httpx.Request("POST", "https://test.invalid/v1/chat/completions")
        if behavior == "raise_timeout":
            raise APITimeoutError(req)
        if behavior == "raise_404":
            raise APIStatusError(
                "not found", response=httpx.Response(404, request=req), body=None
            )
        if behavior == "raise_5xx":
            raise APIStatusError(
                "server error", response=httpx.Response(503, request=req), body=None
            )
        if behavior == "raise_secret":
            raise RuntimeError(f"connection dead with key={FAKE_KEY}")
        return _Resp(_valid_payload())


class FakeChat:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions

    @property
    def chat(self) -> "FakeChat":
        return self


def _backend(script: list[str], provider: str = "nvidia") -> tuple[ModelCognitionBackend, FakeCompletions]:
    completions = FakeCompletions(script)
    config = ProviderConfig(provider, "https://test.invalid/v1", "test-model", FAKE_KEY)
    backend = ModelCognitionBackend.with_client(
        "east_adam", FakeChat(completions), config
    )
    return backend, completions


@pytest.fixture(autouse=True)
def _zero_backoff(monkeypatch):
    monkeypatch.setattr(fpcm, "_TRANSPORT_BACKOFF_SECONDS", (0.0, 0.0))


def test_timeout_retry_success():
    backend, completions = _backend(["raise_timeout", "raise_timeout", "ok"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert raw["proposed_action"] is None
    assert completions.calls == 3


def test_timeout_fail_closed_max_attempts():
    backend, completions = _backend(["raise_timeout", "raise_timeout", "raise_timeout"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert "transport attempts: 3" in err
    assert completions.calls == 3


def test_nonretryable_404_single_attempt():
    backend, completions = _backend(["raise_404", "ok", "ok"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert "transport attempts: 1" in err
    assert completions.calls == 1


def test_5xx_retry_then_success():
    backend, completions = _backend(["raise_5xx", "ok"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert completions.calls == 2


def test_success_single_attempt():
    backend, completions = _backend(["ok"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert completions.calls == 1


def test_no_action_never_rerequested():
    backend, completions = _backend(["ok"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert raw["proposed_action"] is None
    assert completions.calls == 1


def test_no_secret_leakage_in_error():
    backend, completions = _backend(["raise_secret"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert FAKE_KEY not in err
    assert ("[REDACTED]" in err) or ("***" in err)


def test_non_nvidia_lane_no_retry():
    backend, completions = _backend(["raise_timeout"], provider="ollama")
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert completions.calls == 1


def test_transport_retry_and_json_repair_compose():
    invalid_payload = json.dumps({"observation_summary": 123})
    class _InvalidThenTimeoutThenValid(FakeCompletions):
        pass

    completions = FakeCompletions([])
    original_create = completions.create

    def scripted_create(**kwargs):
        completions.calls += 1
        req = httpx.Request("POST", "https://test.invalid/v1/chat/completions")
        if completions.calls == 1:
            return _Resp(invalid_payload)
        if completions.calls == 2:
            raise APITimeoutError(req)
        return _Resp(_valid_payload())

    completions.create = scripted_create  # type: ignore[method-assign]
    config = ProviderConfig("nvidia", "https://test.invalid/v1", "test-model", FAKE_KEY)
    backend = ModelCognitionBackend.with_client(
        "east_adam", FakeChat(completions), config
    )
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert raw["proposed_action"] is None
    assert completions.calls == 3


def test_shared_budget_caps_total_attempts():
    completions = FakeCompletions([])

    def scripted_create(**kwargs):
        completions.calls += 1
        req = httpx.Request("POST", "https://test.invalid/v1/chat/completions")
        raise APITimeoutError(req)

    completions.create = scripted_create  # type: ignore[method-assign]
    config = ProviderConfig("nvidia", "https://test.invalid/v1", "test-model", FAKE_KEY)
    backend = ModelCognitionBackend.with_client(
        "east_adam", FakeChat(completions), config
    )
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert completions.calls == 3
    assert "transport attempts: 3" in err
