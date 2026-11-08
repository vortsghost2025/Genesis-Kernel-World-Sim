"""Phase 10PM — thirst, food spoilage, and tool condition."""

from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world.first_pair_cognition_model import validate_action_exact
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    runtime = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    runtime._world_state.tick = 100
    return runtime


def test_thirst_rises_and_dehydrated_vitality_drains() -> None:
    assert survival.thirst_next(40.0) == 40.8
    v = survival.vitality_next(80.0, 0.0, 80.0, False, False, thirst=88.0)
    assert v < 80.0
    v_healthy = survival.vitality_next(80.0, 0.0, 80.0, False, False, thirst=10.0)
    assert v_healthy > 80.0
    assert survival.vitals_state_label({"thirst": 90.0, "hunger": 0.0, "warmth": 90.0, "vitality": 90.0}) == "dehydrated"


def test_drink_succeeds_on_drinkable_tile_and_fails_elsewhere(tmp_path) -> None:
    rt = _runtime(tmp_path)
    rt._drinkable_tile_ids = {"cont_a_gen_0_0"}
    rt._vitals_for("east_adam")["thirst"] = 80.0
    out = rt._execute_action("east_adam", {
        "action_type": "drink",
        "source": "tile",
        "reason": "thirst",
    }, 100)
    assert out["status"] == "success"
    assert rt._vitals_for("east_adam")["thirst"] == 5.0

    rt2 = _runtime(tmp_path / "dry")
    out2 = rt2._execute_action("east_adam", {
        "action_type": "drink",
        "source": "tile",
        "reason": "thirst",
    }, 100)
    assert out2["status"] == "rejected"


def test_drink_from_carried_water(tmp_path) -> None:
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 2)
    rt._vitals_for("east_adam")["thirst"] = 90.0
    out = rt._execute_action("east_adam", {
        "action_type": "drink",
        "source": "carried",
        "resource_kind": "fresh_water",
        "reason": "thirst",
    }, 100)
    assert out["status"] == "success"
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 1
    assert rt._vitals_for("east_adam")["thirst"] == 35.0


def test_drink_from_pot_and_down(tmp_path) -> None:
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["pot-1"] = {
        "object_id": "pot-1",
        "object_type": "clay_pot",
        "tile_id": "cont_a_gen_0_0",
        "contents": {"fresh_water": 1},
    }
    rt._vitals_for("east_adam")["downed"] = True
    rt._vitals_for("east_adam")["thirst"] = 90.0
    out = rt._execute_action("east_adam", {
        "action_type": "drink",
        "target_object_id": "pot-1",
        "reason": "thirst",
    }, 100)
    assert out["status"] == "success"
    assert rt._world_state.public_objects["pot-1"]["contents"] == {}
    assert rt._vitals_for("east_adam")["thirst"] == 35.0


def test_drink_action_schema() -> None:
    assert validate_action_exact({
        "action_type": "drink",
        "source": "tile",
        "reason": "thirst",
    }, "east_adam") == []
    assert validate_action_exact({
        "action_type": "drink",
        "resource_kind": "stone",
    }, "east_adam") != []


def test_freshness_spoils_carried_and_stored_food(tmp_path) -> None:
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "wild_berries", 3)
    rt._record_food_birth("east_adam", "wild_berries", 3, 100)
    rt._age_and_spoil_world_food(100 + survival.SPOILAGE_LIFETIME_HB["wild_berries"])
    assert load_inventory(rt._store)["east_adam"]["wild_berries"] == 0

    rt2 = _runtime(tmp_path / "obj")
    rt2._world_state.public_objects["cache"] = {
        "object_type": "storage",
        "tile_id": "cont_a_gen_0_0",
        "contents": {"wild_berries": 2},
        "contents_age": {"wild_berries": 100},
    }
    rt2._age_and_spoil_world_food(100 + survival.SPOILAGE_LIFETIME_HB["wild_berries"])
    assert rt2._world_state.public_objects["cache"]["contents"] == {}


def test_cellar_preservation_uses_connected_footprint(tmp_path) -> None:
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["cellar-1"] = {
        "object_type": "storage_cellar",
        "tile_id": "cont_a_gen_0_0",
        "contents": {"cooked_meal": 1},
        "contents_age": {"cooked_meal": 100},
    }
    rt._world_state.public_objects["shelter-2"] = {
        "object_type": "shelter",
        "tile_id": "cont_a_gen_1_0",
        "contents": {},
    }
    footprint, _ = rt._connected_home_network("cont_a_gen_0_0")
    assert footprint == 2
    lifetime = rt._effective_food_lifetime("cooked_meal", "cellar-1", rt._world_state.public_objects["cellar-1"])
    assert lifetime == survival.SPOILAGE_LIFETIME_HB["cooked_meal"] * 6
    rt._age_and_spoil_world_food(100 + survival.SPOILAGE_LIFETIME_HB["cooked_meal"] * 5)
    assert rt._world_state.public_objects["cellar-1"]["contents"]["cooked_meal"] == 1
    rt._age_and_spoil_world_food(100 + lifetime)
    assert rt._world_state.public_objects["cellar-1"]["contents"] == {}


def test_crafted_tool_condition_and_breaking(tmp_path) -> None:
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "stone_axe", 1)
    rt._register_tool("east_adam", "stone_axe")
    assert rt._tool_states_for("east_adam") == {"stone_axe": [24]}
    for _ in range(23):
        wore = rt._use_best_tool("east_adam", ("stone_axe",))
    assert wore["remaining"] == 1
    broke = rt._use_best_tool("east_adam", ("stone_axe",))
    assert broke["broke"] is True
    assert load_inventory(rt._store)["east_adam"].get("stone_axe", 0) == 0


def test_gather_wears_axe_and_records_food_birth(tmp_path) -> None:
    rt = _runtime(tmp_path)
    rt._current_tile_resources["cont_a_gen_0_0"] = [
        {"kind": "wood", "amount": 20},
        {"kind": "wild_berries", "amount": 20},
    ]
    add_to_inventory(rt._store, "east_adam", "stone_axe", 1)
    rt._register_tool("east_adam", "stone_axe")
    out = rt._execute_gather("east_adam", {"resource_kind": "wood", "reason": "wood"}, 100)
    assert out["status"] == "success"
    assert out["amount_gathered"] == 5
    assert out["tool_used"] == "stone_axe"
    assert out["tool_remaining"] == 23
    assert rt._food_freshness_for("east_adam").get("wood") is None

    forage = rt._execute_gather("east_adam", {"resource_kind": "wild_berries", "reason": "food"}, 100)
    assert forage["status"] == "success"
    assert rt._food_freshness_for("east_adam")["wild_berries"]["lots"][0]["born_hb"] == 100
