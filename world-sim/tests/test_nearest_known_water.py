"""Phase 10QM - the water they know about, with a distance.

Measured overnight (2026-11-14, 213 heartbeats East + 184 West):

  East: use_object 222x (mostly trying to EXTRACT water from the operator
        caches they had already drunk dry - 62 refusals about it), drink 45,
        move 36+4.
  West: ask_human 192x in 184 heartbeats, move 37, drink 4.

  Neither lane drank from a river all night, with rivers in their own
  resource rollups and four to five tiles away.

The rollup names the tiles and never says how far, and nothing connects "your
thirst is 100" to "you know where water is". So the body section now states
the fact where it is needed: the nearest drinkable tile the agent has
PERSONALLY OBSERVED, and its distance in tiles. It is the agent's own memory
plus arithmetic - no true-map knowledge, and no directive.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_cognition_interface import AgentContext
from backend.world.first_pair_cognition_model import build_system_prompt
from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.first_pair_runtime import FirstPairRuntime

TILE = "cont_a_gen_0_0"


def _runtime(tmp_path: Path) -> FirstPairRuntime:
    rt = FirstPairRuntime(
        heartbeat_limit=1, store=FirstPairPersistenceStore(tmp_path / "store"))
    rt._load_or_initialize()
    rt._world_state.tile_occupancy["east_adam"] = TILE
    rt._world_state.tick = 100
    return rt


def _know_water(rt, tiles, agent="east_adam"):
    """A known map recording water at the given tiles - the agent's own memory.

    Built with every field the loader validates, since a hand-written map that
    fails validation is worse than no fixture at all.
    """
    from backend.world.first_pair_fog_adapter import persist_known_map
    known = {"schema_version": "7B.1", "agent_id": agent,
             "contact_evidence": [], "hypotheses": [], "myths": [],
             "known_landmarks": {}, "named_places": {}, "routes": [],
             "last_observation_tick": 1,
             "known_tiles": {
                 t: {"tile_id": t, "observed_resources": ["fresh_water"],
                     "first_observed_tick": 1, "last_observed_tick": 1,
                     "visit_count": 0, "confidence": 1.0,
                     "observed_terrain": "grassland",
                     "observed_biome": "temperate_valley",
                     "observed_hazards": [], "agent_given_name": None,
                     "notes": []}
                 for t in tiles}}
    persist_known_map(rt._store.root, agent, known)


# ---------------------------------------------------------------------------
# the measurement
# ---------------------------------------------------------------------------

def test_nearest_known_water_is_measured_from_their_own_memory(tmp_path):
    rt = _runtime(tmp_path)
    _know_water(rt, ["cont_a_gen_-40_0", "cont_a_gen_20_-9"])
    # the agent is at (0,0); -40,0 is 40 tiles, 20,-9 is 20 tiles
    nearest = rt._nearest_known_water_for("east_adam")
    assert nearest["tile_id"] == "cont_a_gen_20_-9"
    assert nearest["distance"] == 20


def test_only_tiles_they_have_observed_count(tmp_path):
    """No true-map peeking: an agent who has seen nothing knows nothing."""
    rt = _runtime(tmp_path)
    assert rt._nearest_known_water_for("east_adam") == {}


def test_a_known_tile_on_the_other_continent_is_not_a_destination(tmp_path):
    """The continents share a coordinate space, so a cont_b tile is not
    'four tiles away' from an agent on cont_a."""
    rt = _runtime(tmp_path)
    _know_water(rt, ["cont_b_gen_1_0", "cont_a_gen_9_0"])
    nearest = rt._nearest_known_water_for("east_adam")
    assert nearest["tile_id"] == "cont_a_gen_9_0"
    assert nearest["distance"] == 9


def test_the_context_carries_it(tmp_path):
    rt = _runtime(tmp_path)
    _know_water(rt, ["cont_a_gen_5_0"])
    ctx = rt._build_context("east_adam", 150)
    assert ctx.nearest_known_water["tile_id"] == "cont_a_gen_5_0"
    assert ctx.nearest_known_water["distance"] == 5


# ---------------------------------------------------------------------------
# the disclosure
# ---------------------------------------------------------------------------

def _ctx(**kw):
    base = dict(
        agent_id="a", canonical_name="Adam", canonical_ref="east_adam",
        heartbeat_number=1, position=TILE, observation={}, memory=[], goals=[],
        unanswered_questions=[], world_public_objects={},
        habitat_allowed_tiles=[], habitat_movement_allowed=False,
        previous_action=None, timestamp_utc="t",
    )
    base.update(kw)
    return AgentContext(**base)


def test_a_thirsty_agent_is_told_where_the_water_it_knows_about_is():
    prompt = build_system_prompt(_ctx(
        observation={"self_body": {"thirst": 96.0, "hunger": 10.0,
                                    "vitality": 40.0, "warmth": 90.0,
                                    "downed": False},
                     "environment": {"drinkable_water": False}},
        nearest_known_water={"tile_id": "cont_a_gen_39_0", "distance": 5}))
    assert "cont_a_gen_39_0" in prompt
    assert "5 tiles" in prompt
    assert "nearest" in prompt.lower()


def test_a_collapsed_agent_is_told_where_the_water_is(tmp_path=None):
    """The cruellest gap: the collapsed branch replaced the whole body
    section, so the one agent who can CRAWL to water was the only one never
    told where it is. Measured 2026-11-14: both East agents collapsed at
    thirst 100 all night while the standing West agents got the line."""
    prompt = build_system_prompt(_ctx(
        nearest_known_water={"tile_id": "cont_a_gen_-39_0", "distance": 6},
        observation={"self_body": {"downed": True, "thirst": 100.0,
                                    "hunger": 100.0, "vitality": 4.0,
                                    "warmth": 90.0},
                     "environment": {"drinkable_water": False}}))
    assert "cont_a_gen_-39_0" in prompt
    assert "6 tiles away" in prompt
    assert "crawl" in prompt.lower()


def test_the_collapsed_water_line_has_no_directive_phrasing():
    from backend.world.first_pair_runtime import _BANNED_DIRECTIVE_PHRASES
    prompt = build_system_prompt(_ctx(
        nearest_known_water={"tile_id": "cont_a_gen_-39_0", "distance": 6},
        observation={"self_body": {"downed": True, "thirst": 100.0,
                                    "hunger": 100.0, "vitality": 4.0,
                                    "warmth": 90.0},
                     "environment": {"drinkable_water": False}}))
    for line in prompt.splitlines():
        if "nearest drinkable" in line.lower():
            for banned in _BANNED_DIRECTIVE_PHRASES:
                assert banned not in line.lower(), (banned, line[:140])


def test_a_comfortable_agent_is_not_nagged_about_water():
    prompt = build_system_prompt(_ctx(
        observation={"self_body": {"thirst": 12.0, "hunger": 10.0,
                                    "vitality": 90.0, "warmth": 90.0,
                                    "downed": False},
                     "environment": {"drinkable_water": False}},
        nearest_known_water={"tile_id": "cont_a_gen_39_0", "distance": 5}))
    assert "nearest drinkable" not in prompt.lower()


def test_no_known_water_means_no_line():
    prompt = build_system_prompt(_ctx(
        observation={"self_body": {"thirst": 96.0, "hunger": 10.0,
                                    "vitality": 40.0, "warmth": 90.0,
                                    "downed": False},
                     "environment": {"drinkable_water": False}}))
    assert "nearest drinkable" not in prompt.lower()


def test_the_water_line_carries_no_directive_phrasing():
    from backend.world.first_pair_runtime import _BANNED_DIRECTIVE_PHRASES
    prompt = build_system_prompt(_ctx(
        observation={"self_body": {"thirst": 96.0, "hunger": 10.0,
                                    "vitality": 40.0, "warmth": 90.0,
                                    "downed": False},
                     "environment": {"drinkable_water": False}},
        nearest_known_water={"tile_id": "cont_a_gen_39_0", "distance": 5}))
    for line in prompt.splitlines():
        if "nearest drinkable" in line.lower():
            for banned in _BANNED_DIRECTIVE_PHRASES:
                assert banned not in line.lower(), (banned, line[:120])
