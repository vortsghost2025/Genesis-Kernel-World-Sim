"""Phase 10UG: a FOOD provision must HOLD food, not be created empty.

Measured 2026-11-23, live. `_apply_operator_provision_queue` built a cache with
`materials: {kind: amount}` and `contents: {}` for every non-water kind, so a food
provision was created EMPTY -- and 10SF's already-empty clearing then deleted it
as bait the first time an agent tried to extract it:

    hb15837 rejected "operator-provision-hb15832-edible_roots-1 is EMPTY"
    (the heartbeat after it was given, while east_eve sat at hunger 100)

A cache must HOLD its gift: materials the agent can extract, not a name on an
empty box. This tests the real creation path.
"""
from __future__ import annotations

import json
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


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._vitals_for("east_adam")
    return rt


def _queue(rt, kind="edible_roots", amount=5):
    p = Path(rt._store.root) / "operator_provisions_pending.json"
    p.write_text(json.dumps({"acts": [{
        "object_id": "op-food-1", "agent_ref": "east_adam", "kind": kind,
        "amount": amount, "into": "object", "tile_id": TILE, "reason": "test"}]}),
        encoding="utf-8")
    return p


def test_a_food_cache_holds_the_food_not_an_empty_box(tmp_path):
    rt = _runtime(tmp_path)
    _queue(rt)
    assert rt._apply_operator_provision_queue() == 1
    obj = rt._world_state.public_objects["op-food-1"]
    assert obj["contents"]["edible_roots"] == 5, obj


def test_extracting_from_a_food_cache_gives_food(tmp_path):
    """The live failure was an EMPTY cache: extract must return the gift."""
    rt = _runtime(tmp_path)
    _queue(rt)
    rt._apply_operator_provision_queue()
    obj_id = "op-food-1"
    res = rt._execute_action("east_adam", {
        "action_type": "use_object", "target_object_id": obj_id,
        "operation": "extract", "materials": {"edible_roots": 3}}, 200)
    assert res["status"] == "success", res
    assert res["contents"]["edible_roots"] == 2, res


def test_a_water_cache_still_holds_water(tmp_path):
    rt = _runtime(tmp_path)
    _queue(rt, kind="fresh_water", amount=4)
    rt._apply_operator_provision_queue()
    obj = rt._world_state.public_objects["op-food-1"]
    assert obj["contents"]["fresh_water"] == 4, obj
