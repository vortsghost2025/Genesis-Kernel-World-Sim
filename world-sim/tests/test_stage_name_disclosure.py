"""Phase 10RX — a stage name must not read as an object to build.

Measured 2026-11-15, live: west_adam asked

    "Which wall should I build on foundation tile cont_b_gen_26_55 to satisfy
     the stage plan for shelter my_shelter_001_new?"

SEVEN heartbeats running, and built THIRTEEN `wall` objects -- while his own
project sat at stage `roofed` (3/5) with an EMPTY remaining floor, one stage
from finished. The construction stages are named after parts of a building and
the third is literally `walls`, so the name read as something to construct; and
because his remaining floor was empty the disclosure never said the rest was
free.

The line now states all three things the question needed:

  * the stage names are PHASES, listed from `_CONSTRUCTION_STAGES`, and a `wall`
    or `roof` object is a separate component that does NOT advance the project;
  * an empty remaining floor reads "no materials are needed for the rest of it";
  * advancing is still named as calling build again with the same object_id.

Stage names are rendered from the runtime's own tuple so the disclosure cannot
drift from the phases the world actually runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_cognition_model import build_system_prompt  # noqa: E402
from backend.world.first_pair_runtime import _CONSTRUCTION_STAGES  # noqa: E402


def _ctx(construction_here: dict) -> AgentContext:
    return AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_b_gen_26_55",
        observation={"self_body": {"downed": False, "vitality": 100.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 100.0, "wetness": 0.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
        construction_here=construction_here,
    )


LIVE = {"object_id": "foundation_my_shelter_001_new", "object_type": "lean-to",
        "stage": "roofed", "progress": 3, "stages_total": 5, "rung": 1,
        "remaining_floor": {"timber": 0}}


def test_a_stage_name_is_stated_to_be_a_phase_not_an_object():
    prompt = build_system_prompt(_ctx(LIVE))
    assert "Stage names are PHASES, not objects to build" in prompt
    assert "does " in prompt and "NOT advance this project" in prompt.replace(
        "\n", " ").replace("  ", " ")


def test_the_stage_list_is_the_runtime_s_own():
    prompt = build_system_prompt(_ctx(LIVE))
    for stage in _CONSTRUCTION_STAGES:
        assert stage in prompt, stage
    assert ", ".join(_CONSTRUCTION_STAGES) in prompt


def test_it_says_the_wall_stage_is_the_third_phase_and_names_the_live_stage():
    prompt = build_system_prompt(_ctx(LIVE))
    assert "at stage roofed (3/5)" in prompt


def test_an_empty_remaining_floor_says_the_rest_is_free():
    """The specific thing that made 13 walls look reasonable."""
    prompt = build_system_prompt(_ctx(LIVE))
    assert "no materials are needed for the rest of it" in prompt
    assert "still needed" not in prompt


def test_a_non_empty_remaining_floor_still_lists_what_is_needed():
    prompt = build_system_prompt(_ctx({**LIVE, "stage": "foundation",
                                       "progress": 0,
                                       "remaining_floor": {"timber": 2}}))
    assert "still needed: timber 2" in prompt
    assert "no materials are needed" not in prompt


def test_it_still_names_the_action_that_advances_the_stage():
    prompt = build_system_prompt(_ctx(LIVE))
    assert "Calling build again with the same object_id" in prompt


def test_no_project_means_no_construction_line():
    prompt = build_system_prompt(_ctx({}))
    assert "under construction at stage" not in prompt
