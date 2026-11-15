"""Phase 10RS — the ladder disclosure must state the numbers that decide it.

Measured 2026-11-15 against the live world: east has 68 roofed structures and
west 158, and NOT ONE above rung 1. The ladder's disclosure was the reason it
could not bite:

  * its closing sentence described the PRE-10QU mechanic -- "a connected home's
    comfort comes from its tier weight, which is the roofed footprint plus the
    bonus for the best rung". 10QU moved comfort onto the best RUNG alone, so
    the prompt had become a lie about the world it describes;
  * the number that actually decides whether to climb -- the comfort floor each
    rung holds -- appeared nowhere;
  * `shelter`, the type they build most, is a LEGACY ALIAS for rung 1, so it is
    the bottom of the ladder, not a way up it, and nothing said so while the
    action menu lists `shelter` first.

These tests require the disclosure to state the truth AND to be derived from the
runtime's own tables, so it cannot drift again.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_runtime import (  # noqa: E402
    _LEGACY_TYPE_RUNG,
    _STRUCTURE_RUNGS,
    _home_network_tier,
    _home_thermal_index,
)

TEXT = m._structure_ladder_description()


def _disclosed_floors(text: str) -> dict[str, float]:
    """{rung name: warmth figure} as the disclosure prints them."""
    out = {}
    for name in _STRUCTURE_RUNGS:
        match = re.search(
            rf"`{name}` \(rung \d+, [^;]*; warmth holds near ([\d.]+) inside", text)
        if match:
            out[name] = float(match.group(1))
    return out


# --- the numbers are the physics --------------------------------------------

def test_every_rung_discloses_the_floor_the_physics_uses():
    """Disclosure equals physics, rung by rung, from one source of truth."""
    disclosed = _disclosed_floors(TEXT)
    assert set(disclosed) == set(_STRUCTURE_RUNGS), disclosed
    for name, rung in _STRUCTURE_RUNGS.items():
        expected = _home_network_tier(_home_thermal_index(rung["rung"]))[0]
        assert disclosed[name] == expected, (name, disclosed[name], expected)


def test_the_floors_rise_with_the_rung_so_climbing_is_worth_something():
    floors = [_disclosed_floors(TEXT)[name] for name in _STRUCTURE_RUNGS]
    assert floors == sorted(floors) and len(set(floors)) == len(floors), floors
    assert floors[0] == 45.0 and floors[-1] == 80.0, floors


# --- and the sentence that had become a lie ---------------------------------

def test_it_no_longer_claims_the_footprint_drives_comfort():
    """10QU moved comfort onto the best rung; the old sentence said otherwise."""
    assert "comfort comes from its tier weight" not in TEXT
    assert "plus the bonus for the best rung" not in TEXT


def test_it_states_that_warmth_comes_from_the_best_rung_not_the_size():
    assert "warmth comes from the BEST rung" in TEXT
    assert "not from its size" in TEXT
    assert "nothing about how many roofed tiles a home covers changes that" in TEXT


def test_it_still_says_the_footprint_governs_capacity():
    """Size was not nerfed, only moved: it buys storage, not warmth."""
    assert "governs CAPACITY" in TEXT
    assert "cellar food" in TEXT and "water store" in TEXT


# --- and the specific thing they keep building ------------------------------

def test_it_says_the_generic_shelter_is_rung_1():
    """`shelter` is a legacy alias for rung 1 -- the bottom, not a way up."""
    rung = _LEGACY_TYPE_RUNG.get("shelter")
    assert rung == 1, rung
    assert f"The generic `shelter` type counts as rung {rung}" in TEXT
    assert "where the ladder starts, not a way up it" in TEXT


def test_every_rung_is_still_disclosed_with_its_cost_and_effects():
    """The 10QC property is preserved: the TABLE is rendered, not a list."""
    for name, record in _STRUCTURE_RUNGS.items():
        assert f"`{name}` (rung {record['rung']}," in TEXT, name
        for kind in record["floor"]:
            assert f"{kind} x{record['floor'][kind]}" in TEXT, (name, kind)
        assert record["effects"] in TEXT, name


def _ctx() -> AgentContext:
    return AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position="cont_a_gen_0_0",
        observation={"self_body": {"downed": False, "vitality": 100.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 100.0, "wetness": 0.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )


def test_it_reaches_the_prompt():
    """The description is resolved at call time inside build_system_prompt (to
    dodge a circular import), so the test asks the PROMPT, not the module."""
    prompt = m.build_system_prompt(_ctx())
    assert "Structure ladder, each rung a buildable roofed type" in prompt
    assert "warmth holds near 62 inside" in prompt
    assert "warmth comes from the BEST rung" in prompt
    assert "The generic `shelter` type counts as rung 1" in prompt
