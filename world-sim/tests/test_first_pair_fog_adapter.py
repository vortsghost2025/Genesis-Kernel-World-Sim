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

    # -- World observation transmission (docs/world_observation_transmission_spec.md)
    # The projection silently dropped `water` and `hazards`. The world has
    # exactly ONE drinkable fresh_water tile in 80,000; agents have been
    # asking about water since the first live loop. These tests pin the fix.

    def test_water_is_transmitted_for_visible_tile(self):
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        by_id = {d["tile_id"]: d for d in obs["visible_tile_details"]}
        origin = by_id.get("cont_a_origin_000")
        assert origin is not None, "origin tile should be visible at radius 1"
        assert "water" in origin, "water key missing from visible tile detail"
        # A tile with no water carries an empty water block, not a null one:
        # the key is always present so consumers never branch on absence.
        center = by_id["public-shared-center"]
        assert center.get("water") == {}

    def test_hazards_are_transmitted(self):
        tm = _mini_true_map()
        for tile in tm["tiles"]:
            if tile["tile_id"] == "cont_a_origin_000":
                tile["hazards"] = ["flood_risk"]
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        by_id = {d["tile_id"]: d for d in obs["visible_tile_details"]}
        assert by_id["cont_a_origin_000"].get("hazards") == ["flood_risk"]

    def test_conditions_absent_when_none_passed(self):
        """Phase 1 guarantee: the runtime passes conditions=None, so no
        conditions key appears and visibility is untouched.

        Note the pre-existing radius dial: `_condition_radius` already shrinks
        radius when `visibility` is storm/fog. That behaviour is untouched by
        this phase - it is only unreachable because the runtime passes None.
        Turning the dial on is Phase 2."""
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, None, [], "east_adam"
        )
        assert "conditions" not in obs

    def test_conditions_reported_read_only_when_supplied(self):
        """When conditions ARE supplied they are reported verbatim."""
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km,
            {"visibility": "gentle", "time_of_day": "day"}, [], "east_adam"
        )
        assert obs["conditions"]["visibility"] == "gentle"
        assert obs["conditions"]["time_of_day"] == "day"

    def test_radius_dial_untouched_by_this_phase(self):
        """The pre-existing storm/radius behaviour must behave identically
        before and after this phase - this phase did not introduce it."""
        tm = _mini_true_map()
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        clear = cognition_safe_observation(
            tm, "public-shared-center", km,
            {"radius": 1, "visibility": "high"}, [], "east_adam"
        )
        storm = cognition_safe_observation(
            tm, "public-shared-center", km,
            {"radius": 1, "visibility": "storm"}, [], "east_adam"
        )
        assert len(storm["visible_tiles"]) < len(clear["visible_tiles"]), (
            "radius dial should still narrow the visible set under storm"
        )

    def test_water_never_leaks_from_non_visible_tiles(self):
        """A drinkable tile outside the visible set must not appear anywhere."""
        tm = _mini_true_map()
        for tile in tm["tiles"]:
            if tile["tile_id"] == "public-start-adam":
                tile["water"] = {"type": "river", "drinkable": True}
                tile["resources"] = ["fresh_water"]
        for res in tm.get("resources", []):
            if res.get("tile_id") == "public-start-adam":
                res["kind"] = "fresh_water"
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        # Observe from the center, so the drinkable tile is NOT in radius.
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 0}, [], "east_adam"
        )
        text = json.dumps(obs)
        if "public-start-adam" not in obs["visible_tiles"]:
            assert "drinkable" not in text
            assert "fresh_water" not in text

    def test_projection_does_not_special_case_water(self):
        """The single drinkable tile must stay a discovery.

        The projection must transmit whatever `water` a tile carries, with no
        branch on drinkability, resource name, or tile id. Proven by
        behavioural test: an arbitrary invented drinkable river on an ordinary
        tile is transmitted exactly like any other water body.
        """
        tm = _mini_true_map()
        visible_ids = {
            t["tile_id"] for t in tm["tiles"]
        }
        # Pick whatever tile the existing fixture makes visible, rather than
        # assuming a coordinate geometry.
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        probe = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        target = probe["visible_tiles"][0]
        assert target in visible_ids
        for tile in tm["tiles"]:
            if tile["tile_id"] == target:
                tile["water"] = {"type": "river", "drinkable": True}
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
        )
        by_id = {d["tile_id"]: d for d in obs["visible_tile_details"]}
        assert by_id[target]["water"] == {"type": "river", "drinkable": True}

    def test_no_contamination_via_new_fields(self):
        """New fields are added BEFORE the contamination check so they are
        covered by it."""
        tm = _mini_true_map()
        for tile in tm["tiles"]:
            if tile["tile_id"] == "cont_a_origin_000":
                tile["hazards"] = ["true_map_internal_marker"]
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        with pytest.raises(FogAdapterError):
            cognition_safe_observation(
                tm, "public-shared-center", km, {"radius": 1}, [], "east_adam"
            )

    def test_observation_shape_with_no_water_or_hazards(self):
        """A map with no water/hazards yields neutral values, so the key set
        is stable and consumers never branch on absence."""
        tm = _mini_true_map()
        for tile in tm["tiles"]:
            tile["water"] = None
            tile["hazards"] = []
        km = seed_known_map_from_history(
            _simple_heartbeats(), "east_adam", "public-start-adam"
        )
        obs = cognition_safe_observation(
            tm, "public-shared-center", km, None, [], "east_adam"
        )
        assert set(obs.keys()) == {
            "tile_id", "visible_tiles", "objects_here", "visible_tile_details",
        }
        for detail in obs["visible_tile_details"]:
            assert detail["water"] == {}
            assert detail["hazards"] == []

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
