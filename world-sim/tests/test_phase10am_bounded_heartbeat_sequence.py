"""Phase 10AM – Bounded Heartbeat Sequence Runner tests.

These tests validate the pure helper ``run_local_heartbeat_sequence`` which
chains multiple Phase 10AL heartbeats deterministically from a finite
heartbeat plan.

No runtime, pause, network I/O or hidden data leakage is involved.
"""

from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

# Ensure the repository root is on the import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.world.fog_of_war import (
    create_active_position,
    create_empty_known_map,
)
from backend.world.local_heartbeat_sequence import run_local_heartbeat_sequence

# Constants for the synthetic map (compatible with 10AL/10AK fixtures).
CONTINENT_ID = "cont_ak"
REGION_START = "reg_start"
REGION_EAST = "reg_east"
AGENT_ID = "am_explorer"

# Hidden terms that must not appear in public results.
HIDDEN_TERMS = {
    "tile_far",
    "tile_hidden",
    "true_map",
    "travel_edges",
    "Southern Plains",
    "Hidden Hollow",
    "lm_hidden_cavern",
    "Hidden Cavern",
    "grain",
    "crystals",
    "obsidian",
}


def _make_true_map() -> dict:
    """Minimal synthetic true_map compatible with 10AL/10AK contracts."""
    return {
        "schema_version": "7B.1",
        "world_id": "test_world_10am",
        "seed": "10am_seed",
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
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    for term in HIDDEN_TERMS:
        assert term not in text, f"hidden term leaked: {term}"


# ---------------------------------------------------------------------------
# Empty heartbeat plan
# ---------------------------------------------------------------------------


def test_empty_heartbeat_plan_returns_unchanged_safe_packet():
    true_map = _make_true_map()
    position = _start_position()
    known_map = _empty_known_map()
    result = run_local_heartbeat_sequence(
        true_map=true_map,
        current_position=position,
        known_map=known_map,
        heartbeat_plan=[],
        start_tick=1,
        sequence_id="seq-empty",
    )
    assert result["ok"] is True
    assert result["sequence_id"] == "seq-empty"
    assert result["start_tick"] == 1
    assert result["end_tick"] == 1
    assert result["final_position"] == copy.deepcopy(position)
    assert result["known_map"] == copy.deepcopy(known_map)
    assert result["heartbeats"] == []
    assert result["timeline"] == []
    assert result["error"] is None
    assert result["failed_heartbeat_id"] is None
    assert result["failed_heartbeat_index"] is None
    assert result["failed_tick"] is None
    assert result["failed_direction"] is None
    _assert_no_hidden(result)


# ---------------------------------------------------------------------------
# Two-heartbeat plan
# ---------------------------------------------------------------------------


def test_two_heartbeat_plan_reaches_east_tile():
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-2",
    )
    assert result["ok"] is True
    assert result["sequence_id"] == "seq-2"
    assert result["final_position"]["tile_id"] == "tile_east"
    assert result["final_position"]["region_id"] == REGION_EAST
    _assert_no_hidden(result)


def test_two_heartbeat_plan_known_map_carries_forward_and_grows():
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    known_tiles = set(result["known_map"].get("known_tiles", {}).keys())
    assert {"tile_start", "tile_north", "tile_east"}.issubset(known_tiles)
    assert len(result["heartbeats"]) == 2
    # Known map carried forward: second heartbeat's known map should include
    # the first heartbeat's discoveries.
    first_known = set(result["heartbeats"][0]["known_map"].get("known_tiles", {}).keys())
    second_known = set(result["heartbeats"][1]["known_map"].get("known_tiles", {}).keys())
    assert first_known.issubset(second_known)
    _assert_no_hidden(result)


