"""Phase 10QG - the cistern rung: water as a home-scale resource.

Specification: docs/phase_10qf_cistern_rung_spec.md

Measured 2026-11-12, and the reason this exists: three of four agents had
collapsed at thirst 100, and NOT ONE object in either lane had ever held a
unit of water - West had three wells and forty containers, all empty. Water
had to be carried by hand from a river, and a collapsed body cannot move.

So the cistern is the first structure whose store is measured in units
someone carried home, and the first thing in the world a collapsed body can
drink from without a partner standing over it.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

import pytest

from backend.world import first_pair_cognition_model as m
from backend.world import survival
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    add_to_inventory,
    load_inventory,
)
from backend.world.first_pair_runtime import (
    _CONSTRUCTION_STAGES,
    _CISTERN_WATER_CAPACITY,
    _RUNG_TIER_BONUS,
    _STRUCTURE_RUNGS,
    FirstPairRuntime,
    _structure_rung_of,
)

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_1_0"
    rt._world_state.tick = 100
    return rt


def _build(rt, object_id, object_type="cistern", tile=TILE, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": tile,
        "description": f"a {object_type}",
        "materials": materials,
    }, 100)


def _advance(rt, object_id, object_type="cistern", tile=TILE, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "build",
        "object_id": object_id,
        "object_type": object_type,
        "tile_id": tile,
        "description": f"a {object_type}",
        "materials": materials,
    }, 101)


def _finish(rt, object_id, object_type="cistern", tile=TILE, **materials):
    for _ in range(len(_CONSTRUCTION_STAGES)):
        res = _advance(rt, object_id, object_type, tile, **materials)
        assert res.get("status") == "success", res
        if res.get("stage") == "finished":
            return res
    raise AssertionError("never finished")


def _stock(rt, **amounts):
    for kind, amount in amounts.items():
        add_to_inventory(rt._store, "east_adam", kind, amount)


def _built_cistern(rt, tile=TILE):
    _stock(rt, timber=8, stone=12, clay=10)
    assert _build(rt, "cistern-1", "cistern", tile,
                  timber=2, stone=8, clay=6)["status"] == "success"
    _finish(rt, "cistern-1", "cistern", tile, timber=2, stone=8, clay=6)
    return rt._world_state.public_objects["cistern-1"]


def _deposit(rt, object_id, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": object_id,
        "operation": "deposit",
        "materials": materials,
    }, 200)


def _drink(rt, source="tile"):
    return rt._execute_action("east_adam", {
        "action_type": "drink",
        "source": source,
        "reason": "thirst",
    }, 200)


# ---------------------------------------------------------------------------
# the rung itself
# ---------------------------------------------------------------------------

def test_cistern_is_rung_six_with_its_floor_and_bonus():
    record = _STRUCTURE_RUNGS["cistern"]
    assert record["rung"] == 6
    assert record["floor"] == {"timber": 2, "stone": 8, "clay": 6}
    assert record["weight"] == 2
    assert _RUNG_TIER_BONUS[6] == 13
    assert _structure_rung_of("cistern")["rung"] == 6


def test_the_previous_rungs_are_untouched():
    """10QF adds a rung; it must not reprice the five that exist."""
    assert _RUNG_TIER_BONUS == {1: 0, 2: 2, 3: 4, 4: 7, 5: 11, 6: 13}
    assert _STRUCTURE_RUNGS["house"]["floor"] == {"timber": 4, "stone": 6, "clay": 4}
    assert _STRUCTURE_RUNGS["longhouse"]["floor"] == {"timber": 8, "stone": 10, "wood": 6}


def test_a_cistern_is_built_through_the_staged_path(tmp_path):
    rt = _runtime(tmp_path)
    _stock(rt, timber=8, stone=12, clay=10)
    res = _build(rt, "cistern-1", "cistern", TILE, timber=2, stone=8, clay=6)
    assert res["status"] == "success", res
    record = rt._world_state.public_objects["cistern-1"]
    assert record["structure_rung"] == 6
    assert record["construction_stage"] == "foundation"
    assert record["construction_project"] is True


def test_a_cistern_costs_its_whole_floor(tmp_path):
    """The staged-build contract (10PW): the rung floor governs the stages
    and the agent pays it from holdings, so a cistern cannot be built cheap
    by declaring less. The declaration only has to cover the floor's timber
    minimum at the first stage."""
    rt = _runtime(tmp_path)
    _stock(rt, timber=8, stone=12, clay=10)
    before = load_inventory(rt._store)["east_adam"]

    # Under-declaring the timber floor is refused outright.
    short = _build(rt, "cistern-short", "cistern", TILE, timber=1, stone=8, clay=6)
    assert short["status"] == "rejected"
    assert "structural timber" in short["reason"].lower()

    assert _build(rt, "cistern-1", "cistern", TILE,
                  timber=2, stone=8, clay=6)["status"] == "success"
    _finish(rt, "cistern-1", "cistern", TILE, timber=2, stone=8, clay=6)

    after = load_inventory(rt._store)["east_adam"]
    floor = _STRUCTURE_RUNGS["cistern"]["floor"]
    for kind, amount in floor.items():
        assert before[kind] - after[kind] == amount, (
            kind, before[kind], after[kind], amount)


def test_a_cistern_counts_toward_the_home_tier(tmp_path):
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    # footprint 2 (its own weight) + rung-6 bonus 13 = 15, the same tier
    # weight as a lone longhouse: the cistern's worth is its water, not its
    # bonus.
    assert rt._home_network_footprint(TILE) == 2
    assert rt._home_tier_weight(TILE) == 15


# ---------------------------------------------------------------------------
# water at home
# ---------------------------------------------------------------------------

def test_a_cistern_holds_water_up_to_its_capacity(tmp_path):
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    _stock(rt, fresh_water=30)
    first = _deposit(rt, "cistern-1", fresh_water=25)
    assert first["status"] == "rejected"
    assert "capacity" in first["reason"].lower()
    ok = _deposit(rt, "cistern-1", fresh_water=_CISTERN_WATER_CAPACITY)
    assert ok["status"] == "success", ok
    contents = rt._world_state.public_objects["cistern-1"]["contents"]
    assert contents["fresh_water"] == _CISTERN_WATER_CAPACITY


def test_a_filled_cistern_makes_its_tile_drinkable(tmp_path):
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    assert rt._current_tile_water_drinkable(TILE) is False
    _stock(rt, fresh_water=5)
    assert _deposit(rt, "cistern-1", fresh_water=5)["status"] == "success"
    assert rt._current_tile_water_drinkable(TILE) is True
    assert rt._cistern_water_units(TILE) == 5


def test_the_observation_names_the_source_and_the_supply(tmp_path):
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    _stock(rt, fresh_water=4)
    _deposit(rt, "cistern-1", fresh_water=4)
    env = rt._build_context("east_adam", 150).observation["environment"]
    assert env["drinkable_water"] is True
    assert env["drinkable_source"] == "cistern"
    assert env["drinkable_units"] == 4


def test_drinking_from_a_cistern_consumes_exactly_one_unit(tmp_path):
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    _stock(rt, fresh_water=3)
    _deposit(rt, "cistern-1", fresh_water=3)
    rt._vitals_for("east_adam")["thirst"] = 90.0

    res = _drink(rt)

    assert res["status"] == "success", res
    assert res["source"] == "cistern"
    contents = rt._world_state.public_objects["cistern-1"]["contents"]
    assert contents["fresh_water"] == 2
    # stored water satisfies like carried water, not like a river
    assert rt._vitals_for("east_adam")["thirst"] == round(
        90.0 - survival.DRINK_SATISFACTION["vessel"], 2)


def test_a_cistern_is_not_an_infinite_river(tmp_path):
    """Three drinks, three units: the supply is what the partner carried."""
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    _stock(rt, fresh_water=3)
    _deposit(rt, "cistern-1", fresh_water=3)
    for _ in range(3):
        assert _drink(rt)["status"] == "success"
    contents = rt._world_state.public_objects["cistern-1"]["contents"]
    assert contents.get("fresh_water", 0) == 0
    empty = _drink(rt)
    assert empty["status"] == "rejected"


def test_a_canonical_river_tile_is_still_unlimited(tmp_path):
    """The cistern must not have replaced the rivers."""
    rt = _runtime(tmp_path)
    rt._drinkable_tile_ids = {TILE}
    rt._vitals_for("east_adam")["thirst"] = 90.0
    res = _drink(rt)
    assert res["status"] == "success", res
    assert res["source"] == "tile"
    assert rt._vitals_for("east_adam")["thirst"] == round(
        90.0 - survival.DRINK_SATISFACTION["tile"], 2)


def test_a_collapsed_body_can_drink_from_a_cistern_beside_it(tmp_path):
    """The case that killed three agents in twelve hours.

    A collapsed, dehydrated body on a filled cistern's tile drinks and
    recovers, with no partner standing over it.
    """
    rt = _runtime(tmp_path)
    _built_cistern(rt)
    _stock(rt, fresh_water=6)
    _deposit(rt, "cistern-1", fresh_water=6)

    vitals = rt._vitals_for("east_adam")
    vitals["downed"] = True
    vitals["thirst"] = 100.0
    vitals["vitality"] = 4.0

    res = _drink(rt)

    assert res["status"] == "success", res
    assert res["source"] == "cistern"
    assert rt._vitals_for("east_adam")["thirst"] == round(
        100.0 - survival.DRINK_SATISFACTION["vessel"], 2)
    contents = rt._world_state.public_objects["cistern-1"]["contents"]
    assert contents["fresh_water"] == 5


# ---------------------------------------------------------------------------
# the disclosure
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=TILE, observation={}, memory=[],
        goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_the_ladder_disclosure_lists_the_cistern():
    prompt = m.build_system_prompt(_ctx())
    assert "`cistern`" in prompt
    assert "timber x2" in prompt and "stone x8" in prompt and "clay x6" in prompt
    assert "drinkable" in prompt


def test_the_cistern_disclosure_has_no_directive_phrasing():
    from backend.world.first_pair_runtime import _BANNED_DIRECTIVE_PHRASES
    prompt = m.build_system_prompt(_ctx())
    for line in prompt.splitlines():
        if "cistern" in line.lower():
            low = line.lower()
            for banned in _BANNED_DIRECTIVE_PHRASES:
                assert banned not in low, (banned, line[:140])
