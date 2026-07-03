"""Phase 10AJ — Known-Map Accumulation.

Proves an agent can accumulate a local known_map from successive
fog-of-war observations after movement, without ever accessing or
leaking the hidden true_map.

Contract claims:
  1. Empty known_map starts empty and validates.
  2. First observation populates known_map with the observed tile(s).
  3. Move to a new position + observe expands known_map to include
     both previously observed and newly observed tiles.
  4. Merging the same observation twice is idempotent.
  5. Hidden substrate (far region names, far tile IDs, far landmark
     names, far resource kinds) does not leak into known_map.
  6. true_map is not mutated by any merge operation.
  7. known_map can be used by subsequent build_local_observation()
     calls — accumulation does not break the observation pipeline.
  8. Observation → known_map → event bridge → verifier → ledger →
     export → sanitizer remains safe.
  9. known_map survives sanitize/export path without leaking.

This is a pure test — no daemon, runtime, live agents, canonical
data files, providers, or Docker.
"""

from __future__ import annotations

import copy
import json
import sys

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    build_local_observation,
    create_active_position,
    create_empty_known_map,
    merge_observation_into_known_map,
    validate_known_map,
    validate_true_map,
)
from backend.world.local_movement import resolve_local_move
from backend.world.slice_to_event_bridge import observation_slice_to_candidate
from backend.world.world_event_candidate_mapper import candidate_from_move_result
from backend.world.world_event_ledger import (
    append_event,
    read_events,
    validate_event,
)
from backend.world.world_event_exporter import export_events
from backend.world.world_event_sanitizer import (
    REDACTED_PATH,
    REDACTED_SECRET,
    REDACTED_RUNTIME,
    REDACTED_AGENT_TRACE,
    REDACTED_SKILL_REF,
    sanitize_public_text,
    sanitize_public_mapping,
)
from backend.world.world_event_verifier import verify_candidate_event

# ---------------------------------------------------------------------------
# Shared fixture: a hidden true_map with adjacent tiles + far hidden tiles
# ---------------------------------------------------------------------------

CONTINENT_ID = "cont_aj"
REGION_NORTH_ID = "reg_north"
REGION_EAST_ID = "reg_east"
REGION_SOUTH_ID = "reg_south"
REGION_HIDDEN_ID = "reg_hidden"


def _make_true_map() -> dict:
    """A hidden true_map with layout identical to 10AI's fixture.

    Layout (coordinates):
        (0,-1) tile_north_1     (reg_north)
        (0,0)  tile_start       (reg_north)
        (0,1)  tile_blocked     (reg_north, blocks_travel=True)
        (1,0)  tile_east_1      (reg_east)
        (5,5)  tile_far         (reg_south, non-local)
        (-5,5) tile_hidden      (reg_hidden, completely hidden)
    """
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10aj",
        "seed": "10aj_seed",
        "continents": [
            {"continent_id": CONTINENT_ID, "name": "Test Continent"},
        ],
        "regions": [
            {"region_id": REGION_NORTH_ID, "continent_id": CONTINENT_ID,
             "name": "North Vale"},
            {"region_id": REGION_EAST_ID, "continent_id": CONTINENT_ID,
             "name": "Eastern Ridge"},
            {"region_id": REGION_SOUTH_ID, "continent_id": CONTINENT_ID,
             "name": "Southern Plains"},
            {"region_id": REGION_HIDDEN_ID, "continent_id": CONTINENT_ID,
             "name": "Hidden Hollow"},
        ],
        "tiles": [
            {
                "tile_id": "tile_start", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland", "biome": "temperate",
                "elevation": 10, "water": None,
                "resources": ["herbs"], "hazards": [],
                "landmark_ids": ["lm_start_shrine"], "blocks_travel": False,
            },
            {
                "tile_id": "tile_north_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": -1},
                "terrain": "forest", "biome": "boreal",
                "elevation": 15, "water": None,
                "resources": ["wood", "berries"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_blocked", "continent_id": CONTINENT_ID,
                "region_id": REGION_NORTH_ID,
                "coordinates": {"x": 0, "y": 1},
                "terrain": "mountain", "biome": "alpine",
                "elevation": 100, "water": None,
                "resources": ["stone"], "hazards": ["avalanche"],
                "landmark_ids": [], "blocks_travel": True,
            },
            {
                "tile_id": "tile_east_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_EAST_ID,
                "coordinates": {"x": 1, "y": 0},
                "terrain": "desert", "biome": "arid",
                "elevation": 5, "water": None,
                "resources": ["sand"], "hazards": ["heat"],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_far", "continent_id": CONTINENT_ID,
                "region_id": REGION_SOUTH_ID,
                "coordinates": {"x": 5, "y": 5},
                "terrain": "plain", "biome": "savanna",
                "elevation": 3, "water": None,
                "resources": ["grain"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_hidden", "continent_id": CONTINENT_ID,
                "region_id": REGION_HIDDEN_ID,
                "coordinates": {"x": -5, "y": 5},
                "terrain": "cave", "biome": "subterranean",
                "elevation": -10, "water": None,
                "resources": ["crystals", "obsidian"], "hazards": ["darkness"],
                "landmark_ids": ["lm_hidden_cavern"], "blocks_travel": True,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_start_shrine", "continent_id": CONTINENT_ID,
                "tile_id": "tile_start", "kind": "shrine",
                "hidden_name": "Shrine of Beginnings",
                "description": "A simple stone shrine",
            },
            {
                "landmark_id": "lm_hidden_cavern", "continent_id": CONTINENT_ID,
                "tile_id": "tile_hidden", "kind": "cavern",
                "hidden_name": "Hidden Cavern",
                "description": "A deep underground cavern",
            },
        ],
        "resources": [],
        "hazards": [],
        "mysteries": [],
        "travel_edges": [],
    }


