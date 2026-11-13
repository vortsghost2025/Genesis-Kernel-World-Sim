"""Phase 10QI - a collapsed body keeps its legs.

Operator, 2026-11-13: "we should help them while they are learning instead of
leaving them on the ground? would you want us to sit here for hours if u were
dying of thirst on the ground?"

Measured, and he is right: the collapsed gate permitted only message,
ask_human, no_action, eat and drink, so a body on the ground could NOT MOVE.
Both agents of a pair are usually down together, the operator has no mechanic
to deliver anything, and self-recovery is DOWNED_PASSIVE_REGEN 0.15/hb -
roughly eighty heartbeats, or four hours, lying still before the body can
stand. In a world with no death, that is not lethality, it is a trap with no
exit.

So collapse takes your hands, not your legs. A downed body may CRAWL to an
adjacent tile: one edge per heartbeat, exactly as slow as walking, but with
nothing else available - no gathering, no building, no work. That is enough
of a penalty (a crawling agent is not surviving, it is only relocating) and it
makes every rescue mechanic in the world reachable: the river, the partner on
the next tile, the cistern at home.

Movement in this world is capability-gated (grant + policy topology), so the
setup here mirrors the live lanes: a granted `movement` capability and the
canonical habitat topology.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    create_default_runtime_policy,
    grant_capability,
)
from backend.world.first_pair_runtime import FirstPairRuntime

START = "public-shared-center"
NEXT = "public-start-eve"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()
    grant = grant_capability(store, "movement", "first-pair-shared-habitat",
                             "Operator-approved movement")
    rt._capability_grant = grant
    rt._runtime_policy = create_default_runtime_policy()
    rt._world_state.tile_occupancy["east_adam"] = START
    rt._world_state.tile_occupancy["east_eve"] = NEXT
    return rt


def _collapse(rt, agent_ref="east_adam", thirst=100.0, hunger=100.0, vitality=0.0):
    v = rt._vitals_for(agent_ref)
    v["downed"] = True
    v["thirst"] = thirst
    v["hunger"] = hunger
    v["vitality"] = vitality
    return v


def _move(rt, target):
    return rt._execute_action("east_adam", {
        "action_type": "move", "target_tile": target, "reason": "crawl",
    }, 101)


# ---------------------------------------------------------------------------

def test_a_collapsed_body_can_crawl_to_an_adjacent_tile(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    out = _move(rt, NEXT)
    assert out["status"] == "success", out
    assert rt._world_state.tile_occupancy["east_adam"] == NEXT


def test_the_crawl_still_respects_adjacency(tmp_path):
    """Collapse does not grant a teleport: a tile that is not reachable in one
    edge stays out of reach, and the body does not move."""
    rt = _runtime(tmp_path)
    _collapse(rt)
    far = "cont_a_gen_40_40"
    out = _move(rt, far)
    assert out["status"] != "success", out
    assert rt._world_state.tile_occupancy["east_adam"] == START


def test_a_collapsed_body_still_cannot_gather_or_build(tmp_path):
    """The crawl is the ONLY thing collapse returns. The hands stay down."""
    rt = _runtime(tmp_path)
    _collapse(rt)
    for action in (
        {"action_type": "gather", "resource_kind": "wood", "reason": "x"},
        {"action_type": "build", "object_id": "s", "object_type": "shelter",
         "tile_id": START, "description": "a shelter",
         "materials": {"timber": 2}},
        {"action_type": "hew_timber", "reason": "x"},
    ):
        out = rt._execute_action("east_adam", action, 101)
        assert out["status"] == "rejected", action
        assert "collapsed" in out["reason"].lower()


def test_crawling_does_not_stand_you_up(tmp_path):
    rt = _runtime(tmp_path)
    _collapse(rt)
    _move(rt, NEXT)
    assert rt._vitals_for("east_adam")["downed"] is True


def test_a_crawling_body_that_reaches_water_can_drink(tmp_path):
    """The whole point: a body that can crawl is a body that can be saved by
    the river it can now reach."""
    rt = _runtime(tmp_path)
    _collapse(rt, thirst=100.0)
    out = _move(rt, NEXT)
    assert out["status"] == "success", out
    rt._drinkable_tile_ids = {NEXT}
    drank = rt._execute_action("east_adam", {
        "action_type": "drink", "source": "tile", "reason": "thirst",
    }, 102)
    assert drank["status"] == "success", drank
    assert rt._vitals_for("east_adam")["thirst"] == round(
        100.0 - survival.DRINK_SATISFACTION["tile"], 2)


# ---------------------------------------------------------------------------
# the disclosure must change with the mechanic
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=START,
        observation={"self_body": {"downed": True, "thirst": 100.0,
                                    "hunger": 100.0, "vitality": 0.0,
                                    "warmth": 90.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_the_collapsed_briefing_says_can_crawl():
    prompt = build_system_prompt(_ctx())
    assert "crawl" in prompt.lower()
    # and it no longer claims the agent is rooted
    assert "You cannot move, gather, or build" not in prompt
