"""Phase 10AK — Multi-Tick Exploration Loop Contract."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import create_active_position, create_empty_known_map
from backend.world.local_exploration_loop import run_multi_tick_exploration
from backend.world.slice_to_event_bridge import observation_slice_to_candidate
from backend.world.world_event_candidate_mapper import candidate_from_move_result
from backend.world.world_event_exporter import export_events
from backend.world.world_event_ledger import append_event, read_events
from backend.world.world_event_sanitizer import sanitize_public_text
from backend.world.world_event_verifier import verify_candidate_event

CONTINENT_ID = "cont_ak"
REGION_START_ID = "reg_start"
REGION_EAST_ID = "reg_east"
REGION_SOUTH_ID = "reg_south"
REGION_HIDDEN_ID = "reg_hidden"
AGENT_ID = "ak_explorer"

HIDDEN_TERMS = {
    "tile_far",
    "tile_hidden",
    "Southern Plains",
    "Hidden Hollow",
    "lm_hidden_cavern",
    "grain",
    "crystals",
    "obsidian",
    "true_map",
    "travel_edges",
}


def _make_true_map() -> dict:
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10ak",
        "seed": "10ak_seed",
        "continents": [{"continent_id": CONTINENT_ID, "name": "Test Continent"}],
        "regions": [
            {"region_id": REGION_START_ID, "continent_id": CONTINENT_ID, "name": "Start Vale"},
            {"region_id": REGION_EAST_ID, "continent_id": CONTINENT_ID, "name": "Eastern Ridge"},
            {"region_id": REGION_SOUTH_ID, "continent_id": CONTINENT_ID, "name": "Southern Plains"},
            {"region_id": REGION_HIDDEN_ID, "continent_id": CONTINENT_ID, "name": "Hidden Hollow"},
        ],
        "tiles": [
            {
                "tile_id": "tile_start", "continent_id": CONTINENT_ID,
                "region_id": REGION_START_ID, "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland", "biome": "temperate", "elevation": 10,
                "water": None, "resources": ["herbs"], "hazards": [],
                "landmark_ids": ["lm_start_shrine"], "blocks_travel": False,
            },
            {
                "tile_id": "tile_north_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_START_ID, "coordinates": {"x": 0, "y": -1},
                "terrain": "forest", "biome": "boreal", "elevation": 15,
                "water": None, "resources": ["wood", "berries"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_blocked_south", "continent_id": CONTINENT_ID,
                "region_id": REGION_START_ID, "coordinates": {"x": 0, "y": 1},
                "terrain": "mountain", "biome": "alpine", "elevation": 100,
                "water": None, "resources": ["stone"], "hazards": ["avalanche"],
                "landmark_ids": [], "blocks_travel": True,
            },
            {
                "tile_id": "tile_east_1", "continent_id": CONTINENT_ID,
                "region_id": REGION_EAST_ID, "coordinates": {"x": 1, "y": 0},
                "terrain": "desert", "biome": "arid", "elevation": 5,
                "water": None, "resources": ["sand"], "hazards": ["heat"],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_far", "continent_id": CONTINENT_ID,
                "region_id": REGION_SOUTH_ID, "coordinates": {"x": 5, "y": 5},
                "terrain": "plain", "biome": "savanna", "elevation": 3,
                "water": None, "resources": ["grain"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
            {
                "tile_id": "tile_hidden", "continent_id": CONTINENT_ID,
                "region_id": REGION_HIDDEN_ID, "coordinates": {"x": -5, "y": 5},
                "terrain": "cave", "biome": "subterranean", "elevation": -10,
                "water": None, "resources": ["crystals", "obsidian"],
                "hazards": ["darkness"], "landmark_ids": ["lm_hidden_cavern"],
                "blocks_travel": True,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_start_shrine", "continent_id": CONTINENT_ID,
                "tile_id": "tile_start", "kind": "shrine",
                "hidden_name": "Shrine of Beginnings", "description": "A simple stone shrine",
            },
            {
                "landmark_id": "lm_hidden_cavern", "continent_id": CONTINENT_ID,
                "tile_id": "tile_hidden", "kind": "cavern",
                "hidden_name": "Hidden Cavern", "description": "A deep underground cavern",
            },
        ],
        "resources": [],
        "hazards": [],
        "mysteries": [],
        "travel_edges": [],
    }


def _start_position() -> dict:
    return create_active_position(
        agent_id=AGENT_ID,
        continent_id=CONTINENT_ID,
        region_id=REGION_START_ID,
        tile_id="tile_start",
        coordinates={"x": 0, "y": 0},
    )


def _empty_known_map() -> dict:
    return create_empty_known_map(AGENT_ID)


def _run_success() -> dict:
    return run_multi_tick_exploration(
        true_map=_make_true_map(),
        initial_position=_start_position(),
        initial_known_map=_empty_known_map(),
        directions=["north", "southeast"],
    )


def _assert_no_hidden(value) -> None:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    for term in HIDDEN_TERMS:
        assert term not in text, f"hidden term leaked: {term}"


def test_empty_known_map_enters_loop_and_gets_populated():
    result = _run_success()
    assert result["ok"] is True
    assert result["known_map"]["known_tiles"]
    assert "tile_start" in result["known_map"]["known_tiles"]


def test_timeline_ticks_are_deterministic():
    result = _run_success()
    assert [(e["tick"], e["action"]) for e in result["timeline"]] == [
        (1, "observe"),
        (2, "move_local"),
        (3, "observe"),
        (4, "move_local"),
        (5, "observe"),
    ]


def test_final_position_after_north_then_southeast_is_east_tile():
    result = _run_success()
    assert result["final_position"]["tile_id"] == "tile_east_1"
    assert result["final_position"]["region_id"] == REGION_EAST_ID


def test_known_map_contains_discovered_tiles_from_all_observed_positions():
    result = _run_success()
    tiles = result["known_map"]["known_tiles"]
    assert "tile_start" in tiles
    assert "tile_north_1" in tiles
    assert "tile_east_1" in tiles


def test_true_map_and_caller_owned_inputs_are_not_mutated():
    true_map = _make_true_map()
    position = _start_position()
    known_map = _empty_known_map()
    true_map_before = copy.deepcopy(true_map)
    position_before = copy.deepcopy(position)
    known_map_before = copy.deepcopy(known_map)

    run_multi_tick_exploration(
        true_map=true_map,
        initial_position=position,
        initial_known_map=known_map,
        directions=["north", "southeast"],
    )

    assert true_map == true_map_before
    assert position == position_before
    assert known_map == known_map_before


def test_result_and_known_map_do_not_leak_hidden_substrate():
    result = _run_success()
    _assert_no_hidden(result)
    _assert_no_hidden(result["known_map"])


def test_observe_candidates_verify():
    result = _run_success()
    existing: list[dict] = []
    observe_ticks = [entry["tick"] for entry in result["timeline"] if entry["action"] == "observe"]
    for observation, tick in zip(result["observations"], observe_ticks):
        candidate = observation_slice_to_candidate(observation, actor_id=AGENT_ID, tick=tick)
        verification = verify_candidate_event(candidate, existing)
        assert verification["accepted"], verification["errors"]
        existing.append(candidate)


def test_move_candidates_verify():
    result = _run_success()
    existing: list[dict] = []
    move_ticks = [entry["tick"] for entry in result["timeline"] if entry["action"] == "move_local"]
    for move_result, tick in zip(result["move_results"], move_ticks):
        candidate = candidate_from_move_result(AGENT_ID, f"Moved at tick {tick}", move_result, tick=tick)
        verification = verify_candidate_event(candidate, existing)
        assert verification["accepted"], verification["errors"]
        existing.append(candidate)


def test_ledger_records_observe_move_observe_move_observe(tmp_path):
    result = _run_success()
    ledger = tmp_path / "ledger.jsonl"
    existing: list[dict] = []
    observation_by_tick = dict(zip([1, 3, 5], result["observations"]))
    move_by_tick = dict(zip([2, 4], result["move_results"]))

    for entry in result["timeline"]:
        tick = entry["tick"]
        if entry["action"] == "observe":
            candidate = observation_slice_to_candidate(observation_by_tick[tick], actor_id=AGENT_ID, tick=tick)
        else:
            candidate = candidate_from_move_result(AGENT_ID, f"Moved at tick {tick}", move_by_tick[tick], tick=tick)
        verification = verify_candidate_event(candidate, existing)
        assert verification["accepted"], verification["errors"]
        append_result = append_event(ledger, candidate)
        assert append_result["ok"], append_result["errors"]
        existing.append(candidate)

    events = read_events(ledger)
    assert [event["action_type"] for event in events] == [
        "observe",
        "move_local",
        "observe",
        "move_local",
        "observe",
    ]


def test_export_and_sanitize_remain_safe(tmp_path):
    result = _run_success()
    ledger = tmp_path / "ledger.jsonl"
    existing: list[dict] = []
    observation_by_tick = dict(zip([1, 3, 5], result["observations"]))
    move_by_tick = dict(zip([2, 4], result["move_results"]))

    for entry in result["timeline"]:
        tick = entry["tick"]
        if entry["action"] == "observe":
            candidate = observation_slice_to_candidate(observation_by_tick[tick], actor_id=AGENT_ID, tick=tick)
        else:
            candidate = candidate_from_move_result(AGENT_ID, f"Moved at tick {tick}", move_by_tick[tick], tick=tick)
        verification = verify_candidate_event(candidate, existing)
        assert verification["accepted"], verification["errors"]
        append_event(ledger, candidate)
        existing.append(candidate)

    exported = export_events(read_events(ledger))
    sanitized = sanitize_public_text(exported)
    _assert_no_hidden(exported)
    _assert_no_hidden(sanitized)


def test_blocked_move_stops_cleanly_after_prior_observation():
    result = run_multi_tick_exploration(
        true_map=_make_true_map(),
        initial_position=_start_position(),
        initial_known_map=_empty_known_map(),
        directions=["south"],
    )
    assert result["ok"] is False
    assert result["failed_tick"] == 2
    assert result["failed_direction"] == "south"
    assert "blocked" in result["error"].lower()
    assert result["final_position"]["tile_id"] == "tile_start"
    assert len(result["observations"]) == 1
    assert result["known_map"]["known_tiles"]
    assert "tile_start" in result["known_map"]["known_tiles"]


def test_invalid_direction_raises_value_error():
    with pytest.raises(ValueError, match="unrecognised direction"):
        run_multi_tick_exploration(
            true_map=_make_true_map(),
            initial_position=_start_position(),
            initial_known_map=_empty_known_map(),
            directions=["sideways"],
        )


def test_deterministic_replay():
    result1 = _run_success()
    result2 = _run_success()
    assert result1["final_position"] == result2["final_position"]
    assert result1["known_map"] == result2["known_map"]
    assert result1["timeline"] == result2["timeline"]
    assert [obs["visible_tile_ids"] for obs in result1["observations"]] == [
        obs["visible_tile_ids"] for obs in result2["observations"]
    ]