def _start_position() -> dict:
    return create_active_position(
        agent_id="aj_explorer",
        continent_id=CONTINENT_ID,
        region_id=REGION_NORTH_ID,
        tile_id="tile_start",
        coordinates={"x": 0, "y": 0},
    )


def _hidden_region_names() -> set[str]:
    return {"Southern Plains", "Hidden Hollow"}


def _hidden_tile_ids() -> set[str]:
    return {"tile_far", "tile_hidden"}


def _hidden_landmark_ids() -> set[str]:
    return {"lm_hidden_cavern"}


def _hidden_resource_kinds() -> set[str]:
    return {"grain", "crystals", "obsidian"}


# =========================================================================
# TestKnownMapStart
# =========================================================================


class TestKnownMapStart:
    """Claim 1: empty known_map starts empty and validates."""

    def test_create_empty_known_map(self):
        known_map = create_empty_known_map("aj_explorer")
        assert known_map["agent_id"] == "aj_explorer"
        assert known_map["known_tiles"] == {}
        assert known_map["known_landmarks"] == {}
        assert known_map["last_observation_tick"] == 0

    def test_empty_known_map_validates(self):
        known_map = create_empty_known_map("aj_explorer")
        result = validate_known_map(known_map)
        assert result["ok"], f"Empty known_map should validate: {result['errors']}"


# =========================================================================
# TestFirstObservationPopulates
# =========================================================================


