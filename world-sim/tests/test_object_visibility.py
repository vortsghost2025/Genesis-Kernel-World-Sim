"""A standing thing is visible farther than flat ground.

`docs/object_visibility_spec.md`. An object on a tile makes that tile
visible from Chebyshev distance 2 instead of the normal radius-1
Manhattan disc. The rule is type-blind: any public object standing in
the world is a landmark, which is the same physics the wall unlock
already uses (a raft by deep water is visible; it does not matter what
else it is).

This gives every object the agents have ever built a reason to exist:
a cairn on a hill extends your knowledge; a container at a crossroads
tells you someone was here. It also makes building *near* someone the
first socially legible act - a shared object extends both sightlines.
"""
from __future__ import annotations

import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import build_local_observation  # noqa: E402


def _tile(tid, x, y, terrain="hill", biome="highland", blocked=False):
    return {
        "tile_id": tid, "coordinates": {"x": x, "y": y},
        "continent_id": "cont_a", "region_id": "r1",
        "terrain": terrain, "biome": biome,
        "blocks_travel": blocked, "hazards": [],
        "resources": [], "water": {}, "landmark_ids": [],
    }


def _map():
    tiles = [_tile(f"t_{x}_{y}", x, y) for x in range(-4, 5) for y in range(-4, 5)]
    return {"tiles": tiles, "landmarks": []}


def _pos():
    return {"coordinates": {"x": 0, "y": 0}, "agent_id": "test",
            "active": True, "continent_id": "cont_a"}


def _known(tm):
    return {"known_tiles": {t["tile_id"]: {} for t in tm["tiles"]}}


def _obs(tm, objects=None):
    return build_local_observation(tm, _pos(), _known(tm), None,
                                    public_objects=objects)


class TestObjectExtendsSight:
    def test_object_tile_at_distance_2_becomes_visible(self):
        """A tile with an object on it is visible from Chebyshev distance
        2, not just the normal radius-1 Manhattan disc."""
        tm = _map()
        objs = [{"object_id": "o1", "object_type": "cairn",
                 "tile_id": "t_2_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_2_0" in obs.get("visible_tile_ids", []), (
            "object tile at distance 2 must be visible")

    def test_object_tile_at_distance_1_stays_visible(self):
        tm = _map()
        objs = [{"object_id": "o1", "object_type": "cairn",
                 "tile_id": "t_1_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_1_0" in obs.get("visible_tile_ids", [])

    def test_no_object_means_normal_visibility_only(self):
        """Without objects, distance-2 tiles are NOT visible. The rule
        extends sight for standing things, not for free."""
        tm = _map()
        obs = _obs(tm, objects=None)
        assert "t_2_0" not in obs.get("visible_tile_ids", [])
        assert "t_1_0" in obs.get("visible_tile_ids", [])

    def test_object_at_chebyshev_3_is_not_visible(self):
        """Distance 3 is beyond the extended range."""
        tm = _map()
        objs = [{"object_id": "o1", "object_type": "cairn",
                 "tile_id": "t_3_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_3_0" not in obs.get("visible_tile_ids", [])

    def test_diagonal_object_at_chebyshev_2_is_visible(self):
        """An object at (2,2) is visible from (0,0). Chebyshev covers
        diagonals; Manhattan does not."""
        tm = _map()
        objs = [{"object_id": "o1", "object_type": "landmark",
                 "tile_id": "t_2_2", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_2_2" in obs.get("visible_tile_ids", [])

    def test_extended_tile_carries_full_details(self):
        """The object tile is not a ghost entry - it carries terrain,
        biome, resources, the same as any visible tile."""
        tm = _map()
        for t in tm["tiles"]:
            if t["tile_id"] == "t_2_0":
                t["resources"] = ["stone"]
                t["terrain"] = "mountain"
        objs = [{"object_id": "o1", "object_type": "cairn",
                 "tile_id": "t_2_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        details = {d["tile_id"]: d for d in obs.get("visible_tiles", [])}
        assert "t_2_0" in details, "object tile must appear in visible_tiles"
        assert details["t_2_0"]["terrain"] == "mountain"
        assert "stone" in details["t_2_0"]["resources"]

    def test_object_on_wrong_continent_is_not_visible(self):
        """The extended sightline does not cross continents."""
        tm = _map()
        for t in tm["tiles"]:
            if t["tile_id"] == "t_2_0":
                t["continent_id"] = "cont_b"
        objs = [{"object_id": "o1", "object_type": "cairn",
                 "tile_id": "t_2_0", "creator_agent_id": "a",
                 "public_description": "x", "created_heartbeat": 1}]
        obs = _obs(tm, objs)
        assert "t_2_0" not in obs.get("visible_tile_ids", [])
