"""Phase 10QU — the payoff ladder is keyed to what a home IS, not how big.

Operator, 2026-11-14: "maybe there just isint enough benefits for them to build
a single main shelter and then just have smaller temp shelter when exploring."

Measured, he was right. Footprint drove the warmth lookup, so twelve rung-1
shacks out-warmed one well-built house, and a lone lean-out's floor of 45.0 was
already 25 points above FREEZE_THRESHOLD (20) — survival stopped being a reason
to build anything better. The only rung-gated payoffs (cellar food at rung 5,
cistern water at rung 6) sit at the TOP of the ladder, so the middle earned
nothing.

These tests pin the new ladder, the invariant that keeps it safe, and the two
new water facts. Pure: tempdir stores, no provider, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival  # noqa: E402
from backend.world.first_pair_persistence import FirstPairPersistenceStore  # noqa: E402
from backend.world.first_pair_runtime import (  # noqa: E402
    _CISTERN_WATER_CAPACITY,
    _HOME_NETWORK_TIERS,
    _THERMAL_TIER_BY_RUNG,
    _WATER_STORE_BY_RUNG,
    FirstPairRuntime,
    _home_network_tier,
    _home_thermal_index,
)


def _runtime(tmp_path: Path, pair: str = "test") -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / pair)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    return rt


def _dwell(rt: FirstPairRuntime, tile: str, kind: str, rung: int) -> str:
    """Put one completed roofed structure of `kind` on a tile."""
    obj_id = f"{kind}-{tile}"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id,
        "object_type": kind,
        "tile_id": tile,
        "materials": {},
        "contents": {},
        "structure_rung": rung,
        "construction_stage": "finished",
        "construction_progress": 4,
    }
    return obj_id


TILES = ("cont_a_gen_0_0", "cont_a_gen_1_0", "cont_a_gen_0_1", "cont_a_gen_1_1",
         "cont_a_gen_2_0", "cont_a_gen_2_1", "cont_a_gen_3_0", "cont_a_gen_3_1",
         "cont_a_gen_4_0", "cont_a_gen_4_1", "cont_a_gen_5_0", "cont_a_gen_5_1")


# --- the ladder itself ------------------------------------------------------

def test_the_ladder_rises_with_rung():
    """Each rung earns a strictly better floor, decay, rest and downed regen."""
    rows = [_home_network_tier(_home_thermal_index(r)) for r in range(1, 7)]
    floors = [row[0] for row in rows]
    regens = [row[2] for row in rows]
    downed = [row[3] for row in rows]
    assert floors == sorted(floors) and len(set(floors)) == 6
    assert regens == sorted(regens) and len(set(regens)) == 6
    assert downed == sorted(downed) and len(set(downed)) == 6


def test_no_new_deaths_the_worst_case_floor_is_unchanged():
    """THE safety invariant: a lone rung-1 structure reads exactly what it did
    before this phase (45.0), which is 25 points above the freeze threshold.
    Every other rung is higher, so no reachable state newly drains vitality."""
    floor, _decay, _regen, _downed, _approach = _home_network_tier(_home_thermal_index(1))
    assert floor == survival.SHELTER_COMFORT_FLOOR == 45.0
    for rung in range(1, 7):
        row_floor = _home_network_tier(_home_thermal_index(rung))[0]
        assert row_floor > survival.FREEZE_THRESHOLD, (
            f"rung {rung} floor {row_floor} is at/below the freeze threshold "
            f"{survival.FREEZE_THRESHOLD} - this phase must not make cold lethal")


def test_a_house_out_warms_a_shanty_town_of_the_same_size(tmp_path):
    """THE defect, stated directly. Twelve rung-1 shacks used to beat a house."""
    rt = _runtime(tmp_path, "shanty")
    for tile in TILES:
        _dwell(rt, tile, "lean-to", 1)
    shack = rt._shelter_params_for(TILES[0])

    rt2 = _runtime(tmp_path, "house")
    _dwell(rt2, TILES[0], "house", 4)
    house = rt2._shelter_params_for(TILES[0])

    assert shack["tier_weight"] > house["tier_weight"], "size still out-weighs quality"
    assert house["comfort_floor"] > shack["comfort_floor"]
    assert house["regen_rate"] > shack["regen_rate"]
    assert house["downed_regen_rate"] > shack["downed_regen_rate"]


def test_footprint_alone_no_longer_raises_the_floor(tmp_path):
    """Adding rung-1 shacks must not buy warmth - that is the whole change."""
    rt = _runtime(tmp_path, "grow")
    _dwell(rt, TILES[0], "lean-to", 1)
    one = rt._shelter_params_for(TILES[0])
    for tile in TILES[1:]:
        _dwell(rt, tile, "lean-to", 1)
    twelve = rt._shelter_params_for(TILES[0])
    assert twelve["footprint"] > one["footprint"], "the network did not grow"
    assert twelve["comfort_floor"] == one["comfort_floor"]
    assert twelve["regen_rate"] == one["regen_rate"]


def test_upgrading_one_structure_in_the_network_raises_it(tmp_path):
    """One better home among the shacks is enough - the incentive to build it."""
    rt = _runtime(tmp_path, "upgrade")
    for tile in TILES:
        _dwell(rt, tile, "lean-to", 1)
    before = rt._shelter_params_for(TILES[0])
    _dwell(rt, TILES[0], "house", 4)          # upgrade one dwelling
    after = rt._shelter_params_for(TILES[0])
    assert after["comfort_floor"] > before["comfort_floor"]
    assert after["regen_rate"] > before["regen_rate"]


# --- disclosure equals physics ----------------------------------------------

def test_the_disclosed_floor_is_the_floor_the_physics_uses(tmp_path):
    """A house must not be TOLD a floor it does not get (10PW's class of bug)."""
    rt = _runtime(tmp_path, "disclose")
    _dwell(rt, TILES[0], "house", 4)
    _dwell(rt, TILES[1], "lean-to", 1)
    disclosed = rt._home_rung_for(TILES[0])
    physics = rt._shelter_params_for(TILES[0])
    assert disclosed["comfort_floor"] == physics["comfort_floor"]
    assert disclosed["cold_decay"] == physics["shelter_decay_factor"]
    assert disclosed["rest_regen"] == physics["regen_rate"]
    assert disclosed["downed_regen"] == physics["downed_regen_rate"]


def test_a_legacy_structures_rank_still_reads_as_rung_one(tmp_path):
    """The live world's 140 rung-less `shelter` objects must not crash or read
    better than a lean-to."""
    rt = _runtime(tmp_path, "legacy")
    obj_id = _dwell(rt, TILES[0], "shelter", 1)
    rt._world_state.public_objects[obj_id].pop("structure_rung", None)
    params = rt._shelter_params_for(TILES[0])
    assert params["comfort_floor"] == 45.0


# --- space was not nerfed ----------------------------------------------------

def test_cellar_food_capacity_still_scales_with_size(tmp_path):
    """Size buys SPACE. This phase must not remove that."""
    rt = _runtime(tmp_path, "cellar")
    small = _dwell(rt, TILES[0], "lean-to", 1)
    capacity_small = rt._cellar_food_capacity(small)
    for tile in TILES[1:6]:
        _dwell(rt, tile, "lean-to", 1)
    assert rt._cellar_food_capacity(small) > capacity_small


# --- the water store --------------------------------------------------------

def test_the_water_store_rises_with_rung_and_the_cistern_still_wins():
    stores = [_WATER_STORE_BY_RUNG[r] for r in range(1, 7)]
    assert stores == sorted(stores) and len(set(stores)) == 6
    assert _WATER_STORE_BY_RUNG[1] > 0, "a lean-to must hold a little, not none"
    assert _WATER_STORE_BY_RUNG[6] == _CISTERN_WATER_CAPACITY == 20


def _deposit(rt, object_id, hb=200, **materials):
    """The established deposit shape, as tests/test_cistern_rung.py uses it."""
    return rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": object_id,
        "operation": "deposit",
        "materials": materials,
    }, hb)


