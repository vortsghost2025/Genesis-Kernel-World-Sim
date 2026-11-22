"""Phase 10TY: a lean-to can actually be FINISHED now.

The real bug, measured on 2026-11-22: 57 build failures in 200 heartbeats.
A lean-to's stage plan is {foundation: {timber: 1}, frame: {}, walls: {},
roofed: {}, finished: {}}. After the foundation every stage is FREE, so the agent
correctly declares `timber: 0` or `{}` -- and the schema rejected BOTH
(`bad_material_amount_timber:0` and `empty_materials`), so a lean-to could never
be finished. The model retried the same correct declaration every heartbeat.

The advance path itself is fine (its loop iterates over nothing), so the only
blocker was the schema. This drives the declaration through BOTH layers, because
that is the layer that was broken.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_model import validate_action_exact  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    add_to_inventory,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

TILE = "cont_a_gen_0_0"
AGENT = "east_adam"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy[AGENT] = TILE
    rt._vitals_for(AGENT)
    add_to_inventory(rt._store, AGENT, "timber", 1)
    return rt


def _build_action(materials, object_id="lean-1", object_type="lean-to"):
    return {"action_type": "build", "object_id": object_id,
            "object_type": object_type, "tile_id": TILE,
            "description": "a lean-to", "materials": materials}


def test_a_lean_to_advances_through_all_its_free_stages(tmp_path):
    """The exact live failure: declaring nothing for a free stage must work."""
    rt = _runtime(tmp_path)
    first = rt._execute_action(AGENT, _build_action({"timber": 1}), 100)
    assert first["status"] == "success", first
    assert rt._world_state.public_objects["lean-1"]["construction_stage"] == "foundation"

    # every later stage is FREE -- these declarations used to be schema errors
    for step, materials in enumerate(({}, {"timber": 0}, {}, {"timber": 0})):
        action = _build_action(materials)
        assert validate_action_exact(action, "genesis-agent-test") == [], (
            f"step {step}: schema rejected a free declaration")
        res = rt._execute_action(AGENT, action, 101 + step)
        assert res["status"] == "success", (step, res)

    rec = rt._world_state.public_objects["lean-1"]
    assert rec["construction_stage"] == "finished", rec


def test_a_zero_declaration_for_a_NEW_build_is_still_refused_with_a_route(tmp_path):
    """The contract is not weakened: a NEW lean-to needs its rung floor, and a
    declaration of 0 for it must be refused with the number, not accepted."""
    rt = _runtime(tmp_path)
    res = rt._execute_action(AGENT, _build_action({"timber": 0}, object_id="lean-new"), 100)
    assert res["status"] == "rejected", res
    assert "timber" in res["reason"], res["reason"]
    assert "needs at least 1 structural timber" in res["reason"], res["reason"]


def test_a_negative_or_non_integer_amount_is_still_rejected():
    for bad in (-1, -2, True, "two", 2.5):
        errors = validate_action_exact(
            _build_action({"timber": bad}), "genesis-agent-test")
        assert errors, f"{bad} should still be an error"
        hit = [e for e in errors if "bad_material_amount_timber" in e]
        assert hit, errors
        assert str(bad) in hit[0], (bad, hit)
