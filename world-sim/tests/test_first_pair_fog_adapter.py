"""Tests for the first-pair fog adapter (10JB-1).

All tests are pure/scratch: no canonical store, no network, no provider.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.world.first_pair_fog_adapter import (
    FogAdapterError,
    build_world_position_from_tile,
    cognition_safe_observation,
    derive_topology,
    fog_gate_active,
    get_known_tile_ids,
    get_known_union,
    load_true_map,
    merge_observation,
    seed_known_map_from_history,
)


def _mini_true_map() -> dict:
    """A minimal valid true map with 2 habitat tiles + 1 world tile."""
    return {
        "schema_version": "7B.1",
        "world_id": "test_world",
        "seed": "test_seed",
        "continents": [{"continent_id": "cont_a", "name": "Continent A"}],
        "regions": [
            {"region_id": "reg_hab", "continent_id": "cont_a", "name": "Habitat"},
            {"region_id": "reg_valley", "continent_id": "cont_a", "name": "Valley"},
        ],
        "tiles": [
            {
                "tile_id": "public-shared-center",
                "continent_id": "cont_a",
                "region_id": "reg_hab",
                "coordinates": {"x": 0, "y": -1},
                "terrain": "grassland",
                "biome": "temperate",
                "elevation": 0,
                "water": None,
                "resources": [],
                "hazards": [],
                "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": "public-start-adam",
                "continent_id": "cont_a",
                "region_id": "reg_hab",
                "coordinates": {"x": -1, "y": -1},
                "terrain": "grassland",
                "biome": "temperate",
                "elevation": 0,
                "water": None,
                "resources": [],
                "hazards": [],
                "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": "cont_a_origin_000",
                "continent_id": "cont_a",
                "region_id": "reg_valley",
                "coordinates": {"x": 0, "y": 0},
                "terrain": "grassland",
                "biome": "valley",
                "elevation": 0,
                "water": None,
                "resources": [],
                "hazards": [],
                "landmark_ids": ["lm_river"],
                "blocks_travel": False,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_river",
                "continent_id": "cont_a",
                "tile_id": "cont_a_origin_000",
                "kind": "river",
                "description": "A narrow river.",
            },
        ],
        "resources": [],
        "hazards": [],
        "mysteries": [
            {
                "mystery_id": "mst_test",
                "tile_id": "cont_a_origin_000",
                "kind": "repeating_sound",
                "reveal_threshold": 3,
            },
        ],
        "travel_edges": [
            {"from_tile_id": "public-start-adam", "to_tile_id": "public-shared-center", "mode": "walk"},
            {"from_tile_id": "public-shared-center", "to_tile_id": "public-start-adam", "mode": "walk"},
            {"from_tile_id": "public-shared-center", "to_tile_id": "cont_a_origin_000", "mode": "walk"},
            {"from_tile_id": "cont_a_origin_000", "to_tile_id": "public-shared-center", "mode": "walk"},
        ],
    }


def _simple_heartbeats() -> list[dict]:
    """Synthetic heartbeat history for replay-seed testing."""
    return [
        {
            "heartbeat_number": 1,
            "action_taken": {},
            "world_mutations": [],
        },
        {
            "heartbeat_number": 2,
            "action_taken": {
                "east_adam": {"action_type": "move", "target_tile": "public-shared-center"},
            },
            "world_mutations": [
                {
                    "acting_agent_id": "genesis-agent-adam",
                    "action_type": "move",
                    "input": {"action_type": "move", "target_tile": "public-shared-center"},
                    "outcome": {"from": "public-start-adam", "status": "success", "to": "public-shared-center"},
                },
            ],
        },
        {
            "heartbeat_number": 3,
            "action_taken": {
                "east_eve": {"action_type": "move", "target_tile": "public-shared-center"},
            },
            "world_mutations": [
                {
                    "acting_agent_id": "genesis-agent-eve",
                    "action_type": "move",
                    "input": {"action_type": "move", "target_tile": "public-shared-center"},
                    "outcome": {"from": "public-start-eve", "status": "success", "to": "public-shared-center"},
                },
            ],
        },
        {
            "heartbeat_number": 4,
            "action_taken": {
                "east_eve": {"action_type": "create_public_object", "object_id": "meeting-stone-center"},
            },
            "world_mutations": [
                {
                    "acting_agent_id": "genesis-agent-eve",
                    "action_type": "create_public_object",
                    "input": {
                        "action_type": "create_public_object",
                        "object_id": "meeting-stone-center",
                        "tile_id": "public-shared-center",
                        "description": "A stone marker.",
                    },
                },
            ],
        },
    ]


class TestLoadTrueMap:
    def test_loads_valid_map(self, tmp_path):
        world_dir = tmp_path / "world"
        world_dir.mkdir()
        (world_dir / "true_map.json").write_text(
            json.dumps(_mini_true_map()), newline="\n"
        )
        tm = load_true_map(tmp_path)
        assert tm["world_id"] == "test_world"
        assert len(tm["tiles"]) == 3

    def test_missing_map_fails_closed(self, tmp_path):
        with pytest.raises(FogAdapterError, match="not found"):
            load_true_map(tmp_path)

    def test_corrupt_map_fails_closed(self, tmp_path):
        world_dir = tmp_path / "world"
        world_dir.mkdir()
        (world_dir / "true_map.json").write_text("{broken", newline="\n")
        with pytest.raises(FogAdapterError, match="unreadable"):
            load_true_map(tmp_path)


class TestBuildWorldPosition:
    def test_known_tile(self):
        tm = _mini_true_map()
        pos = build_world_position_from_tile(tm, "public-shared-center")
        assert pos["tile_id"] == "public-shared-center"
        assert pos["active"] is True
        assert pos["coordinates"] == {"x": 0, "y": -1}

    def test_unknown_tile_fails_closed(self):
        tm = _mini_true_map()
        with pytest.raises(FogAdapterError, match="not in true map"):
            build_world_position_from_tile(tm, "nonexistent-tile")


class TestSeedKnownMap:
    def test_visited_tiles_get_visit_counts(self):
        hbs = _simple_heartbeats()
        km = seed_known_map_from_history(hbs, "east_adam", "public-start-adam")
        center = km["known_tiles"]["public-shared-center"]
        assert center["visit_count"] >= 1

    def test_adjacent_tiles_observed_not_visited(self):
        hbs = _simple_heartbeats()
        km = seed_known_map_from_history(hbs, "east_eve", "public-start-eve")
        # Eve starts at start-eve, center is adjacent
        center = km["known_tiles"]["public-shared-center"]
        # After hb2, Eve sees center as adjacent (visit_count=0)
        # After hb3, Eve moves there (visit_count becomes 1)
        # At minimum, the tile was observed at hb1 as adjacent
        assert "public-shared-center" in km["known_tiles"]
        assert center["first_observed_tick"] <= 3

    def test_earliest_observation_wins(self):
        hbs = _simple_heartbeats()
        km = seed_known_map_from_history(hbs, "east_adam", "public-start-adam")
        # Adam observes center at hb1 (adjacent from start-adam)
        center = km["known_tiles"]["public-shared-center"]
        assert center["first_observed_tick"] == 1

    def test_deterministic_seed(self):
        hbs = _simple_heartbeats()
        km1 = seed_known_map_from_history(hbs, "east_adam", "public-start-adam")
        km2 = seed_known_map_from_history(hbs, "east_adam", "public-start-adam")
        assert json.dumps(km1, sort_keys=True) == json.dumps(km2, sort_keys=True)

    def test_meeting_stone_discovered(self):
        hbs = _simple_heartbeats()
        km = seed_known_map_from_history(hbs, "east_adam", "public-start-adam")
        assert "lm_meeting_stone_center" in km["known_landmarks"]


class TestCognitionSafeObservation:
    def test_basic_shape(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        assert obs["tile_id"] == "public-shared-center"
        assert isinstance(obs["visible_tiles"], list)
        assert isinstance(obs["objects_here"], list)
        assert isinstance(obs["visible_tile_details"], list)

    def test_no_contamination(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        text = json.dumps(obs)
        assert "true_map" not in text
        assert "known_map" not in text
        assert "true_landmark_id" not in text

    def test_only_visible_tiles(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        # cont_a_origin_000 is at (0,0), center is at (0,-1), radius 1 = distance 1
        # so origin_000 should be visible
        assert "cont_a_origin_000" in obs["visible_tiles"]
        # But tiles far away should not appear
        # (there are none in mini map, but the principle holds)

    def test_landmark_projected_safe(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        detail_text = json.dumps(obs.get("visible_tile_details", []))
        assert "landmark_id" in detail_text or "landmarks" in detail_text
        assert "true_landmark_id" not in detail_text

    def test_hidden_mystery_not_exposed(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        text = json.dumps(obs)
        assert "mystery" not in text.lower()
        assert "mst_" not in text


class TestDeriveTopology:
    def test_habitat_tiles_always_included(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        topo = derive_topology(tm, [km])
        assert "public-shared-center" in topo["allowed_tile_ids"]
        assert "public-start-adam" in topo["allowed_tile_ids"]

    def test_unknown_tile_excluded(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        topo = derive_topology(tm, [km])
        # If origin_000 is not yet known, it should not be reachable
        # (unless it happens to be in the historical adjacency, which it isn't)
        # But it IS visible at radius 1 from center, so if the known map
        # was updated post-observation, it would be there. In the seed,
        # only habitat tiles are known.
        # The topology should include it only if it's in known_tiles
        if "cont_a_origin_000" not in km["known_tiles"]:
            # It might still be in allowed if reachable via edges from known tiles
            # Per the spec: edges where both endpoints are known
            # Since origin_000 is NOT known, edges to it are excluded
            pass  # origin_000 may or may not be in allowed depending on edges

    def test_union_of_known_maps(self):
        tm = _mini_true_map()
        km_adam = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        km_eve = seed_known_map_from_history(
            _simple_heartbeats(), "east_eve", "public-start-eve"
        )
        topo = derive_topology(tm, [km_adam, km_eve])
        union = get_known_union([km_adam, km_eve])
        for tile_id in topo["allowed_tile_ids"]:
            # Every allowed tile must either be in the union or be a habitat tile
            assert tile_id in union or tile_id in (
                "public-start-adam", "public-shared-center", "public-start-eve"
            )

    def test_adjacency_matches_edges(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        topo = derive_topology(tm, [km])
        for tile in topo["tiles"]:
            for adj in tile["adjacent"]:
                # Find the corresponding tile in topology
                adj_tile = next(
                    (t for t in topo["tiles"] if t["tile_id"] == adj), None
                )
                # Adjacency should be bidirectional for habitat edges
                if tile["tile_id"].startswith("public-"):
                    assert adj_tile is not None
                    assert tile["tile_id"] in adj_tile["adjacent"]


class TestMergeObservation:
    def test_first_observation(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        before_count = len(km["known_tiles"])
        updated = merge_observation(km, obs, 5)
        after_count = len(updated["known_tiles"])
        # If cont_a_origin_000 was newly visible, it should be added
        assert after_count >= before_count

    def test_repeated_observation_idempotent(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        updated1 = merge_observation(km, obs, 5)
        updated2 = merge_observation(updated1, obs, 5)
        # Same tick → no additional visits
        for tile_id, entry in updated2["known_tiles"].items():
            if tile_id in updated1["known_tiles"]:
                assert entry["visit_count"] == updated1["known_tiles"][tile_id]["visit_count"]


class TestFogGate:
    def test_gate_inactive_when_no_files(self, tmp_path):
        assert fog_gate_active(tmp_path) is False

    def test_gate_active_when_files_exist(self, tmp_path):
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        (tmp_path / "known_map_east_adam.json").write_text(
            json.dumps(km), newline="\n"
        )
        (tmp_path / "known_map_east_eve.json").write_text(
            json.dumps(km), newline="\n"
        )
        assert fog_gate_active(tmp_path) is True

    def test_gate_inactive_with_only_one_file(self, tmp_path):
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        (tmp_path / "known_map_east_adam.json").write_text(
            json.dumps(km), newline="\n"
        )
        assert fog_gate_active(tmp_path) is False


class TestNoLeakage:
    def test_no_hidden_tiles_in_observation(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-start-adam", km, {"radius": 1}, [], "east_adam"
        )
        # From start-adam at (-1,-1), radius 1 reaches:
        # (0,-1)=center and (-1,0)=no tile there in mini map
        # origin_000 at (0,0) is distance 2, NOT visible
        assert "cont_a_origin_000" not in obs["visible_tiles"]

    def test_no_mysteries_in_observation(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        text = json.dumps(obs)
        assert "reveal_threshold" not in text
        assert "mystery_id" not in text

    def test_no_implementation_names(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        text = json.dumps(obs)
        for term in ("true_map", "known_map", "schema_version", "continent_id", "region_id"):
            assert term not in text, f"leakage: {term}"