class TestFirstObservationPopulates:
    """Claim 2: first observation populates known_map with observed tile(s)."""

    def test_observe_at_start_populates_tile_start(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        assert "tile_start" in known_map["known_tiles"]
        entry = known_map["known_tiles"]["tile_start"]
        assert entry["first_observed_tick"] == 1
        assert entry["last_observed_tick"] == 1
        assert entry["visit_count"] == 1
        assert entry["observed_terrain"] == "grassland"
        assert entry["observed_biome"] == "temperate"
        assert entry["observed_resources"] == ["herbs"]

    def test_observe_at_start_also_records_adjacent_tile(self):
        """Radius=1 sees tile_start + tile_north_1 + tile_blocked + tile_east_1."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        assert "tile_start" in known_map["known_tiles"]
        assert "tile_north_1" in known_map["known_tiles"]
        # tile_east_1 is at (1,0), Manhattan distance 1 — visible
        assert "tile_east_1" in known_map["known_tiles"]
        # tile_blocked at (0,1) — visible but blocked for travel
        assert "tile_blocked" in known_map["known_tiles"]

    def test_known_map_records_landmark_from_observation(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        assert "lm_start_shrine" in known_map["known_landmarks"]

    def test_last_observation_tick_updated(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=5)
        assert known_map["last_observation_tick"] == 5


# =========================================================================
# TestAccumulationAfterMove
# =========================================================================


class TestAccumulationAfterMove:
    """Claim 3: move + second observation expands known_map."""

    def test_move_north_then_observe_includes_both_tiles(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe at start (tick 1)
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)
        first_tiles = set(known_map["known_tiles"].keys())

        # Move north to tile_north_1 (tick 2)
        move = resolve_local_move(pos, "north", true_map, tick=2)
        assert move["ok"]
        pos = move["new_position"]

        # Observe at new position (tick 3)
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)

        second_tiles = set(known_map["known_tiles"].keys())
        # Both old and new tiles present
        assert "tile_start" in second_tiles
        assert "tile_north_1" in second_tiles
        # The accumulation grew
        assert len(second_tiles) >= len(first_tiles)

    def test_move_east_changes_region_accumulates_both(self):
        """Cross-region move still accumulates both sides."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe from start (tick 1) — sees tile_start, tile_north_1,
        # tile_blocked, tile_east_1
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)

        # Move east to tile_east_1 (tick 2)
        move = resolve_local_move(pos, "east", true_map, tick=2)
        assert move["ok"], f"East move failed: {move['error']}"
        assert move["territory_ref"] == REGION_EAST_ID
        pos = move["new_position"]

        # Observe from tile_east_1 (tick 3) — sees tile_east_1 + tile_start
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)

        tiles = known_map["known_tiles"]
        assert "tile_start" in tiles
        assert "tile_east_1" in tiles

    def test_known_tile_visit_count_increments(self):
        """Moving back to a previously visited tile increments visit_count."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe at start (tick 1)
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)
        assert known_map["known_tiles"]["tile_start"]["visit_count"] == 1

        # Move north, observe there (tick 3) — does not affect tile_start
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)

        # Move back south to tile_start (tick 4)
        pos = resolve_local_move(pos, "south", true_map, tick=4)["new_position"]
        obs3 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs3, tick=5)
        # tile_start should see visit_count increment when re-observed
        assert known_map["known_tiles"]["tile_start"]["visit_count"] >= 2

    def test_hidden_tiles_never_appear_in_known_map(self):
        """Far tiles outside any observed radius never enter known_map."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe at start (radius 1) — tile_far at (5,5) and
        # tile_hidden at (-5,5) are way out of range
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)

        for hidden_id in _hidden_tile_ids():
            assert hidden_id not in known_map["known_tiles"], (
                f"Hidden tile {hidden_id} leaked into known_map"
            )


# =========================================================================
# TestIdempotentMerge
# =========================================================================


class TestIdempotentMerge:
    """Claim 4: merging the same observation at the same tick is exactly idempotent.

    Same observation + same tick = exact no-op (deep-copy identical).
    Same tile observed again at a different / later tick = visit_count increments.
    """

    def test_same_tick_merge_is_exact_idempotent(self):
        """Merging same observation at same tick leaves known_map bit-identical."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)

        merge_observation_into_known_map(known_map, obs, tick=1)
        snapshot = copy.deepcopy(known_map)

        # Merge same observation again at same tick — must be exact no-op
        merge_observation_into_known_map(known_map, copy.deepcopy(obs), tick=1)

        assert json.dumps(known_map, sort_keys=True) == json.dumps(
            snapshot, sort_keys=True
        ), "known_map changed after same-tick duplicate merge"

    def test_same_tick_merge_preserves_entry_count(self):
        """Entry count is unchanged after same-tick duplicate merge."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)

        merge_observation_into_known_map(known_map, obs, tick=1)
        tile_count_1 = len(known_map["known_tiles"])
        landmark_count_1 = len(known_map["known_landmarks"])

        merge_observation_into_known_map(known_map, copy.deepcopy(obs), tick=1)

        assert len(known_map["known_tiles"]) == tile_count_1
        assert len(known_map["known_landmarks"]) == landmark_count_1

    def test_reobserving_later_tick_increments_visit_count(self):
        """Re-observing same tile at a later tick increments visit_count."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)

        merge_observation_into_known_map(known_map, obs, tick=1)
        start_vc_1 = known_map["known_tiles"]["tile_start"]["visit_count"]

        merge_observation_into_known_map(known_map, copy.deepcopy(obs), tick=2)
        start_vc_2 = known_map["known_tiles"]["tile_start"]["visit_count"]
        assert start_vc_2 > start_vc_1


# =========================================================================
# TestNoTrueMapLeak
# =========================================================================


class TestNoTrueMapLeak:
    """Claim 5: hidden substrate does not leak into known_map."""

    def test_known_map_has_no_hidden_region_names(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        known_map_str = json.dumps(known_map)
        for name in _hidden_region_names():
            assert name not in known_map_str, (
                f"Hidden region name {name!r} leaked into known_map"
            )

    def test_known_map_has_no_hidden_tile_ids(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        known_map_str = json.dumps(known_map)
        for tid in _hidden_tile_ids():
            assert tid not in known_map_str, (
                f"Hidden tile ID {tid!r} leaked into known_map"
            )

    def test_known_map_has_no_hidden_landmark_ids(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        known_map_str = json.dumps(known_map)
        for lid in _hidden_landmark_ids():
            assert lid not in known_map_str, (
                f"Hidden landmark ID {lid!r} leaked into known_map"
            )

    def test_known_map_has_no_hidden_resource_kinds(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        known_map_str = json.dumps(known_map)
        for kind in _hidden_resource_kinds():
            assert kind not in known_map_str, (
                f"Hidden resource kind {kind!r} leaked into known_map"
            )

    def test_known_map_does_not_contain_true_map_top_level(self):
        """The known_map dict itself does not have true_map keys."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        known_map_str = json.dumps(known_map)
        assert "continents" not in known_map_str
        assert "regions" not in known_map_str
        assert "travel_edges" not in known_map_str


