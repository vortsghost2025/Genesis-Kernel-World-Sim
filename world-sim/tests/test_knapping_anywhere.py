"""Phase 10QL(b) - make the world's own claim about knapping true.

`hew_timber` without a tool says, verbatim:

    "Cannot hew timber bare-handed. Holds no axe or knapped blade; with 2
     stone and 1 wood a blade can be knapped on the spot."

It cannot be knapped on the spot. `use_object` operation 'craft' requires the
target to be a crafting_surface, forge, workbench or workshop:

    "Crafting requires a crafting surface, not a {type}"

So the world promised a route it then refused - the same class of defect as
"the operator does not hand out anything", and the reason the Eves have been
stuck for the whole history:

    east_eve  tools=NONE  stone=104 wood=91   (a stone_axe costs stone 2 + wood 1)
    west_eve  tools=NONE  stone=1   wood=211

Neither can ever hew timber, so neither can ever build anything that needs it,
while their partners hold axes and 29/196 timber. ~700 refusals of "Insufficient
timber" across the history are that one missing step.

The fix makes the claim TRUE rather than rewriting it to match the limitation,
and it is scoped to the two recipes the world already calls knapping: knapping
is the archetypal no-workshop craft. A stone_axe or a flint_knife can be made
wherever the agent stands; everything else still needs a surface.
"""
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

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tick = 100
    return rt


def _craft(rt, materials, target=None):
    action = {"action_type": "use_object", "operation": "craft",
              "materials": materials, "reason": "knap a blade"}
    if target is not None:
        action["target_object_id"] = target
    return rt._execute_action("east_adam", action, 101)


def test_a_stone_axe_can_be_knapped_where_the_agent_stands(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    add_to_inventory(rt._store, "east_adam", "wood", 3)
    res = _craft(rt, {"stone": 2, "wood": 1})
    assert res["status"] == "success", res
    inv = load_inventory(rt._store)["east_adam"]
    assert inv.get("stone_axe", 0) == 1
    assert inv.get("stone", 0) == 3 and inv.get("wood", 0) == 2


def test_a_flint_knife_can_be_knapped_where_the_agent_stands(tmp_path):
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "flint", 4)
    add_to_inventory(rt._store, "east_adam", "wood", 2)
    res = _craft(rt, {"flint": 2, "wood": 1})
    assert res["status"] == "success", res
    assert load_inventory(rt._store)["east_adam"].get("flint_knife", 0) == 1


def test_everything_else_still_needs_a_surface(tmp_path):
    """The relaxation is scoped to knapping. A woven basket still needs a
    workshop, and the refusal must say so."""
    rt = _runtime(tmp_path)
    add_to_inventory(rt._store, "east_adam", "fiber_plants", 6)
    add_to_inventory(rt._store, "east_adam", "wood", 4)
    res = _craft(rt, {"fiber_plants": 4, "wood": 2})
    assert res["status"] == "rejected", res
    assert "crafting surface" in res["reason"]


def test_naming_a_non_surface_does_not_block_a_knapped_blade(tmp_path):
    """An agent that wants a stone_axe and names a nearby campfire as its
    "workbench" has said what it means. Refusing that would be the same
    pedantic wall that produced hundreds of these refusals - the blade is
    struck wherever the agent sits, so what it names is irrelevant."""
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["fire-1"] = {
        "object_id": "fire-1", "object_type": "campfire", "tile_id": TILE,
        "creator_agent_id": "x", "public_description": "a fire",
        "materials": {"wood": 1}, "contents": {}, "created_heartbeat": 1,
    }
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    add_to_inventory(rt._store, "east_adam", "wood", 3)
    res = _craft(rt, {"stone": 2, "wood": 1}, target="fire-1")
    assert res["status"] == "success", res
    assert load_inventory(rt._store)["east_adam"].get("stone_axe", 0) == 1


def test_a_real_surface_still_works_for_knapping(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["bench-1"] = {
        "object_id": "bench-1", "object_type": "crafting_surface",
        "tile_id": TILE, "creator_agent_id": "x",
        "public_description": "a bench", "materials": {"wood": 2},
        "contents": {}, "created_heartbeat": 1,
    }
    add_to_inventory(rt._store, "east_adam", "stone", 5)
    add_to_inventory(rt._store, "east_adam", "wood", 3)
    res = _craft(rt, {"stone": 2, "wood": 1}, target="bench-1")
    assert res["status"] == "success", res


def test_the_hew_promise_and_the_craft_rule_now_agree(tmp_path):
    """The whole point: the sentence hew_timber prints must be executable."""
    rt = _runtime(tmp_path)
    res = rt._execute_action("east_adam", {
        "action_type": "hew_timber", "reason": "need timber"}, 101)
    assert "knapped on the spot" in res["reason"]
    add_to_inventory(rt._store, "east_adam", "stone", 2)
    add_to_inventory(rt._store, "east_adam", "wood", 1)
    assert _craft(rt, {"stone": 2, "wood": 1})["status"] == "success"