def test_a_home_banks_water_up_to_its_store_and_no_further(tmp_path):
    rt = _runtime(tmp_path, "watercap")
    obj_id = _dwell(rt, TILES[0], "house", 4)
    store = rt._home_water_capacity(obj_id)
    assert store == _WATER_STORE_BY_RUNG[4]

    rt._world_state.tile_occupancy["east_adam"] = TILES[0]
    rt._ensure_life_state("east_adam", 1)
    from backend.world.first_pair_persistence import add_to_inventory
    add_to_inventory(rt._store, "east_adam", "fresh_water", store + 5)

    ok = _deposit(rt, obj_id, fresh_water=store)
    assert ok["status"] == "success", ok

    over = _deposit(rt, obj_id, hb=201, fresh_water=1)
    assert over["status"] == "rejected", over
    assert str(store) in over["reason"], "the refusal must name the capacity"


def test_a_home_holding_water_makes_its_tile_drinkable(tmp_path):
    """The case that killed three of four agents: water at the tile you fall on."""
    rt = _runtime(tmp_path, "waterdrink")
    obj_id = _dwell(rt, TILES[0], "cabin", 3)
    rt._world_state.public_objects[obj_id]["contents"] = {"fresh_water": 4}
    assert rt._current_tile_water_drinkable(TILES[0]) is True
    assert rt._cistern_water_units(TILES[0]) == 4
    empty = _dwell(rt, TILES[1], "cabin", 3)
    assert rt._current_tile_water_drinkable(TILES[1]) is False


# --- the tables this phase must NOT have touched -----------------------------

def test_the_pinned_tier_and_bonus_tables_are_untouched():
    assert _HOME_NETWORK_TIERS[0] == (1, 45.0, 0.45, 1.00, 0.40, 0.10)
    assert _HOME_NETWORK_TIERS[-1] == (36, 92.0, 0.06, 2.80, 1.70, 0.30)
    assert set(_THERMAL_TIER_BY_RUNG) == {1, 2, 3, 4, 5, 6}
    assert max(_THERMAL_TIER_BY_RUNG.values()) <= _HOME_NETWORK_TIERS[-1][0]
