"""Phase 10TO: a PACK provision must be applied ONCE, not every heartbeat.

Measured 2026-11-21, live. The operator provision queue kept each act while its
`object_id` was absent from `public_objects` -- but a provision with
`into: "pack"` goes into an agent's INVENTORY and never creates an object, so its
id was never there and it was re-applied on every heartbeat, forever. Eight acts
queued on 2026-11-14 had been dripping into the world ever since:

    east_eve   stone_axe    1  -> held 1,706  (~1,600 heartbeats of +1)
    east_*     fresh_water  4  -> held ~6,200 (1,550 heartbeats x 4 = 6,200)
    west_eve   fresh_water  3  -> held  6,206 (2,068 heartbeats x 3 = 6,204)

Food spoils, so the edible_roots acts looked harmless; water and tools do not,
so they grew without bound -- and an agent holding 6,200 water never needs the
world again, which is part of why they stopped wanting anything.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    load_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tile_occupancy["east_eve"] = TILE
    return rt


def _queue(rt: FirstPairRuntime, acts: list[dict]) -> Path:
    p = Path(rt._store.root) / "operator_provisions_pending.json"
    p.write_text(json.dumps({"acts": acts}), encoding="utf-8")
    return p


def _pack_act(object_id="op-1", agent_ref="east_adam", kind="fresh_water",
              amount=4):
    return {"object_id": object_id, "agent_ref": agent_ref, "kind": kind,
            "amount": amount, "into": "pack", "tile_id": TILE,
            "reason": "test"}


def test_a_pack_provision_is_applied_once_and_leaves_the_queue(tmp_path):
    rt = _runtime(tmp_path)
    path = _queue(rt, [_pack_act()])
    assert rt._apply_operator_provision_queue() == 1
    held = load_inventory(rt._store)["east_adam"]["fresh_water"]
    assert held == 4, held
    # the act must be GONE: a second pass must not add again
    assert rt._apply_operator_provision_queue() == 0
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 4
    assert json.loads(path.read_text(encoding="utf-8"))["acts"] == []


def test_the_drip_is_stopped_across_many_heartbeats(tmp_path):
    """The exact live symptom: 100 heartbeats of a +4 act must be +4, not +400."""
    rt = _runtime(tmp_path)
    _queue(rt, [_pack_act(amount=4)])
    for hb in range(1, 101):
        rt._apply_operator_provision_queue()
    assert load_inventory(rt._store)["east_adam"]["fresh_water"] == 4


def test_two_acts_sharing_an_object_id_both_land_once(tmp_path):
    """The live queue holds one object_id for BOTH agents. Keying on the
    object_id alone would silently drop the second agent's share."""
    rt = _runtime(tmp_path)
    _queue(rt, [
        _pack_act(object_id="op-shared", agent_ref="east_adam", amount=4),
        _pack_act(object_id="op-shared", agent_ref="east_eve", amount=4),
    ])
    assert rt._apply_operator_provision_queue() == 2
    inv = load_inventory(rt._store)
    assert inv["east_adam"]["fresh_water"] == 4
    assert inv["east_eve"]["fresh_water"] == 4
    assert rt._apply_operator_provision_queue() == 0


def test_a_cache_provision_still_lands_once_as_an_object(tmp_path):
    """The object path keeps its own idempotence: the object exists afterwards."""
    rt = _runtime(tmp_path)
    _queue(rt, [{"object_id": "op-cache-1", "agent_ref": "east_adam",
                 "kind": "edible_roots", "amount": 5, "tile_id": TILE,
                 "reason": "test"}])
    assert rt._apply_operator_provision_queue() == 1
    assert "op-cache-1" in rt._world_state.public_objects
    assert rt._apply_operator_provision_queue() == 0


def test_a_tool_pack_provision_lands_once_too(tmp_path):
    """The live axe: a +1 stone_axe act held 1,706 copies."""
    rt = _runtime(tmp_path)
    _queue(rt, [_pack_act(object_id="op-axe", agent_ref="east_eve",
                          kind="stone_axe", amount=1)])
    for hb in range(1, 51):
        rt._apply_operator_provision_queue()
    assert load_inventory(rt._store)["east_eve"]["stone_axe"] == 1


def test_an_unapplyable_act_is_kept_not_lost(tmp_path):
    """Never silently: if the add raises, the act stays in the queue."""
    rt = _runtime(tmp_path)
    path = _queue(rt, [_pack_act(object_id="op-bad", agent_ref="east_adam",
                                 kind="", amount=4)])
    rt._apply_operator_provision_queue()
    kept = json.loads(path.read_text(encoding="utf-8"))["acts"]
    assert kept and kept[0]["object_id"] == "op-bad"
