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

import json
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
    _WATER_STORE_BY_RUNG,
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
            and rt._is_standing_goal(g.goal_id)]


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


def test_the_top_of_the_ladder_gets_a_SUPPLY_objective_instead_of_nothing(tmp_path):
    """Phase 10SZ: it used to disappear, and measured 2026-11-17 that meant west
    finished the ladder (274 goals complete, one left) and then stood still for
    261 of 434 heartbeats -- 57 in a row, BOTH agents. A finished ladder must not
    mean a finished agent."""
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None, "topping out must not leave the agent with nothing"
    assert made.goal_id == "world-standing-homestead-supplied"
    assert f"water store holds 0 of {_cap(_top_rung())}" in made.description, \
        made.description
    assert "Carry fresh_water home" in made.description


def test_the_supply_objective_states_the_measured_store(tmp_path):
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    rt._world_state.public_objects[f"{_top_type()}-{HERE}"]["contents"] = {
        "fresh_water": 7}
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert f"holds 7 of {_cap(_top_rung())}" in made.description, made.description


def test_a_full_store_is_stated_as_full(tmp_path):
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    rt._world_state.public_objects[f"{_top_type()}-{HERE}"]["contents"] = {
        "fresh_water": _cap(_top_rung())}
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert "is FULL" in made.description, made.description


def test_a_cisterns_water_is_reported_SEPARATELY_not_as_the_home_store(tmp_path):
    """A cistern keeps its OWN store. Mixing it in would let a home with a full
    cistern read as 'the home store is empty' -- a false statement of exactly
    the kind this world keeps having to unlearn."""
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    rt._world_state.public_objects[f"cistern-{HERE}"] = {
        "object_id": f"cistern-{HERE}", "object_type": "cistern",
        "tile_id": HERE, "contents": {"fresh_water": 20},
        "materials": {}, "structure_rung": 6,
        "construction_stage": "finished", "construction_progress": 4,
    }
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert f"holds 0 of {_cap(_top_rung())}" in made.description, made.description
    assert "the cistern holds 20" in made.description, made.description


def test_held_is_capped_at_capacity_because_a_deposit_past_it_is_refused(tmp_path):
    """The number shown must match what a deposit would actually accept."""
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    rt._world_state.public_objects[f"{_top_type()}-{HERE}"]["contents"] = {
        "fresh_water": 999}
    state = rt._home_water_state_for(HERE)
    assert state["held"] == state["capacity"] == _cap(_top_rung()), state


def _known(rt, agent_ref: str, tiles: dict) -> None:
    path = rt._store.root / f"known_map_{agent_ref}.json"
    path.write_text(json.dumps({
        "schema_version": 1, "agent_id": "x", "known_tiles": tiles,
        "known_landmarks": {}, "named_places": {}, "routes": [],
        "hypotheses": [], "myths": [], "contact_evidence": [],
        "last_observation_tick": 1,
    }), encoding="utf-8")


def _a_land_tile() -> str:
    """A real tile from the true map that has a non-ocean neighbour."""
    from backend.world.first_pair_fog_adapter import load_true_map
    tm = load_true_map(WORLD_SIM / "data")
    index = {}
    for rec in (tm.get("tiles") or []):
        c = rec.get("coordinates") or {}
        if isinstance(c.get("x"), int):
            index[(c["x"], c["y"])] = rec
    for (x, y), rec in index.items():
        if str(rec.get("terrain", "")).lower() == "ocean":
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            n = index.get((nx, ny))
            if n and str(n.get("terrain", "")).lower() != "ocean" \
                    and not n.get("blocks_travel"):
                return str(rec["tile_id"])
    raise AssertionError("no land tile with a land neighbour found")


def _topped_and_full(rt) -> None:
    _top_dwell(rt)
    rt._world_state.public_objects[f"{_top_type()}-{HERE}"]["contents"] = {
        "fresh_water": _cap(_top_rung())}


def test_a_topped_out_AND_supplied_home_is_asked_to_SURVEY(tmp_path):
    """Phase 10TI: measured 2026-11-20, west finished a `stead` (rung 8) AND
    filled its store (28 of 28), so both earlier objectives had run out and the
    idling returned -- the same terminal-goal shape, one rung higher. The answer
    is a purpose that cannot complete."""
    rt = _runtime(tmp_path)
    _topped_and_full(rt)
    _known(rt, "east_adam", {HERE: {"observed_resources": []}})
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None
    assert made.goal_id == "world-standing-homestead-survey", made.goal_id
    assert "never seen it" in made.description, made.description
    assert "Survey the ground beside what you know" in made.description


