"""Phase 10SX: the world says WHERE THE MATERIALS ARE, and the drink line stops
teaching an invalid source value.

Measured 2026-11-16, live: west asked "What is the nearest location where I can
find stone?" and "What mechanism do I need to obtain structural timber or an
axe?" EVERY HOUR for SIXTEEN HOURS, unanswered -- while the world already held
the answer in that agent's own known map, and already disclosed the nearest
water, shelter and food with a distance and a bearing. Every target EXCEPT the
materials a build is made of.

And the drink action line read "source carried or resource_kind fresh_water",
which reads like `source: carried fresh_water`. The record: 20 refusals of
"Unknown drink source 'carried fresh_water'", 30 of a missing source and 24 of
an invalid one -- about 74 confused drink attempts from one sentence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world import first_pair_cognition_model as m  # noqa: E402
from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_persistence import FirstPairPersistenceStore  # noqa: E402
from backend.world.first_pair_runtime import (  # noqa: E402
    FirstPairRuntime,
    _BANNED_DIRECTIVE_PHRASES,
)

HERE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(heartbeat_limit=1,
                          store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = HERE
    rt._vitals_for("east_adam")
    return rt


def _known_map(rt: FirstPairRuntime, agent_ref: str, tiles: dict) -> None:
    # `load_known_map` validates the full envelope, so the fixture must be a
    # real known map rather than a bare `known_tiles` dict.
    path = rt._store.root / f"known_map_{agent_ref}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "agent_id": "x",
        "known_tiles": tiles,
        "known_landmarks": {},
        "named_places": {},
        "routes": [],
        "hypotheses": [],
        "myths": [],
        "contact_evidence": [],
        "last_observation_tick": 1,
    }), encoding="utf-8")


def _tile(resources):
    return {"observed_resources": list(resources)}


# --- the runtime fact -------------------------------------------------------

def test_it_reports_the_nearest_observed_tile_per_material(tmp_path):
    rt = _runtime(tmp_path)
    _known_map(rt, "east_adam", {
        "cont_a_gen_-3_0": _tile(["stone"]),        # 3 tiles
        "cont_a_gen_-1_0": _tile(["stone"]),        # 1 tile  <- nearest
        "cont_a_gen_0_2": _tile(["wood"]),          # 2 tiles north
        "cont_a_gen_-5_0": _tile(["flint"]),        # 5 tiles
    })
    got = rt._nearest_known_materials_for("east_adam")
    assert got["stone"]["tile_id"] == "cont_a_gen_-1_0"
    assert got["stone"]["distance"] == 1
    assert got["wood"]["tile_id"] == "cont_a_gen_0_2"
    assert got["wood"]["distance"] == 2
    assert got["flint"]["distance"] == 5
    assert "clay" not in got, "a material never observed must not be invented"


def test_a_material_on_this_tile_is_distance_zero(tmp_path):
    rt = _runtime(tmp_path)
    _known_map(rt, "east_adam", {HERE: _tile(["stone"])})
    assert rt._nearest_known_materials_for("east_adam")["stone"]["distance"] == 0


def test_it_ignores_tiles_on_the_other_continent(tmp_path):
    """The continents share a coordinate space, so a tile on the other one is
    not 'one tile away'."""
    rt = _runtime(tmp_path)
    _known_map(rt, "east_adam", {
        "cont_b_gen_1_0": _tile(["stone"]),         # near in numbers, wrong world
        "cont_a_gen_-4_0": _tile(["stone"]),        # 4 tiles, same continent
    })
    got = rt._nearest_known_materials_for("east_adam")
    assert got["stone"]["tile_id"] == "cont_a_gen_-4_0", got


def test_no_known_map_means_no_fact_and_no_crash(tmp_path):
    rt = _runtime(tmp_path)
    assert rt._nearest_known_materials_for("east_adam") == {}


# --- the prompt fact --------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="genesis-agent-x", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=HERE, observation={"tile_id": HERE},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_the_prompt_states_the_nearest_materials_with_a_bearing():
    prompt = m.build_system_prompt(_ctx(nearest_known_materials={
        "stone": {"tile_id": "cont_a_gen_-3_0", "distance": 3},
        "wood": {"tile_id": "cont_a_gen_0_2", "distance": 2},
    }))
    assert "the materials a build needs" in prompt
    assert "stone: cont_a_gen_-3_0" in prompt
    assert "3 tiles west" in prompt, prompt
    assert "wood: cont_a_gen_0_2" in prompt


def test_a_material_on_the_current_tile_reads_as_your_current_tile():
    prompt = m.build_system_prompt(_ctx(nearest_known_materials={
        "stone": {"tile_id": HERE, "distance": 0}}))
    assert "stone: your current tile" in prompt, prompt


def test_no_materials_means_no_materials_line():
    prompt = m.build_system_prompt(_ctx())
    assert "the materials a build needs" not in prompt


def test_the_materials_fact_carries_no_directive():
    prompt = m.build_system_prompt(_ctx(nearest_known_materials={
        "stone": {"tile_id": "cont_a_gen_-3_0", "distance": 3}}))
    for line in prompt.splitlines():
        if "the materials a build needs" in line:
            low = line.lower()
            for banned in _BANNED_DIRECTIVE_PHRASES:
                assert banned not in low, (banned, line[:140])


# --- the drink line ---------------------------------------------------------

def _drink_line(prompt: str) -> str:
    return next(l for l in prompt.splitlines() if l.startswith("- drink:"))


def test_the_drink_line_names_its_three_forms_and_the_exact_values():
    line = _drink_line(m.build_system_prompt(_ctx()))
    assert "exactly three forms work" in line, line
    assert '"tile"' in line and '"carried"' in line, line
    assert "clay_pot" in line, line


def test_the_drink_line_warns_that_carried_fresh_water_is_not_a_source():
    """The measured mistake: 20 refusals of "Unknown drink source 'carried
    fresh_water'" -- the model combining the source word with the resource."""
    line = _drink_line(m.build_system_prompt(_ctx()))
    assert '"carried" is a source VALUE' in line, line
    assert '"carried fresh_water" is none of those three' in line, line


def test_the_drink_line_no_longer_contains_the_ambiguous_phrasing():
    line = _drink_line(m.build_system_prompt(_ctx()))
    assert "source carried or resource_kind fresh_water consumes" not in line


def test_the_collapsed_menu_is_consistent_with_the_full_one():
    from backend.world.first_pair_cognition_interface import (
        COLLAPSED_PERMITTED_ACTIONS,
    )
    import backend.world.first_pair_cognition_model as mm
    assert set(mm._COLLAPSED_ACTION_LINES) == set(COLLAPSED_PERMITTED_ACTIONS)
    collapsed = mm._COLLAPSED_ACTION_LINES["drink"]
    assert '"carried"' in collapsed and '"tile"' in collapsed
    assert '"carried fresh_water" is not a source value' in collapsed
