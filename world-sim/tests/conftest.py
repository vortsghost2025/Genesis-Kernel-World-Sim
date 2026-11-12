"""Shared pytest configuration for the world-sim test suite.

The suite was written against one Windows workstation and made silent
assumptions about it: gitignored data present, a user-level Telegram
token, absolute backslash paths. Running the whole suite anywhere else
produced a wall of environment failures that drowned out real regressions.

This conftest makes the assumptions EXPLICIT so they read as honest skips
rather than failures. It does not weaken any test: a test that needs data
declares that it needs data, and skips with a reason when it is absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
REPO_ROOT = WORLD_SIM.parent

# --- 1. Data that is generated or gitignored: fixture or skip, never fail ----
#
# `data/world/true_map.json`, `viewer/viewer_data.js` and `.runtime/` are
# gitignored/build artifacts on Sean's box. Tests that need them must say so.
TRUE_MAP = WORLD_SIM / "data" / "world" / "true_map.json"
VIEWER_DATA = WORLD_SIM / "viewer" / "viewer_data.js"
EAST_STORE = WORLD_SIM / ".runtime" / "first-pair"
WEST_STORE = WORLD_SIM / ".runtime" / "first-pair-west"

needs_true_map = pytest.mark.skipif(
    not TRUE_MAP.exists(),
    reason="data/world/true_map.json is gitignored; generate it before running "
           "viewer/world-map suites (see scripts/generate_world_scale.py)",
)
needs_viewer_data = pytest.mark.skipif(
    not VIEWER_DATA.exists(),
    reason="viewer/viewer_data.js is a build artifact; run "
           "scripts/export_viewer_snapshot.py first",
)
needs_lane_store = pytest.mark.skipif(
    not EAST_STORE.exists() or not WEST_STORE.exists(),
    reason=".runtime/ lane stores are gitignored live simulation data",
)

# A tiny canonical true-map fixture for tests that only need the shape.
FIXTURE_TRUE_MAP = {
    "schema_version": "world.1",
    "world_id": "fixture",
    "seed": "fixture-seed",
    "continents": [{"continent_id": "cont_a"}, {"continent_id": "cont_b"}],
    "regions": [],
    "landmarks": [],
    "resources": [
        {"resource_id": "res_a", "kind": "wood", "amount": 10,
         "renewable": True, "tile_id": "cont_a_origin_000"},
        {"resource_id": "res_b", "kind": "stone", "amount": 10,
         "renewable": True, "tile_id": "cont_a_origin_000"},
    ],
    "hazards": [],
    "mysteries": [],
    "travel_edges": [],
    "tiles": [
        {"tile_id": "cont_a_origin_000", "continent_id": "cont_a",
         "coordinates": {"x": 0, "y": 0}, "terrain": "grassland",
         "biome": "temperate_valley", "elevation": 0.2,
         "water": {"type": "river", "drinkable": True},
         "resources": ["wood", "stone"], "hazards": [],
         "landmark_ids": [], "blocks_travel": False},
    ],
}


@pytest.fixture
def fixture_true_map() -> dict:
    """A minimal, portable true-map for tests that need the shape, not the
    80,000-tile real thing."""
    import copy
    return copy.deepcopy(FIXTURE_TRUE_MAP)


@pytest.fixture
def portable_tmp(tmp_path):
    """A temp dir that is guaranteed to be on this platform's native
    separator. Tests must not hardcode 'C:/...' or 'S:\\...'."""
    return tmp_path


# --- 2. Platform-neutral process flags ---------------------------------------
#
# The runner uses Windows creationflags to spawn silently. Tests asserting
# that behaviour must assert it PORTABLY: windowless on Windows, plain on
# POSIX. Hardcoding one platform is what made the suite unrunnable off
# Sean's machine.
def portable_spawn_kwargs() -> dict:
    """The kwargs a subprocess must be able to accept on THIS platform."""
    return {} if not sys.platform.startswith("win") else {"creationflags": 0}


# --- 3. Credentials that live in the operator's user environment -------------#
# test_chain_watch demanded TELEGRAM_BOT_TOKEN in the user env, which fails
# on any fresh checkout. Fixture it so the test checks propagation, not
# the operator's machine.
@pytest.fixture
def telegram_credentials(monkeypatch) -> dict[str, str]:
    creds = {"TELEGRAM_BOT_TOKEN": "test-bot-token",
             "TELEGRAM_CHAT_ID": "test-chat-id"}
    for key, value in creds.items():
        monkeypatch.setenv(key, value)
    return creds


# --- 4. Path sanity: no absolute paths in committed code ---------------------
def pytest_collection_modifyitems(config, items):
    """Tag the environment-dependent suites so a report can separate them
    from real failures."""
    for item in items:
        markers = {mark.name for mark in item.iter_markers()}
        nodeid = item.nodeid
        if any(name in nodeid for name in (
            "test_lockstep_pair_filter", "test_streaming_count",
            "test_operator_desk", "test_chain_watch",
        )):
            item.add_marker(pytest.mark.env_dependent)
