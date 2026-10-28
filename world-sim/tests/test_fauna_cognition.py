"""Phase 10JN cognition and milk nutrition tests."""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import (
    validate_action_exact,
    build_system_prompt,
)
from backend.world.first_pair_cognition_interface import AgentContext


def test_offer_food_action_validates():
    raw = {
        "action_type": "offer_food",
        "target_id": "cow-1",
        "resource_kind": "wild_berries",
        "reason": "offer one berry",
    }
    assert validate_action_exact(raw, "agent-1") == []


def test_offer_food_requires_resource_kind():
    raw = {
        "action_type": "offer_food",
        "target_id": "cow-1",
        "reason": "offer",
    }
    errors = validate_action_exact(raw, "agent-1")
    assert "action:empty_resource_kind" in errors


def test_milk_animal_action_validates():
    raw = {
        "action_type": "milk_animal",
        "target_id": "cow-1",
        "reason": "milk the ready cow",
    }
    assert validate_action_exact(raw, "agent-1") == []


def test_prompt_recognizes_milk_and_fauna_actions():
    context = AgentContext(
        agent_id="agent-1",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=3,
        position="tile-alpha",
        observation={
            "self_body": {"hunger": 70.0, "vitality": 100.0,
                          "warmth": 100.0, "wetness": 0.0, "downed": False},
            "fauna": {"nearby": [
                {"kind": "cow", "id": "cow-1", "distance": 1,
                 "trust": 60, "tamed": True, "milk_ready": True},
                {"kind": "snake", "id": "snake-1", "distance": 1},
            ]},
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-26T00:00:00Z",
        inventory={"milk": 1},
    )
    prompt = build_system_prompt(context)
    assert "offer_food" in prompt
    assert "milk_animal" in prompt
    assert "milk: 28" in prompt
    assert "A cow is nearby; it is tamed and milk is ready [id: cow-1]." in prompt
    assert "A snake is nearby; it is dangerous [id: snake-1]." in prompt


def test_validator_accepts_every_shared_fauna_food():
    from backend.world.fauna import ANIMAL_FOOD_TRUST

    for food in ANIMAL_FOOD_TRUST:
        raw = {
            "action_type": "offer_food",
            "target_id": "cow-1",
            "resource_kind": food,
            "reason": "offer food",
        }
        errors = validate_action_exact(raw, "agent-1")
        assert "action:invalid_animal_food" not in errors


def test_prompt_advertises_every_shared_fauna_food():
    from backend.world.first_pair_cognition_model import _AVAILABLE_ACTIONS_DESC
    from backend.world.fauna import ANIMAL_FOOD_TRUST

    for food in ANIMAL_FOOD_TRUST:
        assert food in _AVAILABLE_ACTIONS_DESC


def test_meat_satisfaction_matches_prompt_and_runtime():
    from backend.world import survival

    assert survival.eat_satisfaction("meat") == 40.0

    context = AgentContext(
        agent_id="agent-1",
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=3,
        position="tile-alpha",
        observation={
            "self_body": {"hunger": 70.0, "vitality": 100.0,
                          "warmth": 100.0, "wetness": 0.0, "downed": False},
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-26T00:00:00Z",
        inventory={"meat": 1},
    )
    prompt = build_system_prompt(context)
    assert "meat: 40" in prompt