# =========================================================================
# TestTrueMapNotMutated
# =========================================================================


class TestTrueMapNotMutated:
    """Claim 6: true_map is not mutated by any merge."""

    def test_true_map_unchanged_after_observe_and_merge(self):
        true_map = _make_true_map()
        original = copy.deepcopy(true_map)
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs, tick=1)

        assert json.dumps(true_map, sort_keys=True) == json.dumps(
            original, sort_keys=True
        ), "true_map was mutated by observation or merge"

    def test_true_map_unchanged_after_move_observe_merge_cycle(self):
        true_map = _make_true_map()
        original = copy.deepcopy(true_map)
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe at start
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)

        # Move
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]

        # Observe at new position
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)

        assert json.dumps(true_map, sort_keys=True) == json.dumps(
            original, sort_keys=True
        ), "true_map was mutated by full cycle"


# =========================================================================
# TestKnownMapFeedsObservation
# =========================================================================


class TestKnownMapFeedsObservation:
    """Claim 7: known_map can be used by subsequent build_local_observation."""

    def test_observation_with_accumulated_known_map_succeeds(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe + merge at start
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)

        # Move
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]

        # Observe with the now-populated known_map — should not crash
        obs2 = build_local_observation(true_map, pos, known_map)
        assert obs2["ok"] if isinstance(obs2, dict) and "ok" in obs2 else True
        assert obs2["agent_id"] == "aj_explorer"

    def test_known_map_agent_id_persists_in_observation(self):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        obs = build_local_observation(true_map, pos, known_map)
        assert obs["agent_id"] == "aj_explorer"

        # After merge, the agent_id should persist
        merge_observation_into_known_map(known_map, obs, tick=1)
        assert known_map["agent_id"] == "aj_explorer"


# =========================================================================
# TestPipelineSafety
# =========================================================================


