"""Phase 10RH — a collapsed body's refusal must name the action it attempted.

Measured 2026-11-14 on the live east lane: east_eve was refused FIVE heartbeats
in a row (13704-13708) for `use_object` / `extract edible_roots`, and every
refusal read

    "You have collapsed. You cannot gather, build, craft or work while your
     body is down, but you can crawl to an adjacent tile, drink, eat, speak
     and ask."

She was doing none of those four words -- she was working an object -- so a
small model reads its own action as unblocked and retries, while the food in
her own pack goes untouched. Same class as 10RF: the refusal reports a category
instead of the thing attempted.

The gate itself is unchanged and must not move: `eat`, `drink`, `move`,
`speak` and `ask` still work while down, because 10QI deliberately gave a
collapsed body its legs and its reach.

No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"


def _downed_runtime(tmp_path: Path, **carrying) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._ensure_life_state("east_adam", 1)
    # vitals are seeded lazily on first read (see _vitals_for), which is how
    # tests/test_collapsed_crawl.py marks a body down too.
    rt._vitals_for("east_adam")["downed"] = True
    for kind, amount in carrying.items():
        add_to_inventory(store, "east_adam", kind, amount)
    return rt


def _cache(rt: FirstPairRuntime, contents) -> str:
    obj_id = "supply_cache-1"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": "supply_cache", "tile_id": TILE,
        "materials": {}, "contents": dict(contents),
    }
    return obj_id


def _act(rt: FirstPairRuntime, action: dict):
    return rt._execute_action("east_adam", action, 200)


# --- the defect, stated -----------------------------------------------------

def test_extracting_while_down_names_extraction(tmp_path):
    """The exact live case: the refusal never said the word `extract`."""
    rt = _downed_runtime(tmp_path)
    obj_id = _cache(rt, {"edible_roots": 9})
    out = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                    "operation": "extract", "materials": {"edible_roots": 3}})
    assert out["status"] == "rejected"
    assert "extract" in out["reason"], out["reason"]


def test_depositing_while_down_names_depositing(tmp_path):
    rt = _downed_runtime(tmp_path, edible_roots=5)
    obj_id = _cache(rt, {})
    out = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                    "operation": "deposit", "materials": {"edible_roots": 2}})
    assert out["status"] == "rejected"
    assert "deposit" in out["reason"], out["reason"]


def test_working_an_object_is_named_as_unavailable(tmp_path):
    """The enumeration gap: `use_object` was not in the old blocked list."""
    rt = _downed_runtime(tmp_path)
    obj_id = _cache(rt, {"stone": 5})
    reason = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                       "operation": "extract",
                       "materials": {"stone": 1}})["reason"]
    assert "working an object" in reason or "work an object" in reason, reason
    assert "unavailable while your body is down" in reason, reason


def test_gathering_and_building_are_still_named(tmp_path):
    for action_type, word in (("gather", "gather"), ("build", "build"),
                              ("craft", "craft")):
        rt = _downed_runtime(tmp_path / action_type)
        reason = _act(rt, {"action_type": action_type,
                           "resource_kind": "stone"})["reason"]
        assert word in reason, (action_type, reason)


# --- and the part that actually helps ---------------------------------------

def test_it_names_the_food_the_body_is_carrying(tmp_path):
    """The live agent had edible_roots in her pack and never touched them."""
    rt = _downed_runtime(tmp_path, edible_roots=187, fresh_water=93)
    obj_id = _cache(rt, {"edible_roots": 9})
    reason = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                       "operation": "extract",
                       "materials": {"edible_roots": 3}})["reason"]
    assert "edible_roots x187" in reason, reason
    assert "fresh_water x93" in reason, reason
    assert "eating or drinking from your own pack works while down" in reason, reason


def test_it_does_not_invent_food_the_body_lacks(tmp_path):
    rt = _downed_runtime(tmp_path)          # carrying nothing
    obj_id = _cache(rt, {"edible_roots": 9})
    reason = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                       "operation": "extract",
                       "materials": {"edible_roots": 3}})["reason"]
    assert "You are carrying" not in reason, reason
    assert "otherwise rest" in reason


def test_it_says_what_still_works(tmp_path):
    rt = _downed_runtime(tmp_path)
    obj_id = _cache(rt, {"stone": 1})
    reason = _act(rt, {"action_type": "use_object", "target_object_id": obj_id,
                       "operation": "extract",
                       "materials": {"stone": 1}})["reason"]
    for word in ("crawl", "drink", "eat", "speak", "ask"):
        assert word in reason, (word, reason)


# --- the gate itself must NOT have moved ------------------------------------

def test_eating_drinking_and_crawling_still_work_while_down(tmp_path):
    """10QI's contract: collapse takes your hands, not your legs or your reach."""
    rt = _downed_runtime(tmp_path, fresh_water=2, edible_roots=2)
    assert _act(rt, {"action_type": "drink", "source": "carried",
                     "resource_kind": "fresh_water"})["status"] == "success"
    assert _act(rt, {"action_type": "eat",
                     "resource_kind": "edible_roots"})["status"] == "success"
    # a move is never refused BY THE COLLAPSE GATE, whatever the destination
    # answer is (an out-of-reach tile answers "blocked", not "collapsed")
    for target in ("cont_a_gen_1_0", "nonsense"):
        out = _act(rt, {"action_type": "move", "target_tile_id": target})
        assert "collapse" not in str(out.get("reason", "")).lower(), out
        assert out.get("status") != "rejected" or "You have collapsed" not in str(out), out
