"""Phase 10JX tests: Sustainable Cultivation, Garden Addons & Causal Timber Hewing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_cognition_interface import AgentContext


def _setup_runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    runtime = FirstPairRuntime(heartbeat_limit=10, store=store, pair_id="east")
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.tile_occupancy["east_eve"] = "cont_a_gen_0_1"
    return runtime


def test_timber_hewing_requires_tool(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]

    # Ensure tile has a tree or wood available
    runtime._current_tile_resources[pos] = [{"kind": "wood", "amount": 10}]

    # 1. Bare-handed hew attempt fails
    res_bare = runtime._execute_action(agent, {
        "action_type": "hew_timber",
        "reason": "Try to chop tree with bare hands",
    }, heartbeat_number=1)
    assert res_bare["status"] == "rejected"
    assert "axe" in res_bare["reason"].lower() or "tool" in res_bare["reason"].lower() or "blade" in res_bare["reason"].lower()

    # 2. Add stone axe to inventory and hew
    add_to_inventory(runtime._store, agent, "stone_axe", 1)
    res_tool = runtime._execute_action(agent, {
        "action_type": "hew_timber",
        "reason": "Fell tree for compound timbers",
    }, heartbeat_number=2)
    assert res_tool["status"] == "success"
    assert res_tool.get("timber_yield", 0) >= 1

    inv = load_inventory(runtime._store).get(agent, {})
    assert inv.get("timber", 0) >= 1


def test_garden_crop_lifecycle(tmp_path: Path):
    runtime = _setup_runtime(tmp_path)
    agent = "east_adam"
    pos = runtime._world_state.tile_occupancy[agent]

    add_to_inventory(runtime._store, agent, "wood", 10)
    add_to_inventory(runtime._store, agent, "fiber_plants", 10)
    add_to_inventory(runtime._store, agent, "wild_berries", 2)

    # 1. Build enclosed garden plot
    res_build = runtime._execute_build(agent, {
        "action_type": "build",
        "object_id": "garden-001",
        "object_type": "enclosed_garden",
        "tile_id": pos,
        "materials": {"wood": 4, "fiber_plants": 4},
        "description": "Fenced garden plot",
    }, heartbeat_number=1)
    assert res_build["status"] == "success"

    # 2. Plant crop
    res_plant = runtime._execute_action(agent, {
        "action_type": "plant_crop",
        "target_id": "garden-001",
        "resource_kind": "wild_berries",
        "reason": "Plant wild berry bush in garden bed",
    }, heartbeat_number=2)
    assert res_plant["status"] == "success"

    # 3. Harvest too early (heartbeat 10) -> rejected
    res_early = runtime._execute_action(agent, {
        "action_type": "harvest_crop",
        "target_id": "garden-001",
        "reason": "Try to harvest immature berries",
    }, heartbeat_number=10)
    assert res_early["status"] == "rejected"
    assert "mature" in res_early["reason"].lower()

    # 4. Harvest when mature (heartbeat 65, diff >= 61) -> success
    res_mature = runtime._execute_action(agent, {
        "action_type": "harvest_crop",
        "target_id": "garden-001",
        "reason": "Harvest mature crop",
    }, heartbeat_number=65)
    assert res_mature["status"] == "success"
    assert res_mature.get("amount_gathered", 0) >= 3

    inv = load_inventory(runtime._store).get(agent, {})
    assert inv.get("wild_berries", 0) >= 4


def test_cognition_prompt_grounding_and_affordances():
    context = AgentContext(
        agent_id="test_agent",
        canonical_name="Adam",
        canonical_ref="east_adam",
        other_agent_id="test_other",
        other_agent_name="Eve",
        other_agent_ref="east_eve",
        heartbeat_number=1,
        position="cont_a_gen_0_0",
        observation={
            "self_body": {"hunger": 10, "warmth": 90, "vitality": 100},
            "environment": {"weather": "clear", "temperature": 65},
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["cont_a_gen_0_0"],
        habitat_movement_allowed=True,
        previous_action=None,
        timestamp_utc="2026-10-28T00:00:00Z",
    )
    prompt = build_system_prompt(context)

    # 1. Permanent continental scale facts
    assert "40,000 tiles" in prompt
    assert "tiny fraction" in prompt or "<2%" in prompt
    assert "world is never exhausted" in prompt

    # 2. Action verbs present
    assert "addon_to" in prompt
    assert "hew_timber" in prompt
    assert "plant_crop" in prompt
    assert "harvest_crop" in prompt
