"""Phase 10QL - refusals that name the next step, and a drink the model can reach.

Three clusters from the whole-history refusal audit (13,356 heartbeats), all
of them the world's fault rather than the agents':

  ~340  "Invalid drink source; use tile, carried fresh_water, or a clay_pot
        object" and "Unknown drink source None" / "<tile>" / "river on <tile>"
        - the drink action refused the phrasings they actually wrote.
  ~700  "Insufficient timber: need N, hold N" and "A shelter needs at least N
        structural timber ... Fell trees with hew_timber once you hold an axe"
        - the refusal named the tool and not the route to the tool.
    19  "A foundation is not a structure this world knows how to raise."
        - `foundation` is a construction STAGE; the agent named a stage.

Operator, 2026-11-13: "what else are they having issues with that are things
that you should have fixed i cant imagine your 2 minute process fixed 100
questions and problems they had."
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


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tick = 100
    return rt


def _drink(rt, **fields):
    action = {"action_type": "drink", "reason": "thirst"}
    action.update(fields)
    return rt._execute_action("east_adam", action, 101)


# ---------------------------------------------------------------------------
# A. the drink the model actually writes
# ---------------------------------------------------------------------------

def test_a_bare_drink_with_no_source_is_not_a_refusal(tmp_path):
    """41 x "Unknown drink source None" in East alone. A drink with no source
    is the plainest thing in the world: the tile, then what you carry."""
    rt = _runtime(tmp_path)
    rt._drinkable_tile_ids = {TILE}
    rt._vitals_for("east_adam")["thirst"] = 90.0
    res = _drink(rt, source=None)
    assert res["status"] == "success", res
    assert res["source"] == "tile"


def test_a_source_naming_a_tile_in_a_phrase_is_understood(tmp_path):
    """"river on <tile>" and a bare tile id both name a place to drink."""
    rt = _runtime(tmp_path)
    rt._drinkable_tile_ids = {TILE}
    rt._vitals_for("east_adam")["thirst"] = 90.0
    for phrase in (TILE, f"river on {TILE}", f"the water at {TILE}",
                   f"drink from {TILE}", f"lake {TILE}"):
        rt._vitals_for("east_adam")["thirst"] = 90.0
        res = _drink(rt, source=phrase)
        assert res["status"] == "success", (phrase, res)


def test_a_source_that_is_only_a_water_word_means_here(tmp_path):
    rt = _runtime(tmp_path)
    rt._drinkable_tile_ids = {TILE}
    rt._vitals_for("east_adam")["thirst"] = 90.0
    for phrase in ("river", "the river", "water", "this river", "stream"):
        rt._vitals_for("east_adam")["thirst"] = 90.0
        res = _drink(rt, source=phrase)
        assert res["status"] == "success", (phrase, res)


def test_a_bare_drink_falls_back_to_carried_water(tmp_path):
    """With nothing drinkable here and nothing named, carried water is the
    answer - not a rejection."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 2)
    rt._vitals_for("east_adam")["thirst"] = 90.0
    res = _drink(rt, source=None)
    assert res["status"] == "success", res
    assert res["source"] == "carried"
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 1


def test_a_genuinely_dry_drink_is_still_an_honest_refusal(tmp_path):
    rt = _runtime(tmp_path)
    rt._vitals_for("east_adam")["thirst"] = 90.0
    res = _drink(rt, source=None)
    assert res["status"] == "rejected", res
    assert "not drinkable" in res["reason"].lower()


def test_a_named_tile_that_is_dry_still_says_so(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_1"
    rt._vitals_for("east_adam")["thirst"] = 90.0
    res = _drink(rt, source="cont_a_gen_0_0")
    assert res["status"] == "rejected", res
    assert "not drinkable" in res["reason"].lower()


# ---------------------------------------------------------------------------
# B. the refusal names the route to the tool
# ---------------------------------------------------------------------------

def test_the_timber_refusal_names_the_craft_route(tmp_path):
    """~700 refusals told them "hold an axe" without saying how to get one."""
    rt = _runtime(tmp_path)
    res = rt._execute_action("east_adam", {
        "action_type": "build", "object_id": "s1", "object_type": "shelter",
        "tile_id": TILE, "description": "a shelter", "materials": {"wood": 1},
    }, 101)
    assert res["status"] == "rejected", res
    reason = res["reason"]
    assert "structural timber" in reason
    # the route, not just the requirement
    assert "stone_axe" in reason and "stone x2" in reason and "wood x1" in reason
    assert "crafting" in reason.lower()


def test_the_hew_timber_refusal_names_the_route(tmp_path):
    """This one was ALREADY good - "with 2 stone and 1 wood a blade can be
    knapped on the spot" names the route in its own words. Pinned so it stays
    that way, and written semantically rather than against one phrasing."""
    rt = _runtime(tmp_path)
    res = rt._execute_action("east_adam", {
        "action_type": "hew_timber", "reason": "need timber",
    }, 101)
    assert res["status"] == "rejected", res
    reason = res["reason"].lower()
    assert "axe" in reason or "blade" in reason
    # and the materials by which a blade is obtained
    assert "stone" in reason and "wood" in reason


# ---------------------------------------------------------------------------
# C. a stage named as a type is told what it is
# ---------------------------------------------------------------------------

def test_naming_a_construction_stage_as_a_type_says_it_is_a_stage(tmp_path):
    """19 x "A foundation is not a structure this world knows how to raise."
    `foundation` is a STAGE of every build, so the refusal must say that.

    Only the stages that actually reach this check are asserted: `walls` and
    `roofed` contain the component words "wall" and "roof", so they are caught
    earlier by the structural-timber check - which is correct behaviour, since
    a wall and a roof really are buildable components.
    """
    rt = _runtime(tmp_path)
    for stage in ("foundation", "frame", "finished"):
        res = rt._execute_action("east_adam", {
            "action_type": "build", "object_id": f"x-{stage}",
            "object_type": stage, "tile_id": TILE,
            "description": f"a {stage}", "materials": {"timber": 2},
        }, 101)
        assert res["status"] == "rejected", (stage, res)
        reason = res["reason"].lower()
        assert "stage" in reason, (stage, res["reason"])
        assert "structure" in reason
