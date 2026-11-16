"""Phase 10SD — a finished gift leaves nothing, and a dead target stops pulling.

Measured 2026-11-16, live: both pairs carried EIGHT operator-provision objects
and SEVEN of them were empty, sitting on the agents' own tiles as `supply_cache`
objects whose names still advertised what they used to hold
(`operator-provision-hb13608-edible_roots-1`). Both east agents were extracting
from one of them, and an OPEN GOAL existed to do exactly that --

    "food_acquisition: Extract edible_roots from
     operator-provision-hb13608-edible_roots-1 supply cache"

-- so the loop could not end on its own: the refuse-and-retry cycle had a
persistent object to target and a goal telling it to.

Two rules, one on each side:

* an operator provision is a GIFT, not a container: when an extract empties it,
  the object is removed. A finished gift leaves nothing behind to be bait;
* a goal that names an object which no longer exists can never be satisfied, so
  goal hygiene now retires it FIRST and before the age gate -- a dead target is
  dead now, not after STALE_GOAL_AGE_HB. Object-id shaped tokens only: a goal may
  legitimately name a destination TILE, and retiring those would silently kill
  travel goals.

No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    GoalRecord,
)
from backend.world.first_pair_runtime import (  # noqa: E402
    FirstPairRuntime,
    _goal_names_a_missing_object,
)

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._vitals_for("east_adam")
    return rt


def _provision(rt: FirstPairRuntime, contents: dict, oid: str) -> str:
    rt._world_state.public_objects[oid] = {
        "object_id": oid, "object_type": "supply_cache", "tile_id": TILE,
        "materials": {}, "contents": dict(contents),
    }
    return oid


def _extract(rt: FirstPairRuntime, oid: str, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": oid,
        "operation": "extract", "materials": materials}, 200)


# --- 1. a finished gift leaves nothing --------------------------------------

def test_an_emptied_operator_provision_is_removed(tmp_path):
    rt = _runtime(tmp_path)
    oid = _provision(rt, {"edible_roots": 2},
                     "operator-provision-hb1-edible_roots-1")
    assert _extract(rt, oid, edible_roots=2)["status"] == "success"
    assert oid not in rt._world_state.public_objects, (
        "an emptied gift must not linger as bait")


def test_a_provision_with_something_left_stays(tmp_path):
    rt = _runtime(tmp_path)
    oid = _provision(rt, {"edible_roots": 5},
                     "operator-provision-hb1-edible_roots-1")
    _extract(rt, oid, edible_roots=2)
    assert oid in rt._world_state.public_objects
    assert rt._world_state.public_objects[oid]["contents"]["edible_roots"] == 3


def test_an_ordinary_container_is_not_removed_when_emptied(tmp_path):
    """Only a gift leaves; a real cache is the agent's own storage."""
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["cache-1"] = {
        "object_id": "cache-1", "object_type": "supply_cache", "tile_id": TILE,
        "materials": {}, "contents": {"edible_roots": 1}}
    assert _extract(rt, "cache-1", edible_roots=1)["status"] == "success"
    assert "cache-1" in rt._world_state.public_objects


# --- 2. a dead target stops pulling ----------------------------------------

def test_a_goal_naming_a_missing_object_is_detected():
    assert _goal_names_a_missing_object(
        "Extract edible_roots from operator-provision-hb13608-edible_roots-1 "
        "supply cache", {})
    assert not _goal_names_a_missing_object(
        "Extract edible_roots from operator-provision-hb13608-edible_roots-1 "
        "supply cache",
        {"operator-provision-hb13608-edible_roots-1": {}})


def test_a_goal_naming_a_tile_is_never_retired_this_way():
    """A destination tile is legitimate; the world has no object on it."""
    assert not _goal_names_a_missing_object(
        "Deliver 3 fresh_water and 3 edible_roots to Adam at cont_a_gen_-43_6", {})
    assert not _goal_names_a_missing_object(
        "return to public-shared-center", {})


def test_a_goal_with_no_object_shaped_token_is_untouched():
    for desc in ("gather wild_berries to reduce hunger",
                 "Continue building shelter walls",
                 "maintain survival",
                 "Obtain water to satisfy thirst"):
        assert not _goal_names_a_missing_object(desc, {}), desc


def test_goal_hygiene_retires_a_dead_target_immediately(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    dead = GoalRecord(
        goal_id="food_acquisition", agent_id=agent_id,
        description="Extract edible_roots from "
                    "operator-provision-hb13608-edible_roots-1 supply cache",
        status="active", created_heartbeat=1)
    rt._goals.append(dead)
    retired = rt.retire_stale_goals("east_adam", 2)   # young: no age gate
    assert dead.status == "retired"
    assert dead in retired


def test_a_live_target_is_not_retired(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    _provision(rt, {"edible_roots": 4}, "operator-provision-hb9-edible_roots-1")
    live = GoalRecord(
        goal_id="food_acquisition", agent_id=agent_id,
        description="Extract edible_roots from "
                    "operator-provision-hb9-edible_roots-1 supply cache",
        status="active", created_heartbeat=1)
    rt._goals.append(live)
    rt.retire_stale_goals("east_adam", 2)
    assert live.status == "active"


def test_the_two_rules_compose(tmp_path):
    """Empty the gift, and the goal that named it retires on the same pass."""
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    oid = _provision(rt, {"edible_roots": 1},
                     "operator-provision-hb7-edible_roots-1")
    goal = GoalRecord(
        goal_id="g1", agent_id=agent_id,
        description=f"Extract edible_roots from {oid} supply cache",
        status="active", created_heartbeat=1)
    rt._goals.append(goal)
    assert _extract(rt, oid, edible_roots=1)["status"] == "success"
    rt.retire_stale_goals("east_adam", 2)
    assert oid not in rt._world_state.public_objects
    assert goal.status == "retired"
