"""Phase 10SB — the world keeps ONE standing objective on the ladder.

The largest cost in the world that is not a refusal, measured 2026-11-15 over
the full history: goals come ONLY from the model, and once the lanes had
completed 258 of their 277 goals they idled for **23,771 heartbeats between
them** -- 64% of west's entire history, with a single run of 1,138 heartbeats
doing nothing. west_adam's whole open list was "gather wild_berries to reduce
hunger", "maintain survival", "Continue building shelter walls" and "Obtain
water to satisfy thirst".

Disclosure alone does not drive action: the ladder has carried its costs, rungs
and warmth floors since 10RS and neither lane has ever climbed it. So the world
now keeps one standing objective derived from the ladder it already enforces --
the next rung above the home's best -- which advances when the home does and
disappears at the top.

This is a world act on the agents' own goal list, NOT a directive injected into
the prompt: the record states the rung, the type and the payoff.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    GoalRecord,
    load_goals,
)
from backend.world.first_pair_runtime import (  # noqa: E402
    _STRUCTURE_RUNGS,
    FirstPairRuntime,
)

HERE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = HERE
    rt._world_state.tile_occupancy["east_eve"] = HERE
    rt._vitals_for("east_adam")
    rt._vitals_for("east_eve")
    return rt


def _dwell(rt: FirstPairRuntime, tile: str, kind: str, rung: int) -> None:
    obj_id = f"{kind}-{tile}"
    rt._world_state.public_objects[obj_id] = {
        "object_id": obj_id, "object_type": kind, "tile_id": tile,
        "materials": {}, "contents": {}, "structure_rung": rung,
        "construction_stage": "finished", "construction_progress": 4,
    }


def _standing(rt: FirstPairRuntime, agent: str = "east_adam") -> list:
    agent_id = str(rt._agent_view(agent).get("agent_id"))
    return [g for g in rt._goals
            if g.agent_id == agent_id
            and str(g.goal_id).startswith("world-standing-homestead-rung")]


def test_a_rung_one_home_is_given_the_next_rung_as_an_objective(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)                      # best rung 1
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None
    assert made.goal_id == "world-standing-homestead-rung-2"
    assert made.status == "active"
    assert "hut" in made.description and "52" in made.description, made.description


def test_it_is_idempotent_across_heartbeats(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is not None
    assert rt._ensure_standing_homestead_goal("east_adam", 101) is None
    assert len(_standing(rt)) == 1


def test_it_advances_when_the_home_does(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    # the home gains a hut: best rung 2, so the objective becomes cabin (3)
    _dwell(rt, "cont_a_gen_1_0", "hut", 2)
    made = rt._ensure_standing_homestead_goal("east_adam", 200)
    assert made is not None and made.goal_id == "world-standing-homestead-rung-3"
    assert "cabin" in made.description
    old = [g for g in rt._goals
           if g.goal_id == "world-standing-homestead-rung-2"]
    assert old and all(g.status == "completed" for g in old), (
        "the previous objective must close when the home moves on")
    assert len(_standing(rt)) == 2, "one standing, one completed"


def test_it_disappears_at_the_top_of_the_ladder(tmp_path):
    rt = _runtime(tmp_path)
    top = max(rec["rung"] for rec in _STRUCTURE_RUNGS.values())
    _dwell(rt, HERE, "longhouse", top)                  # best rung 6
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is None
    assert _standing(rt) == []


def test_every_rung_it_names_is_a_real_buildable_type(tmp_path):
    for rung in range(1, max(r["rung"] for r in _STRUCTURE_RUNGS.values())):
        rt = _runtime(tmp_path / f"r{rung}")
        name = next(n for n, rec in _STRUCTURE_RUNGS.items() if rec["rung"] == rung)
        _dwell(rt, HERE, name, rung)
        made = rt._ensure_standing_homestead_goal("east_adam", 100)
        want = next((n for n, rec in _STRUCTURE_RUNGS.items()
                     if rec["rung"] == rung + 1), None)
        assert made is not None and want in made.description, (rung, made.description)


def test_it_does_not_touch_a_model_created_goal(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)
    from backend.world.first_pair_persistence import GoalRecord
    mine = GoalRecord(goal_id="g-mine", agent_id=str(rt._agent_view("east_adam")["agent_id"]),
                      description="gather wild_berries to reduce hunger",
                      status="active", created_heartbeat=1)
    rt._goals.append(mine)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    assert mine.status == "active", "a model goal must be untouched"


def test_both_agents_get_their_own_standing_objective(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    rt._ensure_standing_homestead_goal("east_eve", 100)
    assert len(_standing(rt, "east_adam")) == 1
    assert len(_standing(rt, "east_eve")) == 1


def test_no_position_means_no_goal_and_no_crash(tmp_path):
    rt = _runtime(tmp_path)
    rt._world_state.tile_occupancy.pop("east_adam", None)
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is None


def test_the_goal_survives_a_reload(tmp_path):
    """It is a real persisted goal, not a per-heartbeat decoration."""
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "shelter", 1)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    from backend.world.first_pair_persistence import save_goals
    save_goals(rt._store, rt._goals)
    again = load_goals(rt._store)
    assert any(str(g.goal_id).startswith("world-standing-homestead-rung")
               for g in again)


# ---------------------------------------------------------------------------
# Phase 10SV: the world was telling agents TWO DIFFERENT THINGS.
#
# Measured 2026-11-16 in the live store: east_adam and west_adam each held THREE
# active standing goals -- rung-2 AND rung-4 at once, plus a duplicate rung-4,
# and one record whose description the model had overwritten. The old code
# returned the moment it found one current record, so whether the stale ones got
# closed depended on the ORDER they happened to sit in the list.
# ---------------------------------------------------------------------------

def _standing_active(rt, agent="east_adam"):
    agent_id = str(rt._agent_view(agent).get("agent_id"))
    return [g for g in rt._goals
            if g.agent_id == agent_id
            and str(g.goal_id).startswith("world-standing-homestead-rung")
            and str(getattr(g, "status", "")) in ("active", "in_progress")]


def test_a_stale_rung_is_closed_even_when_it_sits_AFTER_the_current_one(tmp_path):
    """The exact order-dependence: current record FIRST, stale one after. The
    old code returned on the current match and never closed the stale one."""
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    _dwell(rt, HERE, "cabin", 3)                    # best rung 3 -> current is rung 4
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is not None
    stale = GoalRecord(goal_id="world-standing-homestead-rung-2",
                       agent_id=agent_id, description="stale",
                       status="active", created_heartbeat=1)
    rt._goals.append(stale)                          # AFTER the current one
    rt._ensure_standing_homestead_goal("east_adam", 101)
    assert stale.status == "completed", "rung-2 must not stay active beside rung-4"
    actives = _standing_active(rt)
    assert len(actives) == 1 and actives[0].goal_id == \
        "world-standing-homestead-rung-4", actives


def test_a_duplicate_of_the_current_rung_is_closed(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    _dwell(rt, HERE, "cabin", 3)
    for _ in range(2):
        rt._goals.append(GoalRecord(
            goal_id="world-standing-homestead-rung-4", agent_id=agent_id,
            description="dup", status="active", created_heartbeat=1))
    kept = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert kept is not None
    actives = _standing_active(rt)
    assert len(actives) == 1, [a.goal_id for a in actives]


def test_the_rung_wording_is_restored_if_it_was_overwritten(tmp_path):
    """The live record read 'Complete house at cont_a_gen_-43_5: hew timber...'
    because the model's update replaced the world's sentence."""
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    _dwell(rt, HERE, "cabin", 3)
    tampered = GoalRecord(
        goal_id="world-standing-homestead-rung-4", agent_id=agent_id,
        description="Complete house at cont_a_gen_-43_5: hew timber",
        status="active", created_heartbeat=1)
    rt._goals.append(tampered)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    assert tampered.description.startswith(
        "Raise the home's best structure rung to 4 (house)"), tampered.description


def test_the_model_may_not_update_a_standing_goal(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    _dwell(rt, HERE, "cabin", 3)
    rt._ensure_standing_homestead_goal("east_adam", 100)
    before = [(g.goal_id, g.status, g.description) for g in rt._goals]
    rt._apply_model_goal_updates([
        {"goal_id": "world-standing-homestead-rung-4", "agent_id": agent_id,
         "description": "Complete house at cont_a_gen_-43_5", "status": "completed"},
        {"goal_id": "world-standing-homestead-rung-2", "agent_id": agent_id,
         "description": "raise to hut", "status": "active"},
    ], 101)
    after = [(g.goal_id, g.status, g.description) for g in rt._goals]
    assert before == after, "the world's standing objective is not the model's to edit"


def test_the_model_can_still_write_its_own_goals(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    rt._apply_model_goal_updates([
        {"goal_id": "g-own", "agent_id": agent_id,
         "description": "gather wild_berries", "status": "active"},
    ], 101)
    assert any(g.goal_id == "g-own"
               and g.status == "active" for g in rt._goals)


def test_at_the_top_of_the_ladder_every_standing_goal_is_closed(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    top = max(rec["rung"] for rec in _STRUCTURE_RUNGS.values())
    _dwell(rt, HERE, "longhouse", top)
    rt._goals.append(GoalRecord(
        goal_id="world-standing-homestead-rung-2", agent_id=agent_id,
        description="old", status="active", created_heartbeat=1))
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is None
    assert _standing_active(rt) == [], "topped out means no rung objective"
