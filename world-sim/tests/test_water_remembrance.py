"""Phase 10QH - water must be REMEMBERABLE.

The defect, measured 2026-11-13 after twelve hours of the lanes dying:

    tiles in the world whose water.drinkable is true ......... 2163
    ...of those listing fresh_water as a resource ............ 1
    east_eve known tiles .................................... 1592
    east_eve known tiles with water ......................... 0
    all four agents ......................................... thirst 100, dry ground

The observation has carried each visible tile's `water` since a previous
phase fixed the fog adapter ("the fact was present in the true map and
dropped here"). The known-map merge then read only `resources` and dropped
it a SECOND time, one step later. So an agent could know about water only
while standing in it, could never remember a river, and the rollup that
answers "where have I seen X?" never once named water.

These tests pin the merge, the rollup, and the end-to-end memory.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_runtime import FirstPairRuntime


def _detail(tid, resources=None, water=None):
    return {
        "tile_id": tid,
        "terrain": "grassland",
        "biome": "temperate_valley",
        "landmarks": [],
        "resources": list(resources or []),
        "water": water if water is not None else {},
        "hazards": [],
    }


def _observed(known_map, tid):
    entry = (known_map.get("known_tiles") or {}).get(tid) or {}
    return entry.get("observed_resources") or []


def test_a_drinkable_tile_is_recorded_as_water():
    known = {"known_tiles": {}}
    obs = {"visible_tile_details": [
        _detail("cont_a_gen_-40_0", resources=["wild_berries"],
                water={"type": "river", "drinkable": True}),
    ]}
    out, changed = FirstPairRuntime._merge_visible_resources_into_known_map(
        known, obs, tick=100)
    assert changed is True
    assert "fresh_water" in _observed(out, "cont_a_gen_-40_0")
    # and the tile's real resources are kept, not replaced
    assert "wild_berries" in _observed(out, "cont_a_gen_-40_0")


def test_a_dry_tile_is_not_recorded_as_water():
    known = {"known_tiles": {}}
    for water in ({}, {"type": "none"}, {"type": "river", "drinkable": False}):
        obs = {"visible_tile_details": [_detail("cont_a_gen_1_1", water=water)]}
        out, _ = FirstPairRuntime._merge_visible_resources_into_known_map(
            known, obs, tick=100)
        assert "fresh_water" not in _observed(out, "cont_a_gen_1_1"), water


def test_seeing_a_river_twice_does_not_duplicate_it():
    known = {"known_tiles": {}}
    detail = _detail("cont_a_gen_-40_0", water={"type": "river", "drinkable": True})
    for tick in (10, 20, 30):
        known, _ = FirstPairRuntime._merge_visible_resources_into_known_map(
            known, {"visible_tile_details": [detail]}, tick=tick)
    resources = _observed(known, "cont_a_gen_-40_0")
    assert resources.count("fresh_water") == 1, resources


def test_a_tile_that_already_lists_water_as_a_resource_is_not_doubled():
    known = {"known_tiles": {}}
    obs = {"visible_tile_details": [
        _detail("cont_a_origin_000", resources=["fresh_water"],
                water={"type": "river", "drinkable": True}),
    ]}
    out, _ = FirstPairRuntime._merge_visible_resources_into_known_map(
        known, obs, tick=100)
    assert _observed(out, "cont_a_origin_000").count("fresh_water") == 1


def test_the_resource_rollup_then_names_the_river():
    """The rollup is the world's own answer to "where have I seen X?" -
    and until this fix it could never answer that for water."""
    known = {
        "known_tiles": {
            "cont_a_gen_-40_0": {
                "tile_id": "cont_a_gen_-40_0",
                "observed_resources": ["fresh_water"],
            },
            "cont_a_gen_-11_-5": {
                "tile_id": "cont_a_gen_-11_-5",
                "observed_resources": ["clay"],
            },
        }
    }
    rollup = FirstPairRuntime._observed_resource_rollup(known)
    assert "fresh_water: cont_a_gen_-40_0" in rollup, rollup


def test_an_agent_walks_over_a_river_and_can_find_it_again():
    """End to end: the observation the fog adapter builds for a river tile
    survives the merge and comes back out of the rollup."""
    known = {"known_tiles": {}}
    obs = {"visible_tile_details": [
        _detail("cont_a_gen_0_0", resources=["wild_berries"], water={}),
        _detail("cont_a_gen_-1_0", resources=[], water={"type": "river", "drinkable": True}),
        _detail("cont_a_gen_-2_0", resources=["stone"], water={}),
    ]}
    known, _ = FirstPairRuntime._merge_visible_resources_into_known_map(
        known, obs, tick=500)

    rollup = FirstPairRuntime._observed_resource_rollup(known)
    assert "fresh_water: cont_a_gen_-1_0" in rollup
    assert "stone: cont_a_gen_-2_0" in rollup
