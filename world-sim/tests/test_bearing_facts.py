"""Phase 10RZ — the known-target facts carry a BEARING, and position carries
coordinates.

The deep audit measured east's movement as 43-63% oscillation -- ~8,400
heartbeats, the largest single cost in the world -- and the model's own recorded
reasons show the cause rather than leaving it to guesswork:

  * east_eve, hb 2029: "Continue eastward along row y=-6 toward
    public-shared-center per goal-eve-010. Breaking the hb1990-2029 oscillation"
    -- she KNEW she was oscillating, and the next heartbeats read "Continuing
    westward return route to public-shared-center" along the same row;
  * east_adam's longest move run (85) is a co-location chase: "Join Eve at her
    tile", "Intercept Eve moving north", "Move to Eve's tile".

The world named targets and never said WHICH WAY they were, so every heartbeat
the model re-derived a bearing from two tile ids. Tile ids encode coordinates
(`x` east, `y` north) and nothing rendered them.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_cognition_model import (  # noqa: E402
    _compass_offset,
    _coords_text,
    build_system_prompt,
)

HERE = "cont_a_gen_0_0"


# --- the helper -------------------------------------------------------------

def test_pure_axes():
    assert _compass_offset(HERE, "cont_a_gen_0_3") == "3 tiles north"
    assert _compass_offset(HERE, "cont_a_gen_0_-2") == "2 tiles south"
    assert _compass_offset(HERE, "cont_a_gen_4_0") == "4 tiles east"
    assert _compass_offset(HERE, "cont_a_gen_-5_0") == "5 tiles west"


def test_diagonals():
    assert _compass_offset(HERE, "cont_a_gen_2_2") == "2 tiles north-east"
    assert _compass_offset(HERE, "cont_a_gen_-2_-2") == "2 tiles south-west"
    assert _compass_offset(HERE, "cont_a_gen_1_-1") == "1 tile south-east"


def test_a_dominant_axis_wins_over_a_near_diagonal():
    """A target 40 north and 1 east is north, not north-east."""
    assert _compass_offset(HERE, "cont_a_gen_1_40") == "40 tiles north"
    assert _compass_offset(HERE, "cont_a_gen_40_1") == "40 tiles east"


def test_same_tile_and_unparseable_ids():
    assert _compass_offset(HERE, HERE) == "here"
    assert _compass_offset(HERE, "public-shared-center") == ""
    assert _compass_offset("nonsense", HERE) == ""


def test_the_callers_distance_wins_over_the_ids():
    """The runtime computed the distance; the helper only supplies the bearing.
    Recomputing it would silently override a fact (and did, against fixtures
    whose distance field and ids disagreed)."""
    assert _compass_offset("cont_a_gen_0_0", "cont_a_gen_39_0", 5) == "5 tiles east"
    assert _compass_offset("cont_a_gen_0_0", "cont_a_gen_0_-44", 2) == "2 tiles south"


def test_coords_text():
    assert _coords_text("cont_a_gen_-44_-1") == "x=-44, y=-1"
    assert _coords_text("public-start-adam") == ""


# --- and the prompt uses it -------------------------------------------------

def _ctx(vitals: dict | None = None, **kw) -> AgentContext:
    body = {"downed": False, "vitality": 100.0, "thirst": 10.0, "hunger": 10.0,
            "warmth": 100.0, "wetness": 0.0}
    body.update(vitals or {})
    base = dict(
        agent_id="a", canonical_name="Eve", canonical_ref="east_eve",
        heartbeat_number=1, position="cont_a_gen_-44_-1",
        observation={"self_body": body},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


# The facts are gated: water appears from thirst >= 40, food from hunger >= 60,
# shelter from warmth <= 60. Each test below opens the gate it needs.
THIRSTY = {"thirst": 70.0}
HUNGRY = {"hunger": 80.0}
COLD = {"warmth": 20.0}


def test_the_position_line_names_the_coordinates():
    prompt = build_system_prompt(_ctx())
    assert "Your position: cont_a_gen_-44_-1 (x=-44, y=-1)" in prompt


def test_the_water_fact_carries_a_bearing():
    prompt = build_system_prompt(_ctx(THIRSTY, nearest_known_water={
        "tile_id": "cont_a_gen_-44_4", "distance": 5}))
    assert "cont_a_gen_-44_4, 5 tiles north" in prompt, (
        "the drinkable tile is 5 north of x=-44,y=-1")


def test_the_shelter_fact_carries_a_bearing():
    prompt = build_system_prompt(_ctx(COLD, nearest_known_shelter={
        "tile_id": "cont_a_gen_-47_-1", "distance": 3,
        "object_type": "cabin", "comfort_floor": 62.0}))
    assert "cabin at cont_a_gen_-47_-1, 3 tiles west" in prompt


def test_the_food_fact_carries_a_bearing():
    prompt = build_system_prompt(_ctx(HUNGRY, nearest_known_food={
        "tile_id": "cont_a_gen_-44_-6", "distance": 5, "kinds": ["nuts"]}))
    assert "nuts on cont_a_gen_-44_-6, 5 tiles south" in prompt


def test_a_bearing_less_tile_falls_back_to_the_old_distance():
    """An id the parser cannot read must not produce an empty phrase."""
    prompt = build_system_prompt(_ctx(THIRSTY, nearest_known_water={
        "tile_id": "public-shared-center", "distance": 7}))
    assert "public-shared-center, 7 tiles away" in prompt


def test_every_distance_fact_in_the_prompt_has_a_direction_or_a_distance():
    """No fact may end up saying nothing about where the place is."""
    prompt = build_system_prompt(_ctx(
        {"thirst": 70.0, "hunger": 80.0, "warmth": 20.0},
        nearest_known_water={"tile_id": "cont_a_gen_-44_4", "distance": 5},
        nearest_known_shelter={"tile_id": "cont_a_gen_-47_-1", "distance": 3,
                               "object_type": "cabin", "comfort_floor": 62.0},
        nearest_known_food={"tile_id": "cont_a_gen_-44_-6", "distance": 5,
                            "kinds": ["nuts"]},
    ))
    lines = [l for l in prompt.splitlines() if "you have observed" in l]
    assert len(lines) >= 3, lines
    for line in lines:
        assert re.search(r"\b(north|south|east|west|here|tiles away)\b", line), line
