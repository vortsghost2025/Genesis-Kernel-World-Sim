"""Test suite for Phase 10NX: Goal Hygiene and Fauna Affordance.

Specification: docs/phase_10nv_goal_hygiene_and_fauna_affordance_spec.md

The primary fixture is derived from the LIVE East lane store
(.runtime/first-pair/goals.json, 34 in_progress goals at hb 8110), so the tests
assert against the population that actually caused the behavioural collapse
rather than a synthetic stand-in.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

FIXTURE = WORLD_SIM / "tests" / "fixtures" / "phase_10nx_east_goals.json"


@pytest.fixture(scope="module")
def east_goals() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)["goals"]


@pytest.fixture(scope="module")
def now_hb() -> int:
    with FIXTURE.open(encoding="utf-8") as f:
        return json.load(f)["heartbeat_number"]


from backend.world.first_pair_runtime import (  # noqa: E402
    DEFAULT_GATHER_RETIRE_THRESHOLDS,
    MAX_ACTIVE_GOALS_EXPOSED,
    STALE_GOAL_AGE_HB,
    _goal_signature,
    _select_diverse_active_goals,
    goal_should_retire,
)


# ---------------------------------------------------------------------------
# _goal_signature
# ---------------------------------------------------------------------------

def test_signature_is_pure_and_stable():
    a = _goal_signature("Continue exploring hill terrain and gather stone")
    b = _goal_signature("Continue exploring hill terrain and gather stone")
    assert a == b, "the signature must be deterministic"
    assert isinstance(a, frozenset), "must return a frozenset (hashable, immutable)"


def test_signature_is_order_insensitive():
    a = _goal_signature("gather stone and explore hills")
    b = _goal_signature("continue exploring hills to gather stone")
    assert a == b, "word order and restatement prefixes must not change meaning"


def test_signature_ignores_restatement_prefixes_and_case():
    a = _goal_signature("Please continue to explore uncharted terrain")
    b = _goal_signature("Explore uncharted terrain")
    assert a == b, "leading imperative verbs and filler restate intent, not meaning"


def test_signature_strips_punctuation_and_filler():
    a = _goal_signature("Continue exploring, and gathering resources!")
    b = _goal_signature("exploring gathering resources")
    assert a == b, "punctuation and connector filler must not split a signature"


def test_signature_distinguishes_genuinely_different_goals():
    a = _goal_signature("Continue exploring hill terrain and gather stone")
    b = _goal_signature("Increase timber supply for shelter")
    assert a != b, "different purposes must keep different signatures"


# ---------------------------------------------------------------------------
# the live population
# ---------------------------------------------------------------------------

def test_live_population_collapses_under_signature(east_goals):
    """The measured 34-goal pile must collapse to a small set of intents."""
    sigs = {_goal_signature(g["description"]) for g in east_goals}
    assert len(east_goals) == 34, "fixture must still hold the live 34 in_progress goals"
    assert len(sigs) <= 15, (
        "34 live in_progress goals collapse to %d distinct signatures; the spec's "
        "measured bound was 15" % len(sigs)
    )
    assert len(sigs) < len(east_goals), (
        "the signature must actually collapse restatements, not reproduce the pile"
    )


def test_live_population_dominates_one_signature(east_goals):
    """Corroborates why the model saw one repeated intent."""
    import collections
    c = collections.Counter(_goal_signature(g["description"]) for g in east_goals)
    top = c.most_common(1)[0]
    assert top[1] >= 4, (
        "the live pile is expected to be dominated by a repeated intent; "
        "largest cluster was %d" % top[1]
    )


# ---------------------------------------------------------------------------
# Rule 4: age-based retirement of restatements
# ---------------------------------------------------------------------------

def test_rule_retires_old_restatements(east_goals, now_hb):
    import collections
    by_sig = collections.defaultdict(list)
    for g in east_goals:
        by_sig[_goal_signature(g["description"])].append(g)

    retired = 0
    kept_newest = 0
    for sig, group in by_sig.items():
        group = sorted(group, key=lambda g: g["created_heartbeat"] or 0, reverse=True)
        for i, g in enumerate(group):
            age = now_hb - (g.get("created_heartbeat") or 0)
            if goal_should_retire(g, group, now_hb, known_tiles=set(),
                                  inventory={}, has_pending_question=False):
                retired += 1
                assert age > STALE_GOAL_AGE_HB, "must never retire a young goal"
            elif i == 0:
                kept_newest += 1

    assert retired >= 20, (
        "Rule 4 must clear the bulk of the measured pile; retired %d of %d"
        % (retired, len(east_goals))
    )
    assert kept_newest == len(by_sig), (
        "the newest goal of every signature must always survive"
    )


def test_rule_keeps_young_goals():
    goals = [
        {"goal_id": "a", "description": "Continue exploring hills", "created_heartbeat": 100},
        {"goal_id": "b", "description": "Continue exploring hills", "created_heartbeat": 50},
    ]
    # now = 400: goal a is young (age 300 < 500), goal b is young too -> neither retires
    assert goal_should_retire(goals[1], goals, 400, set(), {}, False) is False, (
        "age must exceed STALE_GOAL_AGE_HB before a restatement may be retired"
    )
    # now = 700: b is old (650), a is old (600). a is the newest so it survives.
    assert goal_should_retire(goals[0], goals, 700, set(), {}, False) is False, (
        "the newest restatement of a live intent must survive"
    )
    assert goal_should_retire(goals[1], goals, 700, set(), {}, False) is True, (
        "an older restatement of the same intent must retire"
    )


def test_rule_never_retires_tile_scoped_goals():
    goals = [
        {"goal_id": "a", "description": "Survey cont_a_gen_10_10",
         "created_heartbeat": 1},
        {"goal_id": "b", "description": "Survey cont_a_gen_10_10",
         "created_heartbeat": 1},
    ]
    assert goal_should_retire(goals[1], goals, 100000, set(), {}, False) is False, (
        "tile-scoped goals are precise and Rule 1 can still act on them; Rule 4 "
        "must not touch them"
    )


def test_rule_does_not_retire_lonely_goal():
    """A single, unrepeated goal with no duplicate must never be retired."""
    goals = [{"goal_id": "only", "description": "Increase timber supply for shelter",
              "created_heartbeat": 1}]
    assert goal_should_retire(goals[0], goals, 100000, set(), {}, False) is False, (
        "a unique goal is not a restatement and must not be retired by Rule 4"
    )


# ---------------------------------------------------------------------------
# operator standby
# ---------------------------------------------------------------------------

def test_operator_standby_retires_when_unanswered():
    goals = [{"goal_id": "w", "description": "Await operator direction",
              "created_heartbeat": 1}]
    assert goal_should_retire(goals[0], goals, STALE_GOAL_AGE_HB + 10, set(), {},
                              False) is True, (
        "an unanswered operator-standby goal older than STALE_GOAL_AGE_HB must retire"
    )


def test_operator_standby_survives_while_a_question_is_pending():
    goals = [{"goal_id": "w", "description": "Await operator instruction",
              "created_heartbeat": 1}]
    assert goal_should_retire(goals[0], goals, STALE_GOAL_AGE_HB + 10, set(), {},
                              True) is False, (
        "an open question is the legitimate path to the operator and must not be "
        "closed by goal retirement"
    )


def test_operator_standby_survives_while_young():
    goals = [{"goal_id": "w", "description": "Await operator direction",
              "created_heartbeat": 100}]
    assert goal_should_retire(goals[0], goals, 400, set(), {}, False) is False, (
        "a recent standby goal is not yet stale"
    )


# ---------------------------------------------------------------------------
# diverse exposure
# ---------------------------------------------------------------------------

def test_diverse_exposure_beats_recency_slice(east_goals):
    diverse = _select_diverse_active_goals(east_goals, now_hb=10 ** 9)

    assert len(diverse) <= MAX_ACTIVE_GOALS_EXPOSED, (
        "the exposure budget must not grow"
    )
    sigs = {_goal_signature(g["description"]) for g in diverse}
    naive = east_goals[-MAX_ACTIVE_GOALS_EXPOSED:]
    naive_sigs = {_goal_signature(g["description"]) for g in naive}

    assert len(sigs) > len(naive_sigs), (
        "diverse exposure must show more distinct intents than the recency slice "
        "for the same goal list (got %d distinct vs %d)"
        % (len(sigs), len(naive_sigs))
    )
    assert len(diverse) == len(sigs), (
        "no signature may appear twice in the exposed window"
    )


def test_diverse_exposure_preserves_chronological_order(east_goals):
    diverse = _select_diverse_active_goals(east_goals, now_hb=10 ** 9)
    hbs = [g["created_heartbeat"] for g in diverse]
    assert hbs == sorted(hbs), "exposed goals must stay in chronological order"


def test_diverse_exposure_handles_fewer_goals_than_cap():
    goals = [{"goal_id": "a", "description": "Explore hills", "created_heartbeat": 1}]
    out = _select_diverse_active_goals(goals, now_hb=2)
    assert out == goals, "a short list must pass through unchanged"


# ---------------------------------------------------------------------------
# offer_food schema is untouched
# ---------------------------------------------------------------------------

def test_offer_food_schema_is_not_disturbed():
    """Acceptance criterion 8 of the spec."""
    src = (WORLD_SIM / "backend" / "world" / "first_pair_runtime.py").read_text(
        encoding="utf-8"
    )
    assert '"offer_food"' in src or "'offer_food'" in src, (
        "offer_food must remain a first-class action type"
    )
    # the affordance work must not have turned it into something else
    assert "offer_food" in src, "offer_food must still exist in the runtime"


def test_documented_thresholds_are_unchanged():
    """Rule 4 must not quietly redefine the existing rule constants."""
    assert MAX_ACTIVE_GOALS_EXPOSED == 8
    assert STALE_GOAL_AGE_HB == 500
    assert DEFAULT_GATHER_RETIRE_THRESHOLDS["stone"] == 20


# ---------------------------------------------------------------------------
# fauna reach: one constant, and the prompt already states it honestly
# ---------------------------------------------------------------------------

def test_fauna_reach_uses_one_shared_constant():
    """Four duplicated `> 1` literals became one constant (Phase 10OB)."""
    from backend.world import first_pair_runtime as rt_mod
    import inspect

    src = inspect.getsource(rt_mod)
    assert rt_mod.FAUNA_ACTION_REACH == 1, (
        "offer_food/strike require an adjacent-or-same tile"
    )
    assert src.count("> FAUNA_ACTION_REACH") == 4, (
        "all four reach checks must share the constant"
    )
    assert "abs(pxy[1] - exy[1])) > 1:" not in src, (
        "no hardcoded reach check may remain"
    )


def test_existing_fauna_lines_already_state_distance_and_approach():
    """Guard against re-adding a redundant affordance.

    Phase 10NX added a second fauna line that duplicated what
    _format_fauna_lines already states, then a defect in it produced the
    only two offer_food attempts on record -- attempts caused by the
    PRE-EXISTING line, not by the addition. If this ever regresses, the
    existing mechanism is the one to fix.
    """
    from backend.world.first_pair_cognition_model import _format_fauna_lines

    lines = _format_fauna_lines({"nearby": [
        {"kind": "horse", "id": "h-1", "distance": 3, "trust": 0,
         "tamed": False},
    ]})
    assert any("3 tiles away" in l for l in lines), lines
    assert any("move closer to interact" in l for l in lines), (
        "the existing line must already tell the agent how to close the gap"
    )
    assert not any("offer_food may raise trust" in l for l in lines), (
        "a distant animal must not be promised the adjacent-only action"
    )

    adjacent = _format_fauna_lines({"nearby": [
        {"kind": "horse", "id": "h-2", "distance": 1, "trust": 0,
         "tamed": False},
    ]})
    assert any("adjacent" in l for l in adjacent), adjacent
    assert any("offer_food" in l for l in adjacent), (
        "an adjacent untamed animal must be offered the action"
    )
