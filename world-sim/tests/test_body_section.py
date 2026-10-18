"""The body speaks at the moment of need — facts in the prompt.

Measured Oct 18: both pairs starved with full pockets because a
once-told changelog fact does not survive 300 heartbeats of habit,
and the collapsed west pair spent its heartbeats asking the operator
what to do. The prompt now states the body's mechanics as facts every
heartbeat they bear. These tests pin: facts appear when the body
bears them, stay silent when it does not, and never give advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import (  # noqa: E402
    build_system_prompt,
)


def _ctx(observation):
    """A minimal context carrying just the observation the prompt reads."""
    from backend.world.first_pair_cognition_model import AgentContext
    return AgentContext(
        agent_id="a" * 64,
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=4000,
        position="cont_a_gen_0_0",
        observation=observation,
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=[],
        habitat_movement_allowed=True,
        previous_action=None,
        timestamp_utc="now",
        other_agent_id="b" * 64,
        other_agent_name="Eve",
        other_agent_ref="east_eve",
    )


def _prompt_for(vitals, env=None):
    obs = {"self_body": vitals, "environment": env or {}}
    return build_system_prompt(_ctx(obs))


def _well():
    return {"hunger": 20.0, "warmth": 80.0, "vitality": 100.0,
            "wetness": 0.0, "downed": False}


class TestDownedFacts:
    def test_downed_states_the_mechanics(self):
        v = dict(_well(), downed=True, vitality=0.0)
        prompt = _prompt_for(v)
        assert "Your body has collapsed" in prompt
        assert "eat action" in prompt
        assert "works while you are collapsed" in prompt
        assert "deposited into any object on your tile" in prompt

    def test_downed_facts_are_facts_not_orders(self):
        v = dict(_well(), downed=True, vitality=0.0)
        full = _prompt_for(v)
        section = full.split("YOUR BODY")[1].split("\n---")[0]
        for directive in ("you should", "you must", "try to", "we recommend"):
            assert directive not in section.lower(), directive


class TestStarvingFacts:
    def test_starving_states_hunger_and_eat(self):
        v = dict(_well(), hunger=95.0)
        prompt = _prompt_for(v)
        assert "Your hunger is 95/100" in prompt
        assert "vitality drains" in prompt
        assert "eat action" in prompt

    def test_mild_hunger_is_quiet(self):
        """The body does not nag below 60 — a well-fed body says
        nothing about eating."""
        prompt = _prompt_for(dict(_well(), hunger=30.0))
        assert "hunger is" not in prompt
        assert "YOUR BODY" not in prompt

    def test_freezing_states_warmth_and_fire_facts(self):
        prompt = _prompt_for(dict(_well(), warmth=12.0))
        assert "Your warmth is 12/100" in prompt
        assert "roof" in prompt
        assert "soaked" in prompt

    def test_well_body_is_silent(self):
        prompt = _prompt_for(_well())
        assert "YOUR BODY" not in prompt
