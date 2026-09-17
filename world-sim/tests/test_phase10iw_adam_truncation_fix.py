"""Phase 10IW — Adam truncation-fix tests for the first-pair cognition backend.

Root cause proven by operator-authorized differential diagnosis (2026-09-16):
GLM 5.3 Flash is a reasoning model — reasoning_content + content share the
single max_tokens completion budget.  Adam's reasoning for his canonical
context runs ~2,300-3,400 tokens and alone exhausted max_tokens=2048, so
finish_reason="length" fired with content=None and the runtime mislabeled the
truncation as "empty_response".  The same Adam prompt at max_tokens=4096
returned finish=stop with valid JSON.

Proves:
- initial response: finish_reason=length + empty content
  -> "max_tokens_truncated_response" (never "empty_response")
- repair response: finish_reason=length + empty content
  -> "repair_max_tokens_truncated_response"
- finish_reason=length + nonempty valid JSON is accepted normally (Eve case)
- initial and repair calls use max_tokens=4096
- valid first response still causes exactly one model call
- transport retry accounting unchanged (max 3, fail closed)
- no secret leakage regression
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

import httpx
import pytest
from openai import APITimeoutError

import backend.world.first_pair_cognition_model as fpcm
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import ModelCognitionBackend, ProviderConfig

FAKE_KEY = "nvapi-FAKE-SECRET-TEST-456"

_INVALID_JSON = json.dumps({"observation_summary": 123})


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


def _valid_payload() -> str:
    return json.dumps({
        "observation_summary": "test observation",
        "self_model_update": "test update",
        "goal_updates": [],
        "proposed_action": None,
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "low",
        "decision_summary": "test decision",
        "confidence": 0.9,
    })


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, finish_reason):
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content, finish_reason):
        self.choices = [_Choice(content, finish_reason)]


class FakeCompletions:
    """Scripted fake: entries are (finish_reason, content) tuples or exception
    markers.  Records every max_tokens value seen."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.max_tokens_seen = []

    def create(self, **kwargs):
        self.calls += 1
        self.max_tokens_seen.append(kwargs.get("max_tokens"))
        behavior = self._script.pop(0) if self._script else ("stop", _valid_payload())
        req = httpx.Request("POST", "https://test.invalid/v1/chat/completions")
        if behavior == "raise_timeout":
            raise APITimeoutError(req)
        if behavior == "raise_secret":
            raise RuntimeError(f"connection dead with key={FAKE_KEY}")
        finish_reason, content = behavior
        return _Resp(content, finish_reason)


class FakeChat:
    def __init__(self, completions: FakeCompletions):
        self.completions = completions

    @property
    def chat(self) -> "FakeChat":
        return self


def _backend(script) -> tuple[ModelCognitionBackend, FakeCompletions]:
    completions = FakeCompletions(script)
    config = ProviderConfig("nvidia", "https://test.invalid/v1", "test-model", FAKE_KEY)
    backend = ModelCognitionBackend.with_client(
        "east_adam", FakeChat(completions), config
    )
    return backend, completions


@pytest.fixture(autouse=True)
def _zero_backoff(monkeypatch):
    monkeypatch.setattr(fpcm, "_TRANSPORT_BACKOFF_SECONDS", (0.0, 0.0))


def test_initial_length_empty_content_is_truncation_not_empty_response():
    backend, completions = _backend([("length", None)])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err == "max_tokens_truncated_response"
    assert "empty_response" not in err
    assert completions.calls == 1


def test_repair_length_empty_content_is_repair_truncation():
    backend, completions = _backend([("stop", _INVALID_JSON), ("length", None)])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err == "repair_max_tokens_truncated_response"
    assert "repair_empty_response" not in err
    assert completions.calls == 2


def test_length_with_valid_json_accepted_normally():
    backend, completions = _backend([("length", _valid_payload())])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert raw["decision_summary"] == "test decision"
    assert completions.calls == 1


def test_initial_call_uses_max_tokens_4096():
    backend, completions = _backend([("stop", _valid_payload())])
    backend._call_model_with_repair("system prompt", _ctx())
    assert completions.max_tokens_seen == [4096]


def test_repair_call_uses_max_tokens_4096():
    backend, completions = _backend([("stop", _INVALID_JSON), ("stop", _valid_payload())])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert completions.max_tokens_seen == [4096, 4096]


def test_valid_first_response_still_single_call():
    backend, completions = _backend([("stop", _valid_payload())])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert err is None
    assert raw is not None
    assert completions.calls == 1


def test_transport_retry_accounting_unchanged():
    backend, completions = _backend(
        ["raise_timeout", "raise_timeout", "raise_timeout"]
    )
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert "transport attempts: 3" in err
    assert completions.calls == 3


def test_no_secret_leakage_regression():
    backend, completions = _backend(["raise_secret"])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err is not None
    assert FAKE_KEY not in err
    assert ("[REDACTED]" in err) or ("***" in err)


def test_stop_with_empty_content_still_empty_response():
    backend, completions = _backend([("stop", "")])
    raw, err = backend._call_model_with_repair("system prompt", _ctx())
    assert raw is None
    assert err == "empty_response"
    assert completions.calls == 1
