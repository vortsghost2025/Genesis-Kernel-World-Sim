"""10JH model route correction (TDD).

R1: dots primary fails Adam's contract validation (extra goal_updates
fields) - a 200 with invalid JSON is content failure.
R2: a `:free` fallback model is routed to the NVIDIA direct lane under an
`explicit_url` primary, where the OpenRouter `:free` suffix convention is
invalid and the call 404s. The OpenRouter-fallback branch never fires.

No network calls here: routing is pinned via resolve_fallback_provider,
validation via validate_model_output, constants via direct import.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import pytest  # noqa: E402

import backend.world.first_pair_cognition_model as cmod  # noqa: E402
from backend.world.first_pair_cognition_model import (  # noqa: E402
    ProviderConfig,
    ProviderError,
    validate_model_output,
)
from backend.world.first_pair_cognition_interface import (  # noqa: E402
    AgentContext,
)

BOTH_VALID_ROUTE = "inclusionai/ling-3.0-flash-sante:free"

_FALLBACK_ENV_KEYS = (
    "GENESIS_FIRST_PAIR_BASE_URL",
    "GENESIS_FIRST_PAIR_API_KEY",
    "GENESIS_FIRST_PAIR_MODEL",
    "GENESIS_FIRST_PAIR_FALLBACK_MODEL",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_HOST",
)


def _clear_env(monkeypatch):
    for name in _FALLBACK_ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


def _explicit_primary() -> ProviderConfig:
    return ProviderConfig(
        provider_type="explicit_url",
        base_url="https://openrouter.ai/api/v1",
        model="dots-studio/dots-3-note-preview:free",
        api_key="or-key",
    )


def _ctx(agent: str) -> AgentContext:
    aid = "genesis-agent-test-%s-" % agent + "0" * 48
    return AgentContext(
        agent_id=aid,
        canonical_name=agent.capitalize(),
        canonical_ref="east_%s" % agent,
        heartbeat_number=1901,
        position="tile-alpha",
        observation={"tile_id": "tile-alpha",
                     "visible_tiles": ["tile-alpha"], "objects_here": []},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-07T00:00:00Z",
        other_agent_id="genesis-agent-test-other-" + "0" * 42,
        other_agent_name="Other",
        other_agent_ref="east_other",
        answered_questions=[],
    )


def _base_raw(agent_id: str) -> dict:
    return {
        "observation_summary": "Surveying the western row.",
        "self_model_update": None,
        "goal_updates": [],
        "proposed_action": {"action_type": "move",
                            "target_tile": "tile-alpha",
                            "reason": "Continue the survey west."},
        "memory_candidates": [],
        "questions_for_humans": [],
        "uncertainty": "None.",
        "decision_summary": "Move west along the survey row.",
        "confidence": 0.7,
    }


class TestFreeFallbackLane:
    def test_free_fallback_rides_openrouter_under_explicit_url(
            self, monkeypatch):
        """A `:free` fallback must ride the OpenRouter lane, never NVIDIA
        direct, when the primary is explicit_url and both keys exist."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m:free")
        fb = cmod.resolve_fallback_provider(_explicit_primary())
        assert fb is not None
        assert fb.provider_type == "openrouter"
        assert fb.model == "fb/m:free"
        assert fb.api_key == "or-key"
        assert "openrouter" in fb.base_url

    def test_free_fallback_without_openrouter_key_returns_none(
            self, monkeypatch):
        """No OpenRouter credential means no viable lane for a `:free`
        id - offering NVIDIA direct would 404, so resolve to None."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m:free")
        assert cmod.resolve_fallback_provider(
            _explicit_primary()) is None

    def test_nvidia_lane_never_serves_free_ids(self, monkeypatch):
        """Across primary lane types, a `:free` fallback must never
        resolve to the nvidia provider."""
        for primary in (
            _explicit_primary(),
            ProviderConfig("nvidia", "https://n.example/v1", "m", "k"),
            ProviderConfig("openrouter", "https://o.example/v1",
                           "m", "k"),
        ):
            _clear_env(monkeypatch)
            monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
            monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
            monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL",
                               "fb/m:free")
            fb = cmod.resolve_fallback_provider(primary)
            assert fb is None or fb.provider_type != "nvidia"

    def test_nonfree_fallback_still_rides_nvidia(self, monkeypatch):
        """A non-`:free` id stays a valid NVIDIA-direct fallback - the
        fix must not capture ids that were never OpenRouter-style."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL", "fb/m")
        fb = cmod.resolve_fallback_provider(_explicit_primary())
        assert fb is not None
        assert fb.provider_type == "nvidia"
        assert fb.model == "fb/m"

    def test_paid_openrouter_guard_preserved(self, monkeypatch):
        """The free-only guard still fails closed for paid ids on the
        NVIDIA-primary path."""
        _clear_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_MODEL", "m")
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("GENESIS_FIRST_PAIR_FALLBACK_MODEL",
                           "fb/m-paid")
        primary = cmod.resolve_provider()
        with pytest.raises(ProviderError):
            cmod.resolve_fallback_provider(primary)


class TestDotsAdamInvalidity:
    def test_goal_updates_reject_unknown_fields(self):
        """The dots-style Adam output (extra related_question_id and
        metadata inside goal_updates) is INVALID - this pins R1 at the
        validation layer."""
        ctx = _ctx("adam")
        raw = _base_raw(ctx.agent_id)
        raw["goal_updates"] = [{
            "goal_id": "goal-eve-010",
            "agent_id": ctx.agent_id,
            "description": "Return to center.",
            "status": "in_progress",
            "related_question_id": "q2-world-expansion",
            "metadata": {},
        }]
        v = validate_model_output(raw, ctx.agent_id)
        assert not v.is_valid
        assert any("unknown_field:related_question_id" in e
                   for e in v.validation_errors)
        assert any("unknown_field:metadata" in e
                   for e in v.validation_errors)

    def test_valid_move_output_accepted_both_agents(self):
        """The ling-style contract shape (exact fields only) validates
        for both agents - the bar the new primary must clear."""
        for agent in ("adam", "eve"):
            ctx = _ctx(agent)
            v = validate_model_output(_base_raw(ctx.agent_id),
                                      ctx.agent_id)
            assert v.is_valid, v.validation_errors
            assert (v.proposed_action or {}).get(
                "action_type") == "move"


class TestPrimaryModels:
    def test_primary_and_per_agent_models_are_both_valid_route(self):
        """Runner constants must name the Oct-07 both-valid route, not
        the Adam-invalid dots route."""
        from backend.world import canonical_heartbeat_runner as r
        assert r.PRIMARY_MODEL == BOTH_VALID_ROUTE
        assert r.ADAM_MODEL == BOTH_VALID_ROUTE
        assert r.EVE_MODEL == BOTH_VALID_ROUTE
