"""Tests for Phase 10JI: Causal Crafting & Neolithic Tool Utility.

Validates:
1. Flint knapping and expanded craft recipes (flint_knife, flint_spear, woven_basket, clay_pot, iron_axe, iron_spear).
2. Causal tool utility (holding stone_axe boosts wood gathering; woven_basket boosts foraging).
3. Campfire cooking on functional, active fires (converts raw food to cooked_meal).
4. Unearned / non-functional fires and rain-snuffed fires reject cooking.
5. Strict material validation (floats/non-integers rejected before deducting inventory).
6. Nutritional satisfaction of eating cooked_meal (75 points).
7. Predator defense against attacking wolves (armed agent repels wolf bite).
8. Cognition model prompt recognizes cooked_meal as edible food.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world import wildlife
from backend.world import survival
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt


def _setup_runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(root=tmp_path)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt._load_or_initialize()
    if not hasattr(rt, "_current_tile_resources"):
        rt._current_tile_resources = {}
    return rt


def _seed_public_object(
    rt: FirstPairRuntime, obj_id: str, obj_type: str, tile_id: str, materials: dict | None = None
) -> dict:
    obj = {
        "object_id": obj_id,
        "object_type": obj_type,
        "tile_id": tile_id,
        "creator_agent_id": "genesis-agent-test-adam-000",
        "public_description": f"a test {obj_type}",
        "materials": materials or {},
        "contents": {},
    }
    rt._world_state.public_objects[obj_id] = obj
    return obj


def test_craft_flint_knife_and_flint_spear(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    _seed_public_object(rt, "crafting-table-01", "crafting_surface", tile)

    # Seed ingredients for flint_knife (flint: 2, wood: 1) and flint_spear (flint: 1, wood: 2, fiber_plants: 1)
    add_to_inventory(rt._store, agent, "flint", 3)
    add_to_inventory(rt._store, agent, "wood", 3)
    add_to_inventory(rt._store, agent, "fiber_plants", 1)

    # Craft flint_knife
    action_knife = {
        "action_type": "use_object",
        "target_object_id": "crafting-table-01",
        "operation": "craft",
        "materials": {"flint": 2, "wood": 1},
    }
    res_knife = rt._execute_action(agent, action_knife, 1)
    assert res_knife["status"] == "success"
    assert res_knife["crafted"] == "flint_knife"

    # Craft flint_spear
    action_spear = {
        "action_type": "use_object",
        "target_object_id": "crafting-table-01",
        "operation": "craft",
        "materials": {"flint": 1, "wood": 2, "fiber_plants": 1},
    }
    res_spear = rt._execute_action(agent, action_spear, 1)
    assert res_spear["status"] == "success"
    assert res_spear["crafted"] == "flint_spear"

    inv = load_inventory(rt._store)[agent]
    assert inv.get("flint_knife") == 1
    assert inv.get("flint_spear") == 1
    assert inv.get("flint", 0) == 0
    assert inv.get("wood", 0) == 0
    assert inv.get("fiber_plants", 0) == 0


def test_craft_woven_basket_and_clay_pot(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    _seed_public_object(rt, "workbench-01", "crafting_surface", tile)

    add_to_inventory(rt._store, agent, "fiber_plants", 4)
    add_to_inventory(rt._store, agent, "wood", 2)
    add_to_inventory(rt._store, agent, "clay", 3)

    # Craft woven_basket
    action_basket = {
        "action_type": "use_object",
        "target_object_id": "workbench-01",
        "operation": "craft",
        "materials": {"fiber_plants": 4, "wood": 2},
    }
    res_basket = rt._execute_action(agent, action_basket, 1)
    assert res_basket["status"] == "success"
    assert res_basket["crafted"] == "woven_basket"

    # Craft clay_pot
    action_pot = {
        "action_type": "use_object",
        "target_object_id": "workbench-01",
        "operation": "craft",
        "materials": {"clay": 3},
    }
    res_pot = rt._execute_action(agent, action_pot, 1)
    assert res_pot["status"] == "success"
    assert res_pot["crafted"] == "clay_pot"

    inv = load_inventory(rt._store)[agent]
    assert inv.get("woven_basket") == 1
    assert inv.get("clay_pot") == 1


def test_craft_iron_axe_and_iron_spear(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    _seed_public_object(rt, "forge-01", "forge", tile)

    add_to_inventory(rt._store, agent, "iron", 3)
    add_to_inventory(rt._store, agent, "wood", 3)
    add_to_inventory(rt._store, agent, "fiber_plants", 1)

    # Craft iron_axe (iron: 2, wood: 1)
    res_axe = rt._execute_action(agent, {
        "action_type": "use_object",
        "target_object_id": "forge-01",
        "operation": "craft",
        "materials": {"iron": 2, "wood": 1},
    }, 1)
    assert res_axe["status"] == "success"
    assert res_axe["crafted"] == "iron_axe"

    # Craft iron_spear (fiber_plants: 1, iron: 1, wood: 2)
    res_spear = rt._execute_action(agent, {
        "action_type": "use_object",
        "target_object_id": "forge-01",
        "operation": "craft",
        "materials": {"fiber_plants": 1, "iron": 1, "wood": 2},
    }, 1)
    assert res_spear["status"] == "success"
    assert res_spear["crafted"] == "iron_spear"


def test_tool_utility_axe_boosts_wood_gathering(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]

    # Seed wood on tile
    rt._current_tile_resources[tile] = [{"kind": "wood", "amount": 20}]

    # Gather without axe (yields base GATHER_YIELD = 1)
    res_no_axe = rt._execute_action(agent, {"action_type": "gather", "resource_kind": "wood"}, 1)
    assert res_no_axe["status"] == "success"
    assert res_no_axe["amount_gathered"] == 1

    # Give agent stone_axe
    add_to_inventory(rt._store, agent, "stone_axe", 1)

    # Gather with axe (boosts yield to 5)
    res_with_axe = rt._execute_action(agent, {"action_type": "gather", "resource_kind": "wood"}, 2)
    assert res_with_axe["status"] == "success"
    assert res_with_axe["amount_gathered"] == 5
    assert "hewn with axe" in res_with_axe.get("detail", "").lower()


def test_woven_basket_boosts_berry_gathering(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_eve"
    tile = rt._world_state.tile_occupancy[agent]

    rt._current_tile_resources[tile] = [{"kind": "wild_berries", "amount": 20}]

    # Without basket: 1
    res1 = rt._execute_action(agent, {"action_type": "gather", "resource_kind": "wild_berries"}, 1)
    assert res1["status"] == "success"
    assert res1["amount_gathered"] == 1

    # With basket: 3
    add_to_inventory(rt._store, agent, "woven_basket", 1)
    res2 = rt._execute_action(agent, {"action_type": "gather", "resource_kind": "wild_berries"}, 2)
    assert res2["status"] == "success"
    assert res2["amount_gathered"] == 3
    assert "woven basket" in res2.get("detail", "").lower()


def test_campfire_cooking_produces_cooked_meal(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    # Functional campfire with materials
    _seed_public_object(rt, "fire-01", "campfire", tile, materials={"wood": 2})

    # Provide raw ingredients: berries: 2, edible_roots: 1
    add_to_inventory(rt._store, agent, "wild_berries", 2)
    add_to_inventory(rt._store, agent, "edible_roots", 1)

    action_cook = {
        "action_type": "use_object",
        "target_object_id": "fire-01",
        "operation": "cook",
        "materials": {"wild_berries": 2, "edible_roots": 1},
    }
    res = rt._execute_action(agent, action_cook, 1)
    assert res["status"] == "success"
    assert res.get("cooked") == "cooked_meal"

    inv = load_inventory(rt._store)[agent]
    assert inv.get("cooked_meal") == 1
    assert inv.get("wild_berries", 0) == 0
    assert inv.get("edible_roots", 0) == 0


def test_cooking_requires_functional_fire(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    # Unearned fire with 0 materials fails functional check
    _seed_public_object(rt, "fake-fire-01", "campfire", tile, materials={})

    add_to_inventory(rt._store, agent, "wild_berries", 3)

    res = rt._execute_action(agent, {
        "action_type": "use_object",
        "target_object_id": "fake-fire-01",
        "operation": "cook",
        "materials": {"wild_berries": 3},
    }, 1)
    assert res["status"] == "rejected"
    assert "no fuel" in res["reason"].lower() or "unlit" in res["reason"].lower()

    # Verify inventory was untouched
    assert load_inventory(rt._store)[agent]["wild_berries"] == 3


def test_cooking_rejected_when_fire_snuffed_by_rain(monkeypatch, tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    _seed_public_object(rt, "open-fire-01", "campfire", tile, materials={"wood": 2})

    add_to_inventory(rt._store, agent, "wild_berries", 3)

    # Weather is rain
    monkeypatch.setattr(survival, "weather_at", lambda pid, hb: ("rain", 5000))

    res = rt._execute_action(agent, {
        "action_type": "use_object",
        "target_object_id": "open-fire-01",
        "operation": "cook",
        "materials": {"wild_berries": 3},
    }, 1)
    assert res["status"] == "rejected"
    assert "snuffed" in res["reason"].lower()

    # Berries untouched
    assert load_inventory(rt._store)[agent]["wild_berries"] == 3


def test_malformed_materials_rejected_without_partial_consumption(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    tile = rt._world_state.tile_occupancy[agent]
    _seed_public_object(rt, "fire-01", "campfire", tile, materials={"wood": 2})

    add_to_inventory(rt._store, agent, "wild_berries", 5)
    add_to_inventory(rt._store, agent, "edible_roots", 5)

    # Provide float amount: 1.0
    res = rt._execute_action(agent, {
        "action_type": "use_object",
        "target_object_id": "fire-01",
        "operation": "cook",
        "materials": {"wild_berries": 2, "edible_roots": 1.0},
    }, 1)
    assert res["status"] == "rejected"
    assert "positive integer" in res["reason"]

    # Invariant: zero partial consumption!
    inv = load_inventory(rt._store)[agent]
    assert inv["wild_berries"] == 5
    assert inv["edible_roots"] == 5


def test_cooked_meal_satisfaction(tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"

    # Set hunger to 80
    vitals = rt._vitals_for(agent)
    vitals["hunger"] = 80.0
    add_to_inventory(rt._store, agent, "cooked_meal", 1)

    res = rt._execute_action(agent, {"action_type": "eat", "resource_kind": "cooked_meal"}, 1)
    assert res["status"] == "success"

    # Cooked meal satisfies 75 points per survival.py
    assert vitals["hunger"] == 5.0  # exactly 80.0 - 75.0 = 5.0


def test_predator_defense_armed_agent_repels_wolf(monkeypatch, tmp_path: Path):
    rt = _setup_runtime(tmp_path)
    agent = "east_adam"
    rt._world_state.tile_occupancy = {"east_adam": "cont_a_gen_0_0", "east_eve": "cont_a_gen_10_10"}
    rt._world_state.vitals["east_adam"] = {"vitality": 100.0, "downed": False}

    # Place an attacking wolf adjacent to adam at [1, 0]
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-test",
        "tile": [1, 0],
        "hp": 2,
    }]

    monkeypatch.setattr(survival, "weather_at", lambda pid, hb: ("clear", 5000))
    monkeypatch.setattr(survival, "is_night", lambda hb: True)

    # CASE A: Unarmed agent takes bite damage
    rt.wildlife_tick(heartbeat_number=100)
    assert rt._world_state.vitals["east_adam"]["vitality"] == 92.0  # 100 - 8

    # Reset health and spawn another wolf
    rt._world_state.vitals["east_adam"]["vitality"] = 100.0
    rt._world_state.wildlife = [{
        "kind": "wolf",
        "id": "wolf-test-2",
        "tile": [1, 0],
        "hp": 2,
    }]

    # CASE B: Armed with flint_spear -> repels wolf! Zero bite damage!
    add_to_inventory(rt._store, agent, "flint_spear", 1)
    rt.wildlife_tick(heartbeat_number=101)
    assert rt._world_state.vitals["east_adam"]["vitality"] == 100.0  # Bite repelled!
    assert not any(e["kind"] == "wolf" for e in rt._world_state.wildlife)  # Wolf repelled and fled!


def test_prompt_recognizes_cooked_meal_as_food():
    ctx = AgentContext(
        agent_id="genesis-agent-test-adam-" + "0" * 48,
        canonical_name="Adam",
        canonical_ref="east_adam",
        heartbeat_number=3,
        position="tile-alpha",
        observation={
            "tile_id": "tile-alpha",
            "visible_tiles": ["tile-alpha"],
            "objects_here": [],
            "self_body": {"hunger": 80.0, "vitality": 100.0, "warmth": 100.0, "wetness": 0.0, "downed": False},
        },
        memory=[],
        goals=[],
        unanswered_questions=[],
        world_public_objects={},
        habitat_allowed_tiles=["tile-alpha"],
        habitat_movement_allowed=False,
        previous_action=None,
        timestamp_utc="2026-10-25T00:00:00Z",
        inventory={"cooked_meal": 1},
    )
    prompt = build_system_prompt(ctx)
    assert "you are carrying edible food in your belongings: cooked_meal (x1)" in prompt
    assert "You currently hold no food in your belongings" not in prompt
    assert "cooked_meal: 75" in prompt