def test_the_survey_target_is_ground_beside_what_they_know(tmp_path):
    rt = _runtime(tmp_path)
    _topped_and_full(rt)
    home = _a_land_tile()
    _known(rt, "east_adam", {home: {"observed_resources": []}})
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None and made.goal_id == "world-standing-homestead-survey"
    # the named tile must NOT be one they already know
    assert home not in made.description


def test_with_no_known_ground_it_falls_back_to_the_supply_objective(tmp_path):
    """No frontier means no survey: the world must not invent one."""
    rt = _runtime(tmp_path)
    _topped_and_full(rt)
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None
    assert made.goal_id == "world-standing-homestead-supplied", made.goal_id
    assert "is FULL" in made.description


def test_a_store_that_is_not_full_still_asks_for_water(tmp_path):
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    _known(rt, "east_adam", {HERE: {"observed_resources": []}})
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made.goal_id == "world-standing-homestead-supplied"
    assert "Carry fresh_water home" in made.description


def test_the_survey_objective_is_idempotent_and_model_proof(tmp_path):
    rt = _runtime(tmp_path)
    _topped_and_full(rt)
    _known(rt, "east_adam", {HERE: {"observed_resources": []}})
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert rt._ensure_standing_homestead_goal("east_adam", 101) is None
    assert len(_standing(rt)) == 1
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    before = (made.status, made.description)
    rt._apply_model_goal_updates([{
        "goal_id": "world-standing-homestead-survey", "agent_id": agent_id,
        "description": "gather berries", "status": "completed"}], 101)
    assert (made.status, made.description) == before


def test_a_non_dwelling_does_not_add_a_water_store(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "wall", 1)                     # not roofed, not a dwelling
    assert rt._home_water_state_for(HERE) == {}


def test_the_supply_objective_is_idempotent(tmp_path):
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    assert rt._ensure_standing_homestead_goal("east_adam", 100) is not None
    assert rt._ensure_standing_homestead_goal("east_adam", 101) is None
    assert len(_standing(rt)) == 1


def test_the_model_may_not_edit_the_supply_objective(tmp_path):
    rt = _runtime(tmp_path)
    _top_dwell(rt)
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    before = (made.status, made.description)
    rt._apply_model_goal_updates([{
        "goal_id": "world-standing-homestead-supplied", "agent_id": agent_id,
        "description": "gather berries", "status": "completed"}], 101)
    assert (made.status, made.description) == before


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
            and rt._is_standing_goal(g.goal_id)
            and str(getattr(g, "status", "")) in ("active", "in_progress")]


def _top_rung() -> int:
    return max(rec["rung"] for rec in _STRUCTURE_RUNGS.values())


def _top_type() -> str:
    return next(n for n, rec in _STRUCTURE_RUNGS.items()
                if rec["rung"] == _top_rung())


def _cap(rung: int) -> int:
    """The home water store at a rung. Derived, not hardcoded: 10TC raised the
    ladder to rung 8 and every literal '20' in these tests silently became a
    lie about the world."""
    return _WATER_STORE_BY_RUNG[rung]


def _top_dwell(rt) -> None:
    _dwell(rt, HERE, _top_type(), _top_rung())


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


def test_at_the_top_a_stale_rung_objective_is_replaced_by_the_supply_objective(tmp_path):
    rt = _runtime(tmp_path)
    agent_id = str(rt._agent_view("east_adam")["agent_id"])
    top = max(rec["rung"] for rec in _STRUCTURE_RUNGS.values())
    _dwell(rt, HERE, "longhouse", top)
    rt._goals.append(GoalRecord(
        goal_id="world-standing-homestead-rung-2", agent_id=agent_id,
        description="old", status="active", created_heartbeat=1))
    made = rt._ensure_standing_homestead_goal("east_adam", 100)
    assert made is not None and made.goal_id == "world-standing-homestead-supplied"
    actives = _standing_active(rt)
    assert len(actives) == 1, [a.goal_id for a in actives]
    assert actives[0].goal_id == "world-standing-homestead-supplied"
