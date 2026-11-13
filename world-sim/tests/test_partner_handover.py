"""The partner handover: a collapsed body draws on what its partner carries.

Phase 10QE. The world promises a collapsed agent that "if food or water is
brought to your tile you will drink and eat and recover". The FOOD half
exists (10PM) and, since bddc2b2, so does the WATER half - but both only
read OBJECTS on the tile. Measured on the live East lane, 2026-11-13:

    east_eve is collapsed on cont_a_gen_-45_-2, which has ZERO objects.
    east_adam is 35 tiles away carrying 12 edible_roots and 5 fresh_water,
    walking to her because the 550B read her plea and chose to rescue her.

So the rescue run was mechanically impossible: he could arrive with exactly
what she needed and have nothing to put it in. A partner standing on the
same tile IS a supply, and the handover needs no new action, no new object
and no new vocabulary: the collapsed body simply draws on what the partner
carries while they are beside it.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime

TILE = "cont_a_gen_0_0"
OTHER_TILE = "cont_a_gen_1_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tile_occupancy["east_eve"] = TILE
    rt._world_state.tick = 100
    return rt


def _collapse(rt, agent_ref="east_eve", thirst=95.0, hunger=90.0, vitality=5.0):
    v = rt._vitals_for(agent_ref)
    v["downed"] = True
    v["thirst"] = thirst
    v["hunger"] = hunger
    v["vitality"] = vitality
    v["warmth"] = 100.0
    return v


def test_a_collapsed_body_drinks_from_a_partner_beside_it(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 5)

    rt.apply_survival_to_all(101)

    assert rt._vitals_for("east_eve")["thirst"] < 95.0
    # the partner's supply is actually spent, not copied
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 4


def test_a_collapsed_body_eats_from_a_partner_beside_it(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    add_to_inventory(rt._store, "east_adam", "edible_roots", 3)

    rt.apply_survival_to_all(101)

    assert rt._vitals_for("east_eve")["hunger"] < 90.0
    assert load_inventory(rt._store)["east_adam"]["edible_roots"] == 2


def test_a_partner_across_the_tile_boundary_reaches_nothing(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    rt._world_state.tile_occupancy["east_adam"] = OTHER_TILE
    add_to_inventory(rt._store, "east_adam", "fresh_water", 5)

    rt.apply_survival_to_all(101)

    # nothing was handed over: thirst simply climbed by its own rate
    assert rt._vitals_for("east_eve")["thirst"] == min(
        survival.THIRST_CAP, 95.0 + survival.THIRST_RATE)
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 5


def test_the_handover_does_not_touch_a_standing_body(tmp_path):
    """A standing agent has its own hands; it does not drink from its
    partner's pack because it happens to be nearby."""
    rt = _runtime(tmp_path)
    standing = rt._vitals_for("east_adam")
    standing["thirst"] = 80.0
    standing["hunger"] = 70.0
    standing["downed"] = False
    add_to_inventory(rt._store, "east_adam", "fresh_water", 5)

    rt.apply_survival_to_all(101)

    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 5
    assert rt._vitals_for("east_adam")["thirst"] >= 80.0


def test_the_handover_stops_when_the_supply_runs_out(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 1)

    rt.apply_survival_to_all(101)
    thirst_after_first = rt._vitals_for("east_eve")["thirst"]
    rt.apply_survival_to_all(102)

    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 0
    # the second heartbeat has nothing to draw on, so thirst climbs again
    assert rt._vitals_for("east_eve")["thirst"] > thirst_after_first


def test_a_collapsed_body_with_no_partner_is_unchanged(tmp_path):
    """The pre-existing paths still work exactly as they did."""
    rt = _runtime(tmp_path)
    _collapse(rt)
    rt._world_state.tile_occupancy["east_adam"] = OTHER_TILE

    before = rt._vitals_for("east_eve")["thirst"]
    rt.apply_survival_to_all(101)

    after = rt._vitals_for("east_eve")["thirst"]
    assert after == min(survival.THIRST_CAP, before + survival.THIRST_RATE)
