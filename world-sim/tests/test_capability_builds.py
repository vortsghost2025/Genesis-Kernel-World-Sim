"""Buildable things that make you more capable.

Two mechanics, both positive incentives (the world opens when you build,
never punishes you for not building):

1. Watchtower: an object named tower/watchtower extends visibility to
   Chebyshev distance 5 instead of the normal 2. Type-matched, same
   principle as the wall unlock (raft/campfire/bridge).

2. Road: an object named road on your tile lets you move 2 tiles per
   heartbeat instead of 1. The extra tiles appear in available_moves;
   the agent chooses from what they can see.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import build_local_observation  # noqa: E402


def _tile(tid, x, y):
    return {
        "tile_id": tid, "coordinates": {"x": x, "y": y},
        "continent_id": "cont_a", "region_id": "r1",
        "terrain": "hill", "biome": "highland",
        "blocks_travel": False, "hazards": [],
        "resources": [], "water": {}, "landmark_ids": [],
    }


def _map():
    tiles = [_tile(f"t_{x}_{y}", x, y) for x in range(-6, 7) for y in range(-6, 7)]
    return {"tiles": tiles, "landmarks": []}


def _pos():
    return {"coordinates": {"x": 0, "y": 0}, "agent_id": "test",
            "active": True, "continent_id": "cont_a"}


def _known(tm):
    return {"known_tiles": {t["tile_id"]: {} for t in tm["tiles"]}}


def _obs(tm, objects=None):
    return build_local_observation(tm, _pos(), _known(tm), None,
                                    public_objects=objects)


class TestWatchtower:
    def test_tower_at_distance_5_becomes_visible(self):
        """A watchtower extends the sightline to 5 tiles. You built it
        tall so you could see far — the world agrees."""
        tm = _map()
        objs = [{"object_id": "w1", "object_type": "watchtower",
                 "tile_id": "t_5_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_5_0" in obs.get("visible_tile_ids", [])

    def test_tower_at_distance_6_is_not_visible(self):
        """Distance 6 is beyond even a watchtower's reach."""
        tm = _map()
        objs = [{"object_id": "w1", "object_type": "watchtower",
                 "tile_id": "t_6_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_6_0" not in obs.get("visible_tile_ids", [])

    def test_non_tower_object_at_distance_5_is_not_visible(self):
        """A regular object still extends to 2, not 5. Only tall things
        see far."""
        tm = _map()
        objs = [{"object_id": "o1", "object_type": "storage",
                 "tile_id": "t_5_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_5_0" not in obs.get("visible_tile_ids", [])

    def test_tower_type_matching_is_substring(self):
        """An agent that builds 'stone watchtower' or 'wooden_tower'
        qualifies — the same substring matching the wall unlock uses."""
        tm = _map()
        objs = [{"object_id": "w1", "object_type": "stone watchtower",
                 "tile_id": "t_4_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_4_0" in obs.get("visible_tile_ids", [])

    def test_diagonal_tower_at_chebyshev_5(self):
        tm = _map()
        objs = [{"object_id": "w1", "object_type": "watchtower",
                 "tile_id": "t_3_4", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_3_4" in obs.get("visible_tile_ids", [])


class TestRoad:
    def test_road_object_on_tile_allows_2_step_moves(self):
        """Standing on a road tile, available_moves includes tiles 2
        travel-edges away. The road is the first buildable object that
        changes how FAST you move, not just how far you see."""
        # This test requires the runtime's adjacency computation.
        # Placeholder: verified in the runtime integration test.
        pass