def test_ticks_deterministic_across_two_heartbeats():
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    # Tick layout: hb-1 observe(1) move(2) observe(3); hb-2 observe(4) move(5) observe(6).
    assert result["start_tick"] == 1
    assert result["end_tick"] == 6
    assert result["heartbeats"][0]["start_tick"] == 1
    assert result["heartbeats"][0]["end_tick"] == 3
    assert result["heartbeats"][1]["start_tick"] == 4
    assert result["heartbeats"][1]["end_tick"] == 6
    # Flattened timeline ticks 1..6 with observe/move pattern.
    assert [(e["tick"], e["action"]) for e in result["timeline"]] == [
        (1, "observe"),
        (2, "move_local"),
        (3, "observe"),
        (4, "observe"),
        (5, "move_local"),
        (6, "observe"),
    ]
    _assert_no_hidden(result)


# ---------------------------------------------------------------------------
# Monkeypatch call count
# ---------------------------------------------------------------------------


def test_monkeypatch_one_call_per_plan_item_with_copies(monkeypatch):
    calls: list[dict] = []

    def fake_run_local_exploration_heartbeat(**kwargs):
        calls.append(kwargs)
        start_tick = kwargs.get("start_tick", 1)
        # Echo back successful minimal result matching 10AL return shape.
        return {
            "ok": True,
            "heartbeat_id": kwargs.get("heartbeat_id"),
            "heartbeat_index": kwargs.get("heartbeat_index"),
            "start_tick": start_tick,
            "end_tick": start_tick + 2,
            "final_position": copy.deepcopy(kwargs["current_position"]),
            "known_map": kwargs["known_map"],
            "timeline": [{"tick": start_tick, "action": "observe"}],
            "heartbeat_record": {},
            "error": None,
            "failed_tick": None,
            "failed_direction": None,
        }

    lhh = importlib.import_module("backend.world.local_heartbeat_sequence")
    monkeypatch.setattr(
        lhh, "run_local_exploration_heartbeat", fake_run_local_exploration_heartbeat
    )

    true_map = _make_true_map()
    position = _start_position()
    known = _empty_known_map()
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
        {"heartbeat_id": "hb-3", "directions": ["north"]},
    ]

    result = run_local_heartbeat_sequence(
        true_map=true_map,
        current_position=position,
        known_map=known,
        heartbeat_plan=plan,
        start_tick=1,
    )

    assert len(calls) == 3
    # Each call receives a deep copy of current_position / known_map (different ids).
    assert calls[0]["current_position"] is not position
    assert calls[0]["known_map"] is not known
    for c in calls:
        assert c["current_position"] is not position
        assert c["known_map"] is not known
    # Deterministic start ticks: 1, then previous end + 1 = 4, then 7.
    assert calls[0]["start_tick"] == 1
    assert calls[1]["start_tick"] == 4
    assert calls[2]["start_tick"] == 7
    # heartbeat_id and heartbeat_index forwarded from plan.
    assert calls[0]["heartbeat_id"] == "hb-1"
    assert calls[0]["heartbeat_index"] == 0
    assert calls[1]["heartbeat_index"] == 1
    assert calls[2]["heartbeat_index"] == 2
    assert result["ok"] is True
    _assert_no_hidden(result)


# ---------------------------------------------------------------------------
# Blocked move stops sequence cleanly
# ---------------------------------------------------------------------------


def test_blocked_move_stops_sequence_cleanly_with_prior_heartbeats():
    # First heartbeat: north (ok). Second heartbeat: north again into empty
    # space (no tile at (0,-2)) -> blocked stop.
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-block", "directions": ["north"]},
    ]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    assert result["ok"] is False
    assert result["failed_heartbeat_id"] == "hb-block"
    assert result["failed_heartbeat_index"] == 1
    assert result["failed_direction"] == "north"
    assert result["failed_tick"] == 5  # hb-2: observe(4) move(5) blocked
    assert "no tile" in (result["error"] or "").lower()
    # Final position should reflect the prior successful heartbeat.
    assert result["final_position"]["tile_id"] == "tile_north"
    # Prior successful heartbeat data is preserved.
    assert len(result["heartbeats"]) == 2
    assert result["heartbeats"][0]["ok"] is True
    # Timeline includes entries up to the failure.
    assert len(result["timeline"]) >= 4
    _assert_no_hidden(result)


