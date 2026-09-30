"""A lane that answers 200 with nothing has failed, and must fail over.

On 2026-09-30 the first visible symptom of the outage was `empty_response`
for 33 consecutive heartbeats - a healthy HTTP 200 carrying no content.
`_call_model_with_repair` only reached the fallback lane when the
TRANSPORT failed (response is None). A 200-with-no-body returned early,
so the degradation path silently did not exist for the exact failure the
provider was actually producing.

These pin that a content-level failure is a lane failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import (  # noqa: E402
    ModelCognitionBackend, ProviderConfig, _content_failure,
)
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)


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
            {"type": "observation", "content": "I see an empty room.",
             "heartbeat": 1},
        ],
        goals=[
            {"goal_id": "goal-explore",
             "agent_id": "genesis-agent-test-adam-...",
             "description": "Explore the world", "status": "active"},
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

PRIMARY = ProviderConfig("nvidia", "https://n.example/v1", "p-m", "pk")
FALLBACK = ProviderConfig("openrouter", "https://o.example/v1", "f-m:free",
                          "ok")

VALID = {
    "observation_summary": "sees grass",
    "self_model_update": None,
    "decision_summary": "gather here",
    "uncertainty": "unknown",
    "confidence": 0.6,
    "proposed_action": {"action_type": "no_action"},
    "memory_candidates": [],
    "goal_updates": [],
    "questions_for_humans": [],
}


class _Msg:
    def __init__(self, content, finish="stop"):
        self.content = content
        self.finish_reason = finish


class _Choice:
    def __init__(self, content, finish="stop"):
        self.message = _Msg(content, finish)
        self.finish_reason = finish


class _Resp:
    def __init__(self, content, finish="stop"):
        self.choices = [_Choice(content, finish)]


class _Completions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        return self._owner._next()


class _FakeClient:
    """Mimics the OpenAI client's `chat.completions.create` shape."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.chat = type("_Chat", (), {})()
        self.chat.completions = _Completions(self)

    def _next(self):
        self.call_count += 1
        return self.responses[min(self.call_count - 1,
                                   len(self.responses) - 1)]


def _backend(primary, fb, fb_cfg=FALLBACK):
    # key_pool=[] pins "no rotation": the injected fakes must never be
    # replaced by a real client built from ambient environment credentials.
    return ModelCognitionBackend.with_client(
        "east_adam", primary, PRIMARY, fallback_config=fb_cfg,
        fallback_client=fb, key_pool=[])


class TestInjectedClientIsNeverReplaced:
    def test_no_pool_means_the_injected_client_is_used(self, sample_context):
        """A backend handed a client must keep it. Building a real one from
        environment credentials instead would send a test's request to the
        live provider - and, in production, silently ignore the operator's
        explicit configuration."""
        primary = _FakeClient([_Resp(json.dumps(VALID))])
        backend = _backend(primary, _FakeClient([_Resp("")]))
        backend.observe_and_orient(sample_context)
        assert primary.call_count == 1


class TestContentFailureClassification:
    def test_empty_content_is_a_failure_not_a_success(self):
        assert _content_failure(_Resp("")) == "empty_response"
        assert _content_failure(_Resp("   ")) == "empty_response"

    def test_truncation_is_named_as_truncation(self):
        """finish_reason=length with no body is the token cap, not the
        provider being mute - the two need different reading."""
        assert _content_failure(_Resp("", finish="length")) == \
            "max_tokens_truncated_response"

    def test_no_choices_is_a_failure(self):
        class _Empty:
            choices = []
        assert _content_failure(_Empty()) == "no_choices_in_response"

    def test_real_content_is_not_a_failure(self):
        assert _content_failure(_Resp('{"a":1}')) is None


class TestEmptyPrimaryReachesTheFallback:
    def test_empty_primary_falls_back_and_serves(self, sample_context):
        primary = _FakeClient([_Resp("")])
        fb = _FakeClient([_Resp(json.dumps(VALID))])
        backend = _backend(primary, fb)
        result = backend.observe_and_orient(sample_context)
        assert fb.call_count == 1, (
            "a 200 with no content must reach the fallback lane")
        assert backend.fallback_used is True
        assert backend.serving_provider_type == "openrouter"
        assert result.uncertainty is not None

    def test_truncated_primary_also_reaches_the_fallback(self, sample_context):
        primary = _FakeClient([_Resp("", finish="length")])
        fb = _FakeClient([_Resp(json.dumps(VALID))])
        backend = _backend(primary, fb)
        backend.observe_and_orient(sample_context)
        assert fb.call_count == 1

    def test_valid_primary_never_touches_the_fallback(self, sample_context):
        primary = _FakeClient([_Resp(json.dumps(VALID))])
        fb = _FakeClient([_Resp("fallback must not be called")])
        backend = _backend(primary, fb)
        backend.observe_and_orient(sample_context)
        assert fb.call_count == 0
        assert backend.fallback_used is False

    def test_both_lanes_empty_reports_both(self, sample_context):
        primary = _FakeClient([_Resp("")])
        fb = _FakeClient([_Resp("")])
        backend = _backend(primary, fb)
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert "empty_response" in result.uncertainty

    def test_no_fallback_configured_keeps_single_lane_failure(
            self, sample_context):
        primary = _FakeClient([_Resp("")])
        backend = ModelCognitionBackend.with_client("east_adam", primary,
                                                   PRIMARY, key_pool=[])
        result = backend.observe_and_orient(sample_context)
        assert result.action is None
        assert "empty_response" in result.uncertainty
        assert primary.call_count == 1, (
            "one logical call, bounded - no retry loop on a mute provider")
