"""Phase 10TG: a duplicate-object_id refusal must name the remedy.

Measured 2026-11-20: west_adam spent two heartbeats on

    "Duplicate object_id: hall_eve_001 (existing: hall on cont_b_gen_27_58)"

He had copied his partner's object id. The hall was already FINISHED, so there
was nothing to advance -- and the message said neither that, nor what to do
instead. The three situations need different answers.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import FirstPairPersistenceStore  # noqa: E402
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"
EVE = "east_eve"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tile_occupancy[EVE] = TILE
    rt._vitals_for("east_adam")
    rt._vitals_for(EVE)
    return rt


def _build(rt, agent, object_id, object_type="cabin", **materials):
    return rt._execute_action(agent, {
        "action_type": "build", "object_id": object_id,
        "object_type": object_type, "tile_id": TILE,
        "description": "x", "materials": materials or {"stone": 4, "timber": 3},
    }, 100)


def _put(rt, object_id, stage, creator, *, project=True, object_type="hall",
         rung=7):
    rt._world_state.public_objects[object_id] = {
        "object_id": object_id, "object_type": object_type, "tile_id": TILE,
        "materials": {}, "contents": {}, "structure_rung": rung,
        "construction_project": project, "construction_stage": stage,
        "construction_progress": 4, "creator_agent_id": creator,
    }
    return object_id


def test_a_FINISHED_object_says_there_is_nothing_left_and_to_use_a_new_id(tmp_path):
    rt = _runtime(tmp_path)
    eve_id = str(rt._agent_view(EVE)["agent_id"])
    _put(rt, "hall_eve_001", "finished", eve_id)
    res = _build(rt, "east_adam", "hall_eve_001", "hall",
                 timber=12, stone=14, wood=8)
    assert res["status"] == "rejected", res
    assert "Duplicate object_id" in res["reason"]          # substring preserved
    assert "finished" in res["reason"], res["reason"]
    assert "nothing left to build" in res["reason"], res["reason"]
    assert "new object_id" in res["reason"], res["reason"]


def test_a_PARTNERS_unfinished_project_says_only_its_builder_can_advance_it(tmp_path):
    rt = _runtime(tmp_path)
    eve_id = str(rt._agent_view(EVE)["agent_id"])
    _put(rt, "hall_eve_002", "frame", eve_id)
    res = _build(rt, "east_adam", "hall_eve_002", "hall",
                 timber=12, stone=14, wood=8)
    assert res["status"] == "rejected", res
    assert "your partner's" in res["reason"], res["reason"]
    assert "only its builder" in res["reason"], res["reason"]


def test_a_plain_duplicate_still_names_the_way_out(tmp_path):
    rt = _runtime(tmp_path)
    adam_id = str(rt._agent_view("east_adam")["agent_id"])
    _put(rt, "box-9", "finished", adam_id, project=False, object_type="storage_box")
    res = _build(rt, "east_adam", "box-9", "hall", timber=12, stone=14, wood=8)
    assert res["status"] == "rejected", res
    assert "new object_id" in res["reason"], res["reason"]


def test_your_own_unfinished_project_is_STILL_advanced_not_refused(tmp_path):
    """The fix must not touch the advance path it sits next to."""
    from backend.world.first_pair_persistence import add_to_inventory
    rt = _runtime(tmp_path)
    adam_id = str(rt._agent_view("east_adam")["agent_id"])
    _put(rt, "cabin_adam_001", "foundation", adam_id, object_type="cabin", rung=3)
    add_to_inventory(rt._store, "east_adam", "timber", 10)
    add_to_inventory(rt._store, "east_adam", "stone", 10)
    res = _build(rt, "east_adam", "cabin_adam_001", "cabin",
                 stone=4, timber=3)
    assert res["status"] == "success", res
    assert res.get("stage") != "foundation", res
