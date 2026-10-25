"""Tests for Weather/Shelter/Predator Cognition Grounding and Prompting."""
import pytest
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt


def _make_ctx(**over) -> AgentContext:
    defaults = dict(
        agent_id="genesis-agent-test",
        canonical_name="Eve",
        canonical_ref="east_eve",
        heartbeat_number=4500,
        position="cont_a_gen_1_1",
        observation={},
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["cont_a_gen_1_1"],
        habitat_movement_allowed=True,
        previous_action=None,
        timestamp_utc="2026-10-24T19:50:00Z",
    )
    defaults.update(over)
    return AgentContext(**defaults)


def test_predator_alert_in_prompt_when_wolf_nearby():
    ctx = _make_ctx(
        observation={
            "self_body": {"vitality": 50.0, "hunger": 20.0, "warmth": 80.0},
            "environment": {"time_of_day": "night", "season": "autumn", "weather": "clear", "temperature": 55.0},
            "wildlife": {
                "nearby": [{"kind": "wolf", "distance": 3}],
                "howling": False,
            },
        },
    )
    prompt = build_system_prompt(ctx)
    assert "Predator Alert" in prompt
    assert "wolf is nearby (3 tiles away)" in prompt
    assert "Predators physically refuse to enter constructed shelters (huts, lean-tos, cabins, roofs)" in prompt
    assert "Inside a constructed shelter or beside a lit fire, you are completely safe from animal attacks." in prompt
    # Strict verification: caves must not be promised before cave physics is activated
    assert "caves" not in prompt.lower()


def test_predator_alert_in_prompt_when_howling():
    ctx = _make_ctx(
        observation={
            "self_body": {"vitality": 50.0, "hunger": 20.0, "warmth": 80.0},
            "environment": {"time_of_day": "night", "season": "autumn", "weather": "clear", "temperature": 55.0},
            "wildlife": {
                "nearby": [],
                "howling": True,
            },
        },
    )
    prompt = build_system_prompt(ctx)
    assert "Predator Alert" in prompt
    assert "Wolf howls echo in the dark" in prompt
    assert "Predators physically refuse to enter constructed shelters" in prompt


def test_sky_warning_when_rain_approaches():
    ctx = _make_ctx(
        observation={
            "self_body": {"vitality": 50.0, "hunger": 20.0, "warmth": 80.0},
            "environment": {
                "time_of_day": "day",
                "season": "summer",
                "weather": "clear",
                "temperature": 70.0,
                "forecast_next": "rain",
                "weather_changes_at_heartbeat": 4500,
            },
            "wildlife": {"nearby": [], "howling": False},
        },
    )
    prompt = build_system_prompt(ctx)
    assert "Sky warning: Weather will turn to rain at heartbeat 4500" in prompt
    assert "Open fires will be snuffed by rain unless built under a roof" in prompt


def test_wild_bee_colony_facts_in_prompt():
    # Active bees
    ctx_active = _make_ctx(
        observation={
            "self_body": {"vitality": 50.0, "hunger": 20.0, "warmth": 80.0},
            "environment": {
                "time_of_day": "day",
                "season": "summer",
                "weather": "clear",
                "temperature": 70.0,
                "wild_bees": {"tile": "cont_a_gen_1_1", "colony_state": "active"},
            },
            "wildlife": {"nearby": [], "howling": False},
        },
    )
    prompt_active = build_system_prompt(ctx_active)
    assert "wild bee colony on this tile is actively buzzing" in prompt_active
    assert "Gathering without smoke will cause defensive stings (-2.0 vitality)" in prompt_active
    assert "eating a gathered honeycomb with the eat action satisfies 32 hunger points" in prompt_active

    # Calmed bees
    ctx_calmed = _make_ctx(
        observation={
            "self_body": {"vitality": 50.0, "hunger": 20.0, "warmth": 80.0},
            "environment": {
                "time_of_day": "day",
                "season": "summer",
                "weather": "clear",
                "temperature": 70.0,
                "wild_bees": {"tile": "cont_a_gen_1_1", "colony_state": "calmed"},
            },
            "wildlife": {"nearby": [], "howling": False},
        },
    )
    prompt_calmed = build_system_prompt(ctx_calmed)
    assert "calmed by nearby campfire smoke, allowing safe honeycomb gathering into your belongings" in prompt_calmed
    assert "Eating a gathered honeycomb with the eat action satisfies 32 hunger points" in prompt_calmed
