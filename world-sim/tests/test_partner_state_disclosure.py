"""Phase 10QE: the partner's condition is disclosed as a fact.

The operator asked what the NPCs would want, and the answer came straight
out of their question log: "Are you alive?" (east_eve, HB 13014). The world
disclosed the partner's HOLDINGS (10PT) and their NAME, and nothing about
their body or their position - so an agent could not know that their
companion had collapsed, where, or what they needed.

These tests pin the fact: where the partner is, how their body is, and the
one sentence that makes the handover discoverable (a collapsed body draws on
what the partner carries while they stand on the same tile).
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.first_pair_runtime import (
    FirstPairRuntime,
    _BANNED_DIRECTIVE_PHRASES,
)


def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0", observation={},
        memory=[], goals=[], unanswered_questions=[],
        world_public_objects={}, habitat_allowed_tiles=[],
        habitat_movement_allowed=False, previous_action=None,
        timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_partner_state_is_disclosed_when_the_partner_has_collapsed():
    prompt = m.build_system_prompt(_ctx(partner_state={
        "agent_ref": "east_eve", "tile_id": "cont_a_gen_-45_-2", "downed": True,
        "vitality": 5.7, "thirst": 100.0, "hunger": 5.4, "state": "collapsed",
    }))
    assert "your partner is collapsed at cont_a_gen_-45_-2" in prompt
    assert "vitality 5.7" in prompt
    assert "thirst 100" in prompt
    # and the handover is discoverable from the partner's side
    assert "draw on the food and fresh_water you carry" in prompt


def test_partner_state_is_disclosed_when_the_partner_is_merely_poor():
    prompt = m.build_system_prompt(_ctx(partner_state={
        "agent_ref": "east_eve", "tile_id": "cont_a_gen_-45_-2", "downed": False,
        "vitality": 62.0, "thirst": 70.0, "hunger": 30.0, "state": "hungry",
    }))
    assert "your partner is at cont_a_gen_-45_-2" in prompt
    assert "vitality 62" in prompt


def test_no_partner_state_means_no_partner_line():
    prompt = m.build_system_prompt(_ctx())
    assert "your partner is" not in prompt


def test_the_partner_line_carries_no_directive_phrasing():
    prompt = m.build_system_prompt(_ctx(partner_state={
        "agent_ref": "east_eve", "tile_id": "cont_a_gen_-45_-2", "downed": True,
        "vitality": 5.7, "thirst": 100.0, "hunger": 5.4, "state": "collapsed",
    }))
    for line in prompt.splitlines():
        if "your partner is" in line or "draw on the food" in line:
            low = line.lower()
            for banned in _BANNED_DIRECTIVE_PHRASES:
                assert banned not in low, (banned, line[:140])


def test_the_runtime_reports_the_partner_state(tmp_path):
    rt = FirstPairRuntime(
        heartbeat_limit=1,
        store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = "cont_a_gen_0_0"
    rt._world_state.tile_occupancy["east_eve"] = "cont_a_gen_9_9"
    vitals = rt._vitals_for("east_eve")
    vitals["downed"] = True
    vitals["vitality"] = 5.7
    vitals["thirst"] = 100.0

    state = rt._partner_state_for("east_adam")
    assert state["agent_ref"] == "east_eve"
    assert state["tile_id"] == "cont_a_gen_9_9"
    assert state["downed"] is True
    assert state["vitality"] == 5.7
    assert state["thirst"] == 100.0
