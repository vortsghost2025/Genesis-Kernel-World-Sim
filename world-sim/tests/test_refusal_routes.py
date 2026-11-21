"""Phase 10TQ: two refusals that stated the problem and withheld the route.

Both were the top refusals in the world on 2026-11-21, found by auditing every
action against its outcomes rather than waiting for them to bite.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import FirstPairPersistenceStore  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._vitals_for("east_adam")
    return rt


def _drink(rt, **kwargs):
    return rt._execute_action("east_adam",
                              {"action_type": "drink", "reason": "x", **kwargs}, 100)


# --- 1. an unlit fire is a DEAD END and the refusal must say so --------------

def test_an_unlit_fire_refusal_names_the_way_out(tmp_path):
    """east tried the same unlit campfire 15 times in 700 heartbeats."""
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["campfire-007"] = {
        "object_id": "campfire-007", "object_type": "campfire", "tile_id": TILE,
        "materials": {}, "contents": {}, "creator_agent_id": "the operator",
    }
    res = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "campfire-007",
        "operation": "cook", "materials": {"edible_roots": 2}}, 100)
    assert res["status"] == "rejected", res
    reason = res["reason"]
    assert "unlit" in reason
    assert "DECLARED WHEN IT IS BUILT" in reason, reason
    assert "build a new fire" in reason, reason


def test_depositing_wood_does_not_light_a_dead_fire(tmp_path):
    """The refusal is TRUE: contents are not materials, so the dead end is real.
    If this ever starts passing, the message above must be rewritten."""
    from backend.world.first_pair_persistence import add_to_inventory
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["campfire-dead"] = {
        "object_id": "campfire-dead", "object_type": "campfire", "tile_id": TILE,
        "materials": {}, "contents": {}, "creator_agent_id": "east_adam",
    }
    add_to_inventory(rt._store, "east_adam", "wood", 5)
    dep = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "campfire-dead",
        "operation": "deposit", "materials": {"wood": 2}}, 100)
    assert dep["status"] == "success", dep
    assert rt._world_state.public_objects["campfire-dead"]["contents"]["wood"] == 2
    still = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "campfire-dead",
        "operation": "cook", "materials": {"edible_roots": 2}}, 101)
    assert still["status"] == "rejected" and "unlit" in still["reason"], still


def test_a_fire_built_with_fuel_works(tmp_path):
    from backend.world.first_pair_persistence import add_to_inventory
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["campfire-ok"] = {
        "object_id": "campfire-ok", "object_type": "campfire", "tile_id": TILE,
        "materials": {"wood": 2}, "contents": {}, "creator_agent_id": "east_adam",
    }
    add_to_inventory(rt._store, "east_adam", "wild_berries", 5)
    res = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": "campfire-ok",
        "operation": "cook", "materials": {"wild_berries": 3}}, 100)
    assert res["status"] == "success", res


# --- 2. the tile-drink refusal must name the nearest water -------------------

def test_drinking_on_a_dry_tile_names_the_nearest_water(tmp_path):
    """west hit this 8 times in 700 heartbeats while holding no water. Its
    SIBLING branch (an empty vessel) already gave the distance."""
    rt = _runtime(tmp_path)
    from backend.world.first_pair_fog_adapter import persist_known_map
    persist_known_map(rt._store.root, "east_adam", {
        "schema_version": 1, "agent_id": "x",
        "known_tiles": {"cont_a_gen_4_0": {"observed_resources": ["fresh_water"]}},
        "known_landmarks": {}, "named_places": {}, "routes": [], "hypotheses": [],
        "myths": [], "contact_evidence": [], "last_observation_tick": 1,
    })
    res = _drink(rt, source="tile")
    assert res["status"] == "rejected", res
    reason = res["reason"]
    assert "not drinkable" in reason
    assert "nearest drinkable tile" in reason, reason
    assert "cont_a_gen_4_0" in reason, reason
    assert "4 tiles east" in reason, reason


def test_the_dry_tile_refusal_still_stands_without_knowing_any_water(tmp_path):
    rt = _runtime(tmp_path)
    res = _drink(rt, source="tile")
    assert res["status"] == "rejected"
    assert "not drinkable" in res["reason"]
    assert "nearest drinkable tile" not in res["reason"]


def test_drinking_carried_water_is_unaffected(tmp_path):
    from backend.world.first_pair_persistence import add_to_inventory
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fresh_water", 1)
    res = _drink(rt, source="carried")
    assert res["status"] == "success", res
