"""Phase 10AL – Tiny Local Heartbeat Harness tests.

These tests validate the pure helper ``run_local_exploration_heartbeat`` which
wraps the deterministic multi‑tick exploration loop (Phase 10AK) and provides a
minimal heartbeat boundary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import importlib

# Ensure the repository root is on the import path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import create_active_position, create_empty_known_map
from backend.world.local_heartbeat_harness import run_local_exploration_heartbeat

# Constants for synthetic map.
CONTINENT_ID = "cont_ak"
REGION_START = "reg_start"
REGION_EAST = "reg_east"
AGENT_ID = "ak_explorer"

# Hidden terms that must not appear in public results.
HIDDEN_TERMS = {"tile_far", "tile_hidden", "true_map", "travel_edges", "Southern Plains", "Hidden Hollow", "lm_hidden_cavern", "Hidden Cavern", "grain", "crystals", "obsidian", "travel_edges"}


def _make_true_map() -> dict:
    """Create a minimal synthetic true_map.

    Includes a start tile, a north tile, an east tile and a far hidden tile that
    should never be exposed in the heartbeat result.
    """
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10al",
        "seed": "10al_seed",
        "continents": [{"continent_id": CONTINENT_ID, "name": "Test"}],
        "regions": [
            {"region_id": REGION_START, "continent_id": CONTINENT_ID, "name": "Start"},
            {"region_id": REGION_EAST, "continent_id": CONTINENT_ID, "name": "East"},
        ],
        "tiles": [
            {
                "tile_id": "tile_start",
                "continent_id": CONTINENT_ID,
                "region_id": REGION_START,
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grass",
                "blocks_travel": False,
                "landmark_ids": [],
                "resources": [],
                "hazards": [],
                "biome": "grassland",
                "elevation": 0,
                "water": False,
            },
            {
                "tile_id": "tile_north",
                "continent_id": CONTINENT_ID,
                "region_id": REGION_START,
                "coordinates": {"x": 0, "y": -1},
                "terrain": "forest",
                "blocks_travel": False,
                "landmark_ids": [],
                "resources": [],
                "hazards": [],
                "biome": "forest",
                "elevation": 0,
                "water": False,
            },
            {
                "tile_id": "tile_east",
                "continent_id": CONTINENT_ID,
                "region_id": REGION_EAST,
                "coordinates": {"x": 1, "y": 0},
                "terrain": "desert",
                "blocks_travel": False,
                "landmark_ids": [],
                "resources": [],
                "hazards": [],
                "biome": "desert",
                "elevation": 0,
                "water": False,
            },
            # Hidden far tile – never reachable in the test scenarios.
            {
                "tile_id": "tile_far",
                "continent_id": CONTINENT_ID,
                "region_id": REGION_EAST,
                "coordinates": {"x": 5, "y": 5},
                "terrain": "mountain",
                "blocks_travel": False,
                "landmark_ids": [],
                "resources": [],
                "hazards": [],
                "biome": "mountain",
                "elevation": 1000,
                "water": False,
            },
        ],
        "landmarks": [],
        "resources": [],
        "hazards": [],
        "mysteries": [],
        "travel_edges": [],
    }


def _start_position() -> dict:
    return create_active_position(
        agent_id=AGENT_ID,
        continent_id=CONTINENT_ID,
        region_id=REGION_START,
        tile_id="tile_start",
        coordinates={"x": 0, "y": 0},
    )


def _empty_known_map() -> dict:
    return create_empty_known_map(AGENT_ID)


def _assert_no_hidden(value) -> None:
    """Assert that none of the forbidden hidden terms appear in the JSON.
    """
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    for term in HIDDEN_TERMS:
        assert term not in text, f"hidden term leaked: {term}"


def test_successful_heartbeat_two_steps():
    true_map = _make_true_map()
    result = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["north", "southeast"],
        start_tick=10,
    )
    # Basic success fields.
    assert result["ok"] is True
    assert result["final_position"]["tile_id"] == "tile_east"
    # Ticks: start_tick 10 -> observe (10), move north (11), observe (12), move southeast (13), observe (14)
    assert result["end_tick"] == 14
    assert result["heartbeat_id"] == "heartbeat-10"
    # Known map should now contain start, north and east tiles.
    known_tiles = set(result["known_map"].get("known_tiles", {}).keys())
    assert {"tile_start", "tile_north", "tile_east"}.issubset(known_tiles)
    _assert_no_hidden(result)


def test_invalid_direction_raises():
    with pytest.raises(ValueError, match="unrecognised direction"):
        run_local_exploration_heartbeat(
            true_map=_make_true_map(),
            current_position=_start_position(),
            known_map=_empty_known_map(),
            directions=["sideways"],
        )


def test_blocked_move_returns_failure():
    true_map = _make_true_map()
    result = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["south"],  # No tile at (0,1)
        start_tick=1,
    )
    assert result["ok"] is False
    assert result["failed_tick"] == 2  # observe tick1 then move attempt tick2
    assert result["failed_direction"] == "south"
    assert "no tile at destination" in result["error"].lower()
    # Position should remain at start.
    assert result["final_position"]["tile_id"] == "tile_start"
    _assert_no_hidden(result)


def test_sequential_heartbeats_continue_state():
    true_map = _make_true_map()
    # First heartbeat moves north.
    first = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["north"],
        start_tick=1,
    )
    # Second heartbeat continues from the result of the first.
    second = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=first["final_position"],
        known_map=first["known_map"],
        directions=["southeast"],
        start_tick=first["end_tick"] + 1,
    )
    assert second["final_position"]["tile_id"] == "tile_east"
    assert second["start_tick"] == 4  # first heartbeat end_tick 3, plus 1
    assert second["end_tick"] == 6
    _assert_no_hidden(second)


def test_heartbeat_record_structure():
    true_map = _make_true_map()
    result = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["north"],
        start_tick=3,
        heartbeat_index=7,
    )
    hb = result["heartbeat_record"]
    expected_keys = {"heartbeat_id", "heartbeat_index", "start_tick", "end_tick", "ok", "action_count", "final_tile_id", "error"}
    assert set(hb) == expected_keys
    assert hb["heartbeat_index"] == 7
    assert hb["start_tick"] == 3
    assert hb["end_tick"] == result["end_tick"]
    assert hb["action_count"] == len(result["timeline"])
    _assert_no_hidden(hb)

# Additional tests for call count, deterministic replay, and source scan

def test_monkeypatch_calls_and_copies(monkeypatch):
    call_data = {}
    call_counter = {"calls": 0}
    def fake_run_multi_tick_exploration(**kwargs):
        call_counter["calls"] += 1
        call_data.update({k: id(v) for k, v in kwargs.items()})
        # Return minimal successful result matching expected structure
        return {
            "ok": True,
            "timeline": [{"tick": kwargs.get("start_tick", 1)}],
            "final_position": kwargs["initial_position"],
            "known_map": kwargs["initial_known_map"],
            "failed_tick": None,
            "failed_direction": None,
            "error": None,
        }
    lhh = importlib.import_module('backend.world.local_heartbeat_harness')
    monkeypatch.setattr(lhh, 'run_multi_tick_exploration', fake_run_multi_tick_exploration)
    true_map = _make_true_map()
    cur = _start_position()
    known = _empty_known_map()
    dirs = ["north"]
    result = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=cur,
        known_map=known,
        directions=dirs,
    )
    # ensure function called exactly once via presence of keys
    assert "true_map" in call_data and "initial_position" in call_data
    # Ensure copies were passed (different ids)
    assert call_data["initial_position"] != id(cur)
    assert call_data["initial_known_map"] != id(known)
    assert call_data["directions"] != id(dirs)
    assert result["ok"] is True
    assert call_counter["calls"] == 1


def test_deterministic_replay():
    true_map = _make_true_map()
    first = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["north", "southeast"],
        start_tick=1,
    )
    second = run_local_exploration_heartbeat(
        true_map=true_map,
        current_position=_start_position(),
        known_map=_empty_known_map(),
        directions=["north", "southeast"],
        start_tick=1,
    )
    assert first["final_position"] == second["final_position"]
    assert first["known_map"] == second["known_map"]
    assert first["timeline"] == second["timeline"]


def test_production_source_scan():
    source_path = Path(__file__).resolve().parents[1] / "backend" / "world" / "local_heartbeat_harness.py"
    content = source_path.read_text()
    prohibited = ["while True", "sleep", "threading", "asyncio", "requests", "http", "socket", "provider", "Docker", "daemon", "scheduler"]
    for term in prohibited:
        assert term not in content, f"Forbidden term found: {term}"