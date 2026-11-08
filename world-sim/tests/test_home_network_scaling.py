"""Tests for Phase 10PJ: home-network scaling.

Specification: docs/phase_10ph_home_network_scaling_spec.md
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
    runtime = FirstPairRuntime(heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    runtime._load_or_initialize()
    runtime._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    return runtime


def _obj(otype: str, x: int, y: int, contents=None):
    return {
        "object_id": f"{otype}-{x}-{y}",
        "object_type": otype,
        "tile_id": f"cont_a_gen_{x}_{y}",
        "materials": {"timber": 2},
        "contents": contents or {},
        "created_heartbeat": 1,
    }


def test_network_counts_connected_tiles_once_and_cabin_weighted(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects = {
        "a": _obj("shelter", 1, 0),
        "b": _obj("shelter", 1, 0),
        "c": _obj("shelter", 2, 0),
        "d": _obj("cabin", 3, 0),
        "far": _obj("shelter", 9, 9),
    }
    assert rt._home_network_footprint("cont_a_gen_0_0") == 4  # 1 + 1 + 2; far rejected


def test_network_rejects_disconnected_and_non_roofed(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects = {
        "a": _obj("shelter", 1, 0),
        "wall": _obj("wooden_wall", 2, 0),
        "far": _obj("cabin", 6, 0),
    }
    assert rt._home_network_footprint("cont_a_gen_0_0") == 1


def test_shelter_params_scale_with_network_and_explicit_compound_fallback(tmp_path):
    rt = _runtime(tmp_path)
    for x in range(5):
        rt._world_state.public_objects[f"s{x}"] = _obj("shelter", x + 1, 0)
    tier = rt._shelter_params_for("cont_a_gen_0_0")
    assert tier["footprint"] == 5
    assert tier["comfort_floor"] == 68.0
    assert tier["shelter_decay_factor"] == 0.14
    assert tier["regen_rate"] == 1.75
    assert tier["downed_regen_rate"] == 0.9

    rt2 = _runtime(tmp_path / "more")
    rt2._world_state.compounds = {
        "x": {"rooms": {"a": {"tile_id": "cont_a_gen_0_0", "roofed": True}, "b": {"tile_id": "cont_a_gen_1_0", "roofed": True}}, "thermal_mass": 2}
    }
    assert rt2._shelter_params_for("cont_a_gen_0_0")["footprint"] == 2


def test_cellar_capacity_sees_connected_footprint(tmp_path):
    rt = _runtime(tmp_path)
    from backend.world.first_pair_persistence import add_to_inventory
    rt._world_state.public_objects = {
        "c": {**_obj("storage_cellar", 0, 0, {"wild_berries": 15})},
        "s1": _obj("shelter", 1, 0),
        "s2": _obj("shelter", 2, 0),
        "s3": _obj("cabin", 3, 0),
    }
    assert rt._cellar_food_capacity("c") == 100

    add_to_inventory(rt._store, "east_adam", "wild_berries", 100)
    rejected = rt._execute_use_object("east_adam", {
        "target_object_id": "c",
        "operation": "deposit",
        "materials": {"wild_berries": 86},
    }, 1)
    assert rejected["status"] == "rejected"
    assert "100" in rejected["reason"]
    accepted = rt._execute_use_object("east_adam", {
        "target_object_id": "c",
        "operation": "deposit",
        "materials": {"wild_berries": 85},
    }, 1)
    assert accepted["status"] == "success"
    assert rt._world_state.public_objects["c"]["contents"]["wild_berries"] == 100