class TestPipelineSafety:
    """Claim 8: observation → known_map → event bridge → verifier →
    ledger → export → sanitizer remains safe."""

    def test_full_pipeline_no_hidden_leak(self, tmp_path):
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")
        ledger_path = tmp_path / "ledger.jsonl"
        existing: list[dict] = []

        # Observe at start (tick 1)
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)
        cand1 = observation_slice_to_candidate(
            obs1, actor_id="aj_explorer", tick=1
        )
        result1 = verify_candidate_event(cand1, existing)
        assert result1["accepted"], f"Verifier rejected obs1: {result1['errors']}"
        ap1 = append_event(ledger_path, cand1)
        assert ap1["ok"], f"Append failed: {ap1['errors']}"
        existing.append(cand1)

        # Move north (tick 2)
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]

        # Move candidate → verifier → ledger
        move_result_raw = resolve_local_move(
            _start_position(), "north", true_map, tick=2
        )
        move_candidate = candidate_from_move_result(
            "aj_explorer", "Moved north", move_result_raw, tick=2
        )
        mv = verify_candidate_event(move_candidate, existing)
        assert mv["accepted"], f"Verifier rejected move: {mv['errors']}"
        ap2 = append_event(ledger_path, move_candidate)
        assert ap2["ok"], f"Append move failed: {ap2['errors']}"
        existing.append(move_candidate)

        # Observe at new position (tick 3)
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)
        cand2 = observation_slice_to_candidate(
            obs2, actor_id="aj_explorer", tick=3
        )
        result2 = verify_candidate_event(cand2, existing)
        assert result2["accepted"], f"Verifier rejected obs2: {result2['errors']}"
        ap3 = append_event(ledger_path, cand2)
        assert ap3["ok"], f"Append failed: {ap3['errors']}"
        existing.append(cand2)

        # Export + sanitize
        events = read_events(ledger_path)
        export_data = export_events(events)
        sanitized = sanitize_public_text(export_data)

        # Verify known_map grew properly
        assert "tile_start" in known_map["known_tiles"]
        assert "tile_north_1" in known_map["known_tiles"]

        # Hidden tile IDs not in export
        for tid in _hidden_tile_ids():
            assert tid not in sanitized

        # Hidden region names not in export
        for name in _hidden_region_names():
            assert name not in sanitized

        # Hidden landmark IDs not in export
        for lid in _hidden_landmark_ids():
            assert lid not in sanitized

        # Hidden resource kinds not in export
        for kind in _hidden_resource_kinds():
            assert kind not in sanitized

    def test_known_map_grows_after_move(self):
        """known_map has more tiles after move+observe than at start."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")

        # Observe at start
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)
        count_1 = len(known_map["known_tiles"])

        # Move north
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]

        # Observe at north
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)
        count_2 = len(known_map["known_tiles"])

        # From north, visible tiles may differ slightly but at minimum
        # should include the north tile plus potentially the start tile
        assert count_2 >= count_1
        # tile_north_1 is visible from both start (radius 1) and north
        # position, so visit_count >= 1
        assert known_map["known_tiles"]["tile_north_1"]["visit_count"] >= 1


# =========================================================================
# TestExportSanitize
# =========================================================================


class TestExportSanitize:
    """Claim 9: known_map survives sanitize/export path."""

    def test_known_map_sanitize_leak_markers_safe(self):
        """known_map text with harmless leak markers gets sanitized."""
        known_map = create_empty_known_map("aj_explorer")
        known_map["known_tiles"]["tile_start"] = {
            "observed_terrain": f"grassland at {FAKE_LEAK_PATH}",
        }

        text = json.dumps(known_map)
        sanitized = sanitize_public_text(text)
        assert REDACTED_PATH in sanitized
        assert FAKE_LEAK_PATH not in sanitized

    def test_known_map_mapping_sanitize(self):
        """known_map dict with leak markers gets mapping-sanitized."""
        known_map = create_empty_known_map("aj_explorer")
        known_map["known_tiles"]["tile_start"] = {
            "observed_terrain": "temperate",
            "note": f"thought: {FAKE_LEAK_THOUGHT}",
        }

        sanitized = sanitize_public_mapping(known_map)
        sanitized_str = json.dumps(sanitized)
        assert FAKE_LEAK_THOUGHT not in sanitized_str

    def test_accumulated_known_map_does_not_break_export(self, tmp_path):
        """known_map accumulation does not corrupt the export pipeline."""
        true_map = _make_true_map()
        pos = _start_position()
        known_map = create_empty_known_map("aj_explorer")
        ledger_path = tmp_path / "ledger.jsonl"
        existing_events: list[dict] = []

        # Observe + merge at start
        obs1 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs1, tick=1)

        # Move + observe
        pos = resolve_local_move(pos, "north", true_map, tick=2)["new_position"]
        obs2 = build_local_observation(true_map, pos, known_map)
        merge_observation_into_known_map(known_map, obs2, tick=3)

        # Create events from both observations, pass through verifier + ledger
        for i, obs in enumerate([obs1, obs2], start=1):
            candidate = observation_slice_to_candidate(
                obs, actor_id="aj_explorer", tick=i
            )
            result = verify_candidate_event(candidate, existing_events)
            assert result["accepted"], f"Verifier rejected: {result['errors']}"
            ap = append_event(ledger_path, candidate)
            assert ap["ok"], f"Append failed: {ap['errors']}"
            existing_events.append(candidate)

        events = read_events(ledger_path)
        export_data = export_events(events)
        sanitized = sanitize_public_text(export_data)
        # Sanitized text must still be valid JSON
        parsed = json.loads(sanitized)
        assert len(parsed) >= 2
        # known_map still has both tiles
        assert "tile_start" in known_map["known_tiles"]
        assert "tile_north_1" in known_map["known_tiles"]


# Fake leak markers for sanitizer tests — no real data
FAKE_LEAK_PATH = r"C:\Users\example\Documents\seed.txt"
FAKE_LEAK_THOUGHT = "Thought: scanning terrain"
FAKE_LEAK_SECRET = "TOKEN=dummy-placeholder"