# ---------------------------------------------------------------------------
# Invalid direction raises ValueError
# ---------------------------------------------------------------------------


def test_invalid_direction_raises_value_error():
    plan = [{"heartbeat_id": "hb-1", "directions": ["sideways"]}]
    with pytest.raises(ValueError, match="unrecognised direction"):
        run_local_heartbeat_sequence(
            true_map=_make_true_map(),
            current_position=_start_position(),
            known_map=_empty_known_map(),
            heartbeat_plan=plan,
            start_tick=1,
        )


# ---------------------------------------------------------------------------
# No hidden true_map leaks
# ---------------------------------------------------------------------------


def test_no_true_map_substrate_in_result():
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    _assert_no_hidden(result)
    assert "true_map" not in result
    assert "true_map" not in json.dumps(result, sort_keys=True)


# ---------------------------------------------------------------------------
# Caller-owned inputs not mutated
# ---------------------------------------------------------------------------


def test_caller_owned_inputs_not_mutated():
    true_map = _make_true_map()
    position = _start_position()
    known_map = _empty_known_map()
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    true_map_before = copy.deepcopy(true_map)
    position_before = copy.deepcopy(position)
    known_map_before = copy.deepcopy(known_map)
    plan_before = copy.deepcopy(plan)

    run_local_heartbeat_sequence(
        true_map=true_map,
        current_position=position,
        known_map=known_map,
        heartbeat_plan=plan,
        start_tick=1,
    )

    assert true_map == true_map_before
    assert position == position_before
    assert known_map == known_map_before
    assert plan == plan_before


# ---------------------------------------------------------------------------
# Deterministic replay
# ---------------------------------------------------------------------------


def test_deterministic_replay():
    plan = [
        {"heartbeat_id": "hb-1", "directions": ["north"]},
        {"heartbeat_id": "hb-2", "directions": ["southeast"]},
    ]
    first = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    second = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
    )
    assert first["final_position"] == second["final_position"]
    assert first["known_map"] == second["known_map"]
    assert first["timeline"] == second["timeline"]
    assert first["end_tick"] == second["end_tick"]
    assert [h["heartbeat_id"] for h in first["heartbeats"]] == [
        h["heartbeat_id"] for h in second["heartbeats"]
    ]


# ---------------------------------------------------------------------------
# Source scan for runtime markers
# ---------------------------------------------------------------------------


def test_production_source_scan_for_runtime_markers():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "world"
        / "local_heartbeat_sequence.py"
    )
    content = source_path.read_text()
    prohibited = [
        "while True",
        "sleep",
        "threading",
        "asyncio",
        "requests",
        "http",
        "socket",
        "provider",
        "Docker",
        "daemon",
        "scheduler",
    ]
    for term in prohibited:
        assert term not in content, f"Forbidden term found: {term}"


# ---------------------------------------------------------------------------
# Return field contract
# ---------------------------------------------------------------------------


def test_return_fields_contract():
    plan = [{"heartbeat_id": "hb-1", "directions": ["north"]}]
    result = run_local_heartbeat_sequence(
        true_map=_make_true_map(),
        current_position=_start_position(),
        known_map=_empty_known_map(),
        heartbeat_plan=plan,
        start_tick=1,
        sequence_id="seq-contract",
    )
    expected_keys = {
        "ok",
        "sequence_id",
        "start_tick",
        "end_tick",
        "final_position",
        "known_map",
        "heartbeats",
        "timeline",
        "error",
        "failed_heartbeat_id",
        "failed_heartbeat_index",
        "failed_tick",
        "failed_direction",
    }
    assert set(result.keys()) == expected_keys
    assert "true_map" not in result
