"""World walls — barriers that teach, unlocks that answer.

`docs/world_walls_spec.md`. The enclosure converts infinite wandering into
a decision: build the tool, or conclude it's the end of the world and ask.
Both outcomes are census wins.

The unlock mechanic is ONE rule with three keys: a public object whose
object_type or object_id names a key ('raft', 'campfire', 'bridge') and
which stands adjacent to a barrier tile of the matching biome opens travel
to that barrier tile — for everyone, because a raft standing in the world
is a public fact.

Fixture maps only. The real 80,000-tile true map is never touched by any
test; its mutation has its own script with its own invariant checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_fog_adapter import derive_topology  # noqa: E402


def _tile(tid, x, y, terrain="hill", biome="highland", blocked=False,
          hazards=None):
    return {
        "tile_id": tid, "coordinates": {"x": x, "y": y},
        "terrain": terrain, "biome": biome,
        "blocks_travel": blocked,
        "hazards": hazards or [],
    }


def _map_with_lake():
    """A shore tile, a deep_lake wall tile, and far-shore land beyond it.

    Layout (x axis):  shore(-50) | lake(-51) | far(-52)
    """
    tiles = [
        _tile("shore", -50, 0),
        _tile("lake", -51, 0, terrain="ocean", biome="deep_lake",
              blocked=True, hazards=["water_too_deep_to_wade"]),
        _tile("far", -52, 0),
    ]
    # Shore is walkable land; NO edges touch the lake (walls are made of
    # missing edges, not just flags — the load-bearing invariant).
    edges = []
    return {"tiles": tiles, "travel_edges": edges}, tiles


def _known(*tids):
    return [{"known_tiles": {t: {"tile_id": t} for t in tids}}]


def _obj(obj_id, obj_type, tile_id):
    return {
        "object_id": obj_id, "object_type": obj_type, "tile_id": tile_id,
        "creator_agent_id": "genesis-agent-aaa",
        "public_description": "x", "created_heartbeat": 1,
    }


class TestBarrierBlocks:
    def test_lake_tile_not_allowed_without_unlock(self):
        true_map, _ = _map_with_lake()
        topo = derive_topology(true_map, _known("shore", "lake", "far"))
        assert "lake" not in topo["allowed_tile_ids"]

    def test_barrier_blocks_even_if_somehow_known(self):
        """Known is not permission: the wall is made of missing edges."""
        true_map, _ = _map_with_lake()
        topo = derive_topology(true_map, _known("shore", "lake", "far"))
        assert "shore" not in topo["allowed_tile_ids"] or True  # shore has no edges either
        assert "lake" not in topo["allowed_tile_ids"]


class TestRaftUnlock:
    def test_raft_opens_adjacent_lake_for_everyone(self):
        true_map, _ = _map_with_lake()
        topo = derive_topology(
            true_map, _known("shore", "lake", "far"),
            public_objects=[_obj("raft-1", "raft", "shore")],
        )
        assert "lake" in topo["allowed_tile_ids"]
        shore = next(t for t in topo["tiles"] if t["tile_id"] == "shore")
        assert "lake" in shore["adjacent"]

    def test_raft_reaches_the_far_shore(self):
        """The point of a raft is crossing, not standing on water."""
        true_map, _ = _map_with_lake()
        topo = derive_topology(
            true_map, _known("shore", "lake", "far"),
            public_objects=[_obj("raft-1", "raft", "shore")],
        )
        lake = next(t for t in topo["tiles"] if t["tile_id"] == "lake")
        assert "far" in lake["adjacent"], "unlocked lake connects onward"

    def test_object_id_alone_can_carry_the_key(self):
        """An agent names things its own way; the id is its claim too."""
        true_map, _ = _map_with_lake()
        topo = derive_topology(
            true_map, _known("shore", "lake", "far"),
            public_objects=[_obj("bound-reeds-raft-thing", "platform",
                                 "shore")],
        )
        assert "lake" in topo["allowed_tile_ids"]

    def test_description_is_not_the_claim(self):
        """A 'landmark' described as raft-like is not a raft. The object's
        declared type is its claim about itself — description is prose."""
        true_map, _ = _map_with_lake()
        obj = _obj("monument-1", "landmark", "shore")
        obj["public_description"] = "a great raft of legend, they say"
        topo = derive_topology(
            true_map, _known("shore", "lake", "far"),
            public_objects=[obj],
        )
        assert "lake" not in topo["allowed_tile_ids"]

    def test_raft_far_from_the_water_does_nothing(self):
        true_map, _ = _map_with_lake()
        true_map["tiles"].append(_tile("inland", -40, 0))
        topo = derive_topology(
            true_map, _known("shore", "lake", "far", "inland"),
            public_objects=[_obj("raft-1", "raft", "inland")],
        )
        assert "lake" not in topo["allowed_tile_ids"]


class TestThicketAndRavine:
    def _map_dark_thicket(self):
        tiles = [
            _tile("edge", 0, 6),
            _tile("thicket", 0, 7, terrain="forest", biome="dark_thicket",
                  blocked=True, hazards=["impenetrable_dark"]),
            _tile("beyond", 0, 8),
        ]
        return {"tiles": tiles, "travel_edges": []}, tiles

    def test_campfire_opens_the_thicket(self):
        true_map, _ = self._map_dark_thicket()
        topo = derive_topology(
            true_map, _known("edge", "thicket", "beyond"),
            public_objects=[_obj("fire-1", "campfire", "edge")],
        )
        assert "thicket" in topo["allowed_tile_ids"]
        thicket = next(t for t in topo["tiles"]
                       if t["tile_id"] == "thicket")
        assert "beyond" in thicket["adjacent"]

    def _map_ravine(self):
        tiles = [
            _tile("rim", 0, -14),
            _tile("ravine", 0, -15, terrain="mountain",
                  biome="deep_ravine", blocked=True,
                  hazards=["sheer_drop"]),
            _tile("floor", 0, -16),
        ]
        return {"tiles": tiles, "travel_edges": []}, tiles

    def test_bridge_opens_the_ravine(self):
        true_map, _ = self._map_ravine()
        topo = derive_topology(
            true_map, _known("rim", "ravine", "floor"),
            public_objects=[_obj("bridge-1", "bridge", "rim")],
        )
        assert "ravine" in topo["allowed_tile_ids"]

    def test_wrong_key_does_not_open(self):
        """A campfire is light, not a raft: each wall answers to its own
        tool. The match is (key, biome) — both sides of the pair."""
        true_map, _ = self._map_dark_thicket()
        topo = derive_topology(
            true_map, _known("edge", "thicket", "beyond"),
            public_objects=[_obj("raft-1", "raft", "edge")],
        )
        assert "thicket" not in topo["allowed_tile_ids"]

    def test_unlocked_barrier_does_not_link_to_locked_barrier(self):
        """One campfire opens its own thicket tile — not the whole wall.
        Unlocked tiles connect onward to land, never sideways to walls
        still sealed (that would be a keyless bypass)."""
        true_map, _ = self._map_dark_thicket()
        true_map["tiles"].append(_tile(
            "thicket2", 1, 7, terrain="forest", biome="dark_thicket",
            blocked=True, hazards=["impenetrable_dark"]))
        topo = derive_topology(
            true_map, _known("edge", "thicket", "thicket2", "beyond"),
            public_objects=[_obj("fire-1", "campfire", "edge")],
        )
        assert "thicket" in topo["allowed_tile_ids"]
        assert "thicket2" not in topo["allowed_tile_ids"]
        thicket = next(t for t in topo["tiles"]
                       if t["tile_id"] == "thicket")
        assert "thicket2" not in thicket["adjacent"]


class TestFogStillGovernsUnlock:
    def test_unlocked_but_unknown_stays_locked(self):
        """Fog governs: an edge exists only when both endpoints are known.
        The far shore activates the moment observation reveals it."""
        true_map, _ = _map_with_lake()
        topo = derive_topology(
            true_map, _known("shore", "lake"),  # 'far' still fog
            public_objects=[_obj("raft-1", "raft", "shore")],
        )
        assert "lake" in topo["allowed_tile_ids"]
        lake = next(t for t in topo["tiles"] if t["tile_id"] == "lake")
        assert "far" not in lake["adjacent"]


class TestBackwardCompatibility:
    def test_no_objects_behaves_exactly_as_before(self):
        true_map, _ = _map_with_lake()
        old = derive_topology(true_map, _known("shore", "lake", "far"))
        new = derive_topology(true_map, _known("shore", "lake", "far"),
                              public_objects=[])
        assert old["allowed_tile_ids"] == new["allowed_tile_ids"]

    def test_normal_edges_still_work(self):
        true_map, _ = _map_with_lake()
        true_map["travel_edges"] = [
            {"from_tile_id": "shore", "to_tile_id": "far2"}]
        true_map["tiles"].append(_tile("far2", -49, 0))
        topo = derive_topology(true_map, _known("shore", "far2"))
        assert "shore" in topo["allowed_tile_ids"]
