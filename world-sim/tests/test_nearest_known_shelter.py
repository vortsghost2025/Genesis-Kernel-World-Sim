"""Phase 10RL — tell an agent where its own roof is, and how warm.

10QM gave water a distance ("the nearest drinkable tile you have observed is X,
N tiles away") and it produced the first self-directed water trip in 13,000+
heartbeats. Shelter had no equivalent. Measured 2026-11-14 the east pair spent a
winter night soaked to wetness 100, warmth 12, collapsed -- with their own
shelter at foundation elsewhere in the valley and no way to find it -- while the
west pair sat at warmth 100 inside theirs.

Two deliberate differences from the water fact:

  * only a FINISHED roofed structure counts: an unfinished frame shelters
    nobody, and pointing an agent at one would be a lie;
  * it states the comfort floor, because "three tiles away" only means
    something if the place is warm when you arrive.

No provider, no network: tempdir stores only.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext  # noqa: E402
from backend.world.first_pair_cognition_model import build_system_prompt  # noqa: E402
from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
)
from backend.world.first_pair_runtime import FirstPairRuntime  # noqa: E402

HERE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    store = FirstPairPersistenceStore(tmp_path / "store")
    rt = FirstPairRuntime(heartbeat_limit=1, store=store, pair_id="east")
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = HERE
    rt._vitals_for("east_adam")
    return rt


def _dwell(rt: FirstPairRuntime, tile: str, kind: str, rung: int,
           stage: str = "finished") -> None:
    """A finished dwelling, or a real staged build (which shelters nobody)."""
    obj_id = f"{kind}-{tile}"
    record = {
        "object_id": obj_id, "object_type": kind, "tile_id": tile,
        "materials": {}, "contents": {}, "structure_rung": rung,
    }
    if stage == "finished":
        record["construction_stage"] = "finished"
        record["construction_progress"] = 4
    else:
        # the shape the live world actually uses for a staged build
        record["construction_project"] = True
        record["construction_stage"] = stage
        record["construction_progress"] = 0
    rt._world_state.public_objects[obj_id] = record


def _know(rt: FirstPairRuntime, tiles: list[str], agent: str = "east_adam") -> None:
    """A valid known map recording these tiles as observed.

    Shape copied from tests/test_nearest_known_water.py: `load_known_map`
    VALIDATES the map, so a hand-written map missing a required field is worse
    than no fixture at all -- and the runtime's try/except turns the validation
    error into "knows nothing", which looks exactly like a passing test.
    """
    from backend.world.first_pair_fog_adapter import persist_known_map

    known = {"schema_version": "7B.1", "agent_id": agent,
             "contact_evidence": [], "hypotheses": [], "myths": [],
             "known_landmarks": {}, "named_places": {}, "routes": [],
             "last_observation_tick": 1,
             "known_tiles": {
                 t: {"tile_id": t, "observed_resources": [],
                     "first_observed_tick": 1, "last_observed_tick": 1,
                     "visit_count": 0, "confidence": 1.0,
                     "observed_terrain": "grassland",
                     "observed_biome": "temperate_valley",
                     "observed_hazards": [], "agent_given_name": None,
                     "notes": []}
                 for t in tiles}}
    persist_known_map(rt._store.root, agent, known)


# --- the fact itself ---------------------------------------------------------

def test_it_reports_the_nearest_finished_shelter_with_distance_and_floor(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "lean-to", 1)
    _dwell(rt, "cont_a_gen_2_0", "cabin", 3)
    _dwell(rt, "cont_a_gen_5_0", "house", 4)
    _know(rt, [HERE, "cont_a_gen_2_0", "cont_a_gen_5_0"])
    got = rt._nearest_known_shelter_for("east_adam")
    # standing ON the lean-to: distance 0 is the nearest of all
    assert got["tile_id"] == HERE and got["distance"] == 0
    assert got["object_type"] == "lean-to"
    assert got["comfort_floor"] == 45.0


def test_it_measures_distance_from_a_body_away_from_home(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, "cont_a_gen_4_0", "cabin", 3)          # 4 tiles east of the body
    _dwell(rt, "cont_a_gen_1_0", "house", 4)          # 1 tile east
    _know(rt, ["cont_a_gen_4_0", "cont_a_gen_1_0"])
    got = rt._nearest_known_shelter_for("east_adam")
    assert got["tile_id"] == "cont_a_gen_1_0", got
    assert got["distance"] == 1
    assert got["comfort_floor"] == 68.0, "a house must report its own floor"


def test_an_unfinished_frame_is_not_a_shelter(tmp_path):
    """Pointing an agent at a foundation would be a lie."""
    rt = _runtime(tmp_path)
    _dwell(rt, "cont_a_gen_1_0", "shelter", 1, stage="foundation")
    _know(rt, ["cont_a_gen_1_0"])
    assert rt._nearest_known_shelter_for("east_adam") == {}


def test_a_bare_stage_marker_alone_is_not_a_shelter_either(tmp_path):
    """Defence in depth: the fact must not depend on `_record_shelters` alone."""
    rt = _runtime(tmp_path)
    rt._world_state.public_objects["odd-1"] = {
        "object_id": "odd-1", "object_type": "cabin", "tile_id": "cont_a_gen_1_0",
        "materials": {}, "contents": {}, "structure_rung": 3,
        "construction_stage": "walls",          # no construction_project flag
    }
    _know(rt, ["cont_a_gen_1_0"])
    assert rt._nearest_known_shelter_for("east_adam") == {}


def test_a_shelter_the_agent_has_never_observed_is_not_offered(tmp_path):
    """The fact comes from the agent's own memory, like water's."""
    rt = _runtime(tmp_path)
    _dwell(rt, "cont_a_gen_1_0", "house", 4)          # never observed
    assert rt._nearest_known_shelter_for("east_adam") == {}
    _know(rt, ["cont_a_gen_1_0"])
    assert rt._nearest_known_shelter_for("east_adam")["tile_id"] == "cont_a_gen_1_0"


def test_the_other_continent_is_not_three_tiles_away(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, "cont_b_gen_1_0", "house", 4)
    _know(rt, ["cont_b_gen_1_0"])
    assert rt._nearest_known_shelter_for("east_adam") == {}


def test_with_no_known_map_it_says_nothing(tmp_path):
    rt = _runtime(tmp_path)
    _dwell(rt, HERE, "cabin", 3)
    assert rt._nearest_known_shelter_for("east_adam") == {}


# --- and it reaches the prompt, including the collapsed one ------------------

def _ctx(downed: bool, shelter: dict) -> AgentContext:
    return AgentContext(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=HERE,
        observation={"self_body": {"downed": downed, "vitality": 3.0,
                                   "thirst": 10.0, "hunger": 10.0,
                                   "warmth": 12.0, "wetness": 100.0}},
        memory=[], goals=[], unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
        nearest_known_shelter=shelter,
    )


def test_the_standing_prompt_names_the_shelter_with_its_distance():
    prompt = build_system_prompt(_ctx(False, {
        "tile_id": "cont_a_gen_3_0", "distance": 3,
        "object_type": "cabin", "comfort_floor": 62.0}))
    assert "the nearest finished shelter you have observed is a cabin at " \
           "cont_a_gen_3_0, 3 tiles away" in prompt
    assert "62" in prompt, "the comfort floor must be stated"


def test_the_collapsed_prompt_names_it_too():
    """The branch that replaced the body section is where it matters most."""
    prompt = build_system_prompt(_ctx(True, {
        "tile_id": "cont_a_gen_3_0", "distance": 3,
        "object_type": "cabin", "comfort_floor": 62.0}))
    assert "the nearest finished shelter you have observed is" in prompt
    assert "cont_a_gen_3_0" in prompt
    assert "blocking rain entirely" in prompt


def test_it_invents_nothing_when_there_is_no_known_shelter():
    prompt = build_system_prompt(_ctx(True, {}))
    assert "nearest finished shelter" not in prompt
