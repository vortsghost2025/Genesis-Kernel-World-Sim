"""Phase 10PM follow-up: the drink action must accept natural phrasing."""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tick = 100
    return rt


def _drinkable(rt, tile="cont_a_gen_0_0"):
    rt._drinkable_tile_ids = {tile}


def _try(rt, action):
    rt._vitals_for("east_adam")["thirst"] = 90.0
    return rt._execute_action("east_adam", {"action_type": "drink", **action}, 100)


def test_bare_drink_on_drinkable_tile(tmp_path):
    rt = _runtime(tmp_path)
    _drinkable(rt)
    out = _try(rt, {})
    assert out["status"] == "success", out
    assert out["source"] == "tile"
    assert rt._vitals_for("east_adam")["thirst"] == 15.0


def test_source_river_is_accepted(tmp_path):
    rt = _runtime(tmp_path)
    _drinkable(rt)
    out = _try(rt, {"source": "river", "resource_kind": "fresh_water"})
    assert out["status"] == "success", out
    assert out["source"] == "tile"


def test_source_tile_id_is_accepted(tmp_path):
    rt = _runtime(tmp_path)
    _drinkable(rt)
    out = _try(rt, {"source": "cont_a_gen_0_0", "resource_kind": "fresh_water"})
    assert out["status"] == "success", out


def test_tile_id_as_target_object_id_names_a_place(tmp_path):
    rt = _runtime(tmp_path)
    _drinkable(rt)
    out = _try(rt, {"target_object_id": "cont_a_gen_0_0"})
    assert out["status"] == "success", out
    assert out["source"] == "tile"


def test_distant_tile_id_is_rejected_with_position(tmp_path):
    rt = _runtime(tmp_path)
    _drinkable(rt, "cont_a_gen_9_0")
    out = _try(rt, {"source": "cont_a_gen_9_0"})
    assert out["status"] == "rejected"
    assert "you are at" in out["reason"]


def test_non_drinkable_tile_falls_back_to_carried_water(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 1)
    out = _try(rt, {"source": "river"})
    assert out["status"] == "success", out
    assert out["source"] == "carried"
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 0


def test_non_drinkable_tile_without_water_is_a_honest_refusal(tmp_path):
    rt = _runtime(tmp_path)
    out = _try(rt, {"source": "river"})
    assert out["status"] == "rejected"
    assert "not drinkable" in out["reason"]


def test_well_holding_water_can_be_drunk(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["well-1"] = {
        "object_id": "well-1",
        "object_type": "clay_well",
        "tile_id": "cont_a_gen_0_0",
        "contents": {"fresh_water": 2},
    }
    out = _try(rt, {"target_object_id": "well-1"})
    assert out["status"] == "success", out
    assert out["source"] == "vessel"
    assert rt._world_state.public_objects["well-1"]["contents"]["fresh_water"] == 1


def test_empty_vessel_is_refused(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["pot-1"] = {
        "object_id": "pot-1",
        "object_type": "clay_pot",
        "tile_id": "cont_a_gen_0_0",
        "contents": {},
    }
    out = _try(rt, {"target_object_id": "pot-1"})
    assert out["status"] == "rejected"
    assert "holds no fresh_water" in out["reason"]


def test_unknown_source_names_the_problem(tmp_path):
    rt = _runtime(tmp_path)
    out = _try(rt, {"source": "dewdrops"})
    assert out["status"] == "rejected"
    assert "Unknown drink source" in out["reason"]
