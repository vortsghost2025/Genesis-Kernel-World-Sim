"""Phase 10RF — an empty container's refusal must name the next step.

Measured 2026-11-14, watching the live east lane: for SIX consecutive
heartbeats (13681-13686) both agents asked to extract fresh_water 3 from a cache
that holds 0, and were refused each time with

    "Not enough fresh_water in object: holds 0, tried to extract 3"

which reports a number and not a situation. They could not tell an EMPTY
container from a nearly-empty one, so they retried while they froze at warmth 12
with vitality 1.6 and 0.8. The sibling `gather` refusal already does this
properly (it lists what the tile does have), and 10QL established the rule: a
refusal names the next step.

No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    return rt


def _cache(rt: FirstPairRuntime, contents=None, kind="supply_cache") -> str:
    obj_id = f"{kind}-1"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": kind, "tile_id": TILE,
        "materials": {}, "contents": dict(contents or {}),
    }
    return obj_id


def _extract(rt: FirstPairRuntime, obj_id: str, **materials):
    return rt._execute_action("east_adam", {
        "action_type": "use_object",
        "target_object_id": obj_id,
        "operation": "extract",
        "materials": materials,
    }, 200)


def test_an_empty_cache_says_it_is_empty_not_just_a_zero(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _cache(rt)                      # the live case: contents == {}
    out = _extract(rt, obj_id, fresh_water=3)
    assert out["status"] == "rejected"
    reason = out["reason"]
    assert "EMPTY" in reason, reason
    assert "holds no fresh_water" in reason
    assert f"Not enough fresh_water in object" not in reason, (
        "the old number-only line came back")


def test_an_empty_container_names_where_that_kind_comes_from(tmp_path):
    """The next step, per 10QL. Water must point at water."""
    rt = _runtime(tmp_path)
    obj_id = _cache(rt)
    reason = _extract(rt, obj_id, fresh_water=3)["reason"]
    assert "river or lake" in reason or "cistern" in reason, reason


def test_it_says_a_cache_only_gives_back_what_was_put_in(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _cache(rt)
    reason = _extract(rt, obj_id, fresh_water=3)["reason"]
    assert "only what was put into it" in reason, reason


def test_a_partly_full_container_says_how_much_and_what_would_work(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _cache(rt, {"fresh_water": 2})
    out = _extract(rt, obj_id, fresh_water=3)
    assert out["status"] == "rejected"
    reason = out["reason"]
    assert "holds 2" in reason, reason
    assert "Extracting 2 would work" in reason, reason
    assert "EMPTY" not in reason, "a partly full cache is not empty"


def test_a_container_that_holds_enough_still_works(tmp_path):
    """No regression: the happy path is untouched."""
    rt = _runtime(tmp_path)
    obj_id = _cache(rt, {"fresh_water": 5})
    out = _extract(rt, obj_id, fresh_water=3)
    assert out["status"] == "success", out
    assert rt._world_state.public_objects[obj_id]["contents"]["fresh_water"] == 2
    assert rt._get_agent_inventory("east_adam").get("fresh_water") == 3


def test_extracting_everything_removes_the_key(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _cache(rt, {"fresh_water": 2})
    assert _extract(rt, obj_id, fresh_water=2)["status"] == "success"
    assert "fresh_water" not in rt._world_state.public_objects[obj_id]["contents"]


def test_another_kind_gets_its_own_hint(tmp_path):
    """Stone points at stone, not at water."""
    rt = _runtime(tmp_path)
    obj_id = _cache(rt)
    reason = _extract(rt, obj_id, stone=4)["reason"]
    assert "EMPTY" in reason and "stone" in reason
    assert "gathered from a tile" in reason, reason


def test_an_invalid_amount_is_still_refused_first(tmp_path):
    rt = _runtime(tmp_path)
    obj_id = _cache(rt, {"fresh_water": 5})
    out = _extract(rt, obj_id, fresh_water=0)
    assert out["status"] == "rejected"
    assert "Invalid amount" in out["reason"]
