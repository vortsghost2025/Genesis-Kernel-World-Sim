"""Body-state disclosure: a number, a sentence with lead time, and a word.

The operator asked why the lanes keep dying of thirst: "do they get thirsty
and hungry warnings as it dips, or do they just drop when it gets too low,
no notice?" Measured against the live prompt, the answer was: they get a
number, and the danger sentence for THIRST arrived on the exact heartbeat
the damage began.

Concretely, before this suite:

- thirst was silent below 40, a bare "Your thirst is N/100" from 40, and
  "Your vitality drains while thirst stays at 88 or higher" only FROM 88 --
  the same heartbeat `DEHYDRATION_DRAIN` starts. Zero lead time on harm.
- hunger rendered that identical sentence from 60, i.e. with ~35 heartbeats
  of notice. Same mechanic, two different gates: the thirst note was built
  as `if thirst_val >= 88 else ""` while hunger's was unconditional.
- `vitals_state_label` computes a one-word body state (collapsed, failing,
  dehydrated, starving, freezing, hungry, cold, well) and the runtime puts
  it in `self_body.state` -- and the prompt never rendered it as a sentence
  at all, so the only genuinely alarming word left the world as a JSON key.

This suite pins the fixed ladder: silent below 40, the number from 40, the
danger sentence with the same lead time hunger always had, and the state
word as prose.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import survival
from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_runtime import _BANNED_DIRECTIVE_PHRASES

DANGER = "Your vitality drains while"


def _prompt(thirst=18, hunger=0, vitality=100.0, warmth=88.0, downed=False,
            state=None, fresh_water=0):
    body = {"thirst": thirst, "hunger": hunger, "vitality": vitality,
            "warmth": warmth, "downed": downed}
    if state is not None:
        body["state"] = state
    ctx = AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0",
        observation={"self_body": body,
                     "environment": {"drinkable_water": False}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
        inventory={"fresh_water": fresh_water},
    )
    return build_system_prompt(ctx)


# ---------------------------------------------------------------------------
# thirst gets the lead time hunger always had
# ---------------------------------------------------------------------------

def test_thirst_danger_sentence_matches_hunger_lead_time():
    """The asymmetry, fixed: at thirst 60 and 75 -- both BELOW the 88 harm
    threshold -- the prompt must already carry the danger sentence, exactly
    as hunger has always done."""
    for thirst in (60, 75, 87):
        prompt = _prompt(thirst=thirst)
        assert DANGER in prompt, f"thirst {thirst} has no danger sentence"
        assert f"Your thirst is {thirst}/100." in prompt, thirst
    for hunger in (60, 75, 87):
        assert DANGER in _prompt(hunger=hunger), hunger


def test_thirst_is_silent_below_40_and_numbered_from_40():
    assert "Your thirst is" not in _prompt(thirst=18)
    assert "Your thirst is" not in _prompt(thirst=39)
    assert "Your thirst is 40/100." in _prompt(thirst=40)


def test_hunger_stays_silent_below_60():
    assert "Your hunger is" not in _prompt(hunger=55)
    assert "Your hunger is 60/100." in _prompt(hunger=60)


# ---------------------------------------------------------------------------
# the state word becomes prose instead of a JSON key
# ---------------------------------------------------------------------------

def test_state_word_is_rendered_as_a_sentence():
    for state in ("dehydrated", "starving", "failing", "freezing",
                  "hungry", "cold"):
        prompt = _prompt(state=state)
        assert f"Fact: your body is {state}." in prompt, state
    assert "collapsed" in _prompt(downed=True).lower()


def test_well_is_not_rendered_as_noise():
    prompt = _prompt(state="well", thirst=18, hunger=0)
    assert "Fact: your body is well." not in prompt


def test_state_is_derived_when_the_field_is_absent():
    """`self_body.state` is a cached copy. If an older observation lacks it,
    the word is recomputed from the numbers rather than dropped on the floor."""
    prompt = _prompt(thirst=92.0, vitality=90.0)
    assert "Fact: your body is dehydrated." in prompt
    assert "Fact: your body is starving." in _prompt(hunger=92.0, vitality=90.0)
    assert "Fact: your body is failing." in _prompt(vitality=20.0)


def test_state_label_agrees_with_the_survival_function():
    """The prose and the physics cannot drift: the word shown is the word
    `vitals_state_label` computes for the same numbers."""
    for thirst, hunger, warmth, vitality in ((92, 0, 88, 90), (0, 92, 88, 90),
                                             (0, 0, 88, 20), (18, 0, 88, 100)):
        expected = survival.vitals_state_label(
            {"thirst": thirst, "hunger": hunger, "warmth": warmth,
             "vitality": vitality, "downed": False})
        prompt = _prompt(thirst=thirst, hunger=hunger, warmth=warmth,
                         vitality=vitality)
        if expected == "well":
            # A well body stays silent: the word is only a WARNING channel.
            assert "Fact: your body is well." not in prompt, expected
        else:
            assert f"Fact: your body is {expected}." in prompt, (expected, thirst, hunger)


def test_collapsed_body_still_leads_with_the_collapse_facts():
    """The downed branch is the rescue briefing and must come first; the
    state word must not shadow it or contradict it. Since 10QI it also names
    the crawl, because a body that cannot move at all is a body that cannot
    reach the water five tiles away."""
    prompt = _prompt(downed=True, vitality=0.0, thirst=100.0)
    assert "Your body has collapsed." in prompt
    assert "crawl" in prompt.lower()
    assert "Eat" in prompt or "eat" in prompt
    assert "the drink action also works while you are collapsed" in prompt.lower()


def test_no_directive_phrasing_in_the_new_lines():
    for state in ("dehydrated", "starving", "failing"):
        for line in _prompt(state=state, thirst=60).splitlines():
            if "your body is" in line or DANGER in line:
                low = line.lower()
                for banned in _BANNED_DIRECTIVE_PHRASES:
                    assert banned not in low, (banned, line[:120])
