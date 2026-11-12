"""The collapsed-body rescue path, water half.

The world tells a collapsed agent, verbatim:

    "You have collapsed (vitality 0). Your body cannot act. If food or water
     is brought to your tile you will drink and eat and recover; otherwise
     rest."

`_downed_tile_feed` built the FOOD half (Phase 10PM: "food deposited on your
tile feeds you even while you are down"). The WATER half never existed: a
vessel left on a collapsed body's tile was never drunk, so thirst only ever
fell through the `drink` action -- which a downed body is forbidden to take.

Measured on the live lanes, 2026-11-12: 3 of 4 agents collapsed, all four at
thirst 100, and zero objects anywhere in either lane holding fresh_water.
`vitality_next` discards the home tier's downed regen once thirst reaches
THIRST_WEAKEN (88) and falls back to DOWNED_PASSIVE_REGEN (0.15/hb), so a
dehydrated collapsed agent stands in ~80 heartbeats and the partner rescue
promised in that rejection string was the only faster route -- and it did
not work for water. These tests pin the completed path.
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
)
from backend.world.first_pair_runtime import FirstPairRuntime


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store")
    )
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_1_0"
    rt._world_state.tick = 100
    return rt


def _collapse(rt, agent_ref="east_adam", thirst=95.0, vitality=2.0, hunger=0.0):
    v = rt._vitals_for(agent_ref)
    v["downed"] = True
    v["thirst"] = thirst
    v["vitality"] = vitality
    v["hunger"] = hunger
    v["warmth"] = 100.0
    return v


def _vessel_on_tile(rt, tile_id="cont_a_gen_0_0", fresh_water=3):
    """An object on the agent's tile holding carried water.

    No materials: `_downed_tile_feed` reads materials and treats an unknown
    kind as edible (EAT_SATISFACTION's default of 10.0), so a vessel that
    carried a build material would be EATEN as well as drunk. The drink path
    this suite pins reads `contents` only.
    """
    return {
        "object_id": f"pot-{tile_id}",
        "object_type": "storage_cellar",
        "tile_id": tile_id,
        "creator_agent_id": "genesis-agent-" + "0" * 56,
        "materials": {},
        "contents": {"fresh_water": fresh_water},
        "created_heartbeat": 1,
    }


def _tick(rt, heartbeat=101):
    rt.apply_survival_to_all(heartbeat)


# ---------------------------------------------------------------------------
# the promise in the rejection string, made true
# ---------------------------------------------------------------------------

def test_a_collapsed_body_drinks_water_left_on_its_tile(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    rt._world_state.public_objects["pot"] = _vessel_on_tile(rt)
    before = rt._vitals_for("east_adam")["thirst"]

    _tick(rt)

    after = rt._vitals_for("east_adam")
    assert after["thirst"] < before, (before, after["thirst"])
    # and the vessel actually lost the water it gave up
    assert rt._world_state.public_objects["pot"]["contents"]["fresh_water"] == 2


def test_the_rejection_text_promise_holds_for_food_and_water_together(tmp_path):
    """Both halves at once, which is the literal sentence the world prints."""
    rt = _runtime(tmp_path)
    _collapse(rt, thirst=95.0, hunger=90.0)
    rt._world_state.public_objects["pot"] = _vessel_on_tile(rt, fresh_water=5)
    rt._world_state.public_objects["box"] = {
        "object_id": "box", "object_type": "storage_box",
        "tile_id": "cont_a_gen_0_0",
        "creator_agent_id": "genesis-agent-" + "0" * 56,
        "materials": {"edible_roots": 3}, "contents": {},
        "created_heartbeat": 1,
    }
    control = _runtime(tmp_path / "control")
    _collapse(control, thirst=95.0, hunger=90.0)

    _tick(rt)
    _tick(control)

    fed = rt._vitals_for("east_adam")
    alone = control._vitals_for("east_adam")
    assert fed["thirst"] < alone["thirst"], (fed["thirst"], alone["thirst"])
    assert fed["hunger"] < alone["hunger"], (fed["hunger"], alone["hunger"])


def test_no_vessel_on_the_tile_means_no_drink(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    before = rt._vitals_for("east_adam")["thirst"]

    _tick(rt)

    # THIRST_RATE still rises; nothing is subtracted, because nothing is there
    after = rt._vitals_for("east_adam")["thirst"]
    assert after == min(survival.THIRST_CAP, before + survival.THIRST_RATE)


def test_water_is_consumed_one_unit_per_heartbeat(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt, thirst=95.0)
    rt._world_state.public_objects["pot"] = _vessel_on_tile(rt, fresh_water=3)
    left = []
    for hb in (101, 102, 103, 104):
        _tick(rt, hb)
        left.append(rt._world_state.public_objects["pot"]["contents"].get("fresh_water", 0))

    # three units in the pot, three handed out, then the pot is empty and
    # thirst resumes climbing from wherever the last drink left it
    assert left == [2, 1, 0, 0], left
    # one vessel drink (55 satisfaction) more than covers the THIRST_RATE rise
    assert rt._vitals_for("east_adam")["thirst"] < 95.0 - 55


def test_food_alone_does_not_quench_and_water_alone_does_not_feed(tmp_path):
    """The two rescue paths are independent, each compared against a control
    runtime with nothing on the tile so the assertion is about what the path
    did rather than about what hunger_next happens to do."""
    food = _runtime(tmp_path / "food")
    _collapse(food, thirst=95.0, hunger=90.0)
    food._world_state.public_objects["box"] = {
        "object_id": "box", "object_type": "storage_box",
        "tile_id": "cont_a_gen_0_0",
        "creator_agent_id": "genesis-agent-" + "0" * 56,
        "materials": {"edible_roots": 3}, "contents": {},
        "created_heartbeat": 1,
    }
    food_control = _runtime(tmp_path / "food-control")
    _collapse(food_control, thirst=95.0, hunger=90.0)

    _tick(food)
    _tick(food_control)
    assert food._vitals_for("east_adam")["hunger"] < food_control._vitals_for("east_adam")["hunger"]
    assert food._vitals_for("east_adam")["thirst"] == food_control._vitals_for("east_adam")["thirst"]

    water = _runtime(tmp_path / "water")
    _collapse(water, thirst=95.0, hunger=90.0)
    water._world_state.public_objects["pot"] = _vessel_on_tile(water)
    water_control = _runtime(tmp_path / "water-control")
    _collapse(water_control, thirst=95.0, hunger=90.0)

    _tick(water)
    _tick(water_control)
    assert water._vitals_for("east_adam")["thirst"] < water_control._vitals_for("east_adam")["thirst"]
    assert water._vitals_for("east_adam")["hunger"] == water_control._vitals_for("east_adam")["hunger"]


def test_a_standing_agent_is_not_fed_or_watered_from_the_tile(tmp_path):
    """The rescue path is for a body that cannot act. A standing agent still
    has to act for itself, or the tile would feed everyone for free."""
    rt = _runtime(tmp_path)
    rt._vitals_for("east_adam")["thirst"] = 95.0
    rt._vitals_for("east_adam")["hunger"] = 90.0
    rt._world_state.public_objects["pot"] = _vessel_on_tile(rt, fresh_water=5)

    _tick(rt)

    after = rt._vitals_for("east_adam")
    assert after["thirst"] >= 95.0, after
    assert after["hunger"] >= 90.0, after
    assert rt._world_state.public_objects["pot"]["contents"]["fresh_water"] == 5


def test_rescue_water_is_not_stolen_from_an_adjacent_tile(tmp_path):
    """Only this collapsed body's own tile. A pot two tiles away is not
    'brought to your tile'."""
    rt = _runtime(tmp_path)
    _collapse(rt)
    rt._world_state.public_objects["pot"] = _vessel_on_tile(
        rt, tile_id="cont_a_gen_3_0", fresh_water=5)
    before = rt._vitals_for("east_adam")["thirst"]

    _tick(rt)

    after = rt._vitals_for("east_adam")
    assert after["thirst"] == min(survival.THIRST_CAP, before + survival.THIRST_RATE)
    assert rt._world_state.public_objects["pot"]["contents"]["fresh_water"] == 5


def test_the_collapsed_gate_still_refuses_an_acting_body(tmp_path):
    """Fixing the passive path must not quietly let a collapsed agent act."""
    rt = _runtime(tmp_path)
    _collapse(rt)
    out = rt._execute_action("east_adam", {
        "action_type": "gather", "resource_kind": "wood", "reason": "x",
    }, 101)
    assert out["status"] == "rejected"
    assert "collapsed" in out["reason"].lower()
