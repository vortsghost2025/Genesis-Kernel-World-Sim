"""Phase 10QJ - water in a container on your tile is water you can drink.

The operator left a supply cache holding fresh_water on east_eve's tile. She
is STANDING (not downed), so the downed-tile path never fires, and a bare
`drink` fell through to carried water - she was at thirst 100 with a full
cache at her feet, inspecting it with use_object and unable to drink from it.

A cistern already made its tile drinkable (10QF). Generalising is the honest
fix: ANY object on the tile holding fresh_water is a source you can drink
from, and the supply is finite - one drink, one unit.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.first_pair_runtime import FirstPairRuntime


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tick = 100
    return rt


def _cache(rt, object_id="cache-1", amount=3, tile="cont_a_gen_0_0",
           object_type="supply_cache"):
    rt._world_state.public_objects[object_id] = {
        "object_id": object_id, "object_type": object_type, "tile_id": tile,
        "creator_agent_id": "the operator", "public_description": "a cache",
        "materials": {}, "contents": {"fresh_water": amount},
        "created_heartbeat": 99,
    }


def test_a_cache_of_water_makes_its_tile_drinkable(tmp_path):
    rt = _runtime(tmp_path)
    assert rt._current_tile_water_drinkable("cont_a_gen_0_0") is False
    _cache(rt)
    assert rt._current_tile_water_drinkable("cont_a_gen_0_0") is True


def test_a_standing_agent_drinks_from_the_cache_and_spends_a_unit(tmp_path):
    rt = _runtime(tmp_path)
    _cache(rt, amount=3)
    rt._vitals_for("east_adam")["thirst"] = 100.0
    rt._vitals_for("east_adam")["downed"] = False

    res = rt._execute_action("east_adam", {
        "action_type": "drink", "source": "tile", "reason": "thirst",
    }, 101)

    assert res["status"] == "success", res
    assert res["source"] == "cistern"
    assert rt._world_state.public_objects["cache-1"]["contents"]["fresh_water"] == 2
    assert rt._vitals_for("east_adam")["thirst"] == round(
        100.0 - survival.DRINK_SATISFACTION["vessel"], 2)


def test_an_empty_cache_is_not_a_source(tmp_path):
    rt = _runtime(tmp_path)
    _cache(rt, amount=1)
    rt._execute_action("east_adam", {
        "action_type": "drink", "source": "tile", "reason": "thirst",
    }, 101)
    # the cache is now empty, so the tile is dry again
    assert rt._current_tile_water_drinkable("cont_a_gen_0_0") is False


def test_the_observation_names_the_containers_supply(tmp_path):
    rt = _runtime(tmp_path)
    _cache(rt, amount=4)
    env = rt._build_context("east_adam", 150).observation["environment"]
    assert env["drinkable_water"] is True
    assert env["drinkable_source"] == "cistern"
    assert env["drinkable_units"] == 4


def test_a_cistern_still_works_exactly_as_before(tmp_path):
    """10QF behaviour must not regress under the generalisation."""
    rt = _runtime(tmp_path)
    _cache(rt, object_id="cistern-1", amount=2, object_type="cistern")
    assert rt._current_tile_water_drinkable("cont_a_gen_0_0") is True
    assert rt._cistern_water_units("cont_a_gen_0_0") == 2
