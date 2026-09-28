"""Known-map merge ordering: an observed tile must be reachable this heartbeat.

Heartbeat 942 gave the defect away: east_adam saw `cont_a_gen_1_2` in his
observation, correctly chose to walk there, and was blocked with
"not in runtime policy allowed tiles" - because the known-map merge happened
AFTER the action, so the reachability rule consulted a map that did not yet
contain the tile the agent had just been shown.

See docs/known_map_merge_order_spec.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import backend.world.first_pair_runtime as rt_mod
from backend.world.first_pair_fog_adapter import (
    derive_topology,
    load_known_map,
    merge_observation,
)

WORLD_SIM = Path(__file__).resolve().parents[1]


def _mini_true_map() -> dict:
    """Two-tile chain reachable from the historical habitat seed tile."""
    return {
        "schema_version": "7B.1",
        "world_id": "t",
        "seed": "s",
        "continents": [{"continent_id": "cont_a", "name": "A"}],
        "regions": [
            {"region_id": "r1", "continent_id": "cont_a", "name": "R1"},
            {"region_id": "r2", "continent_id": "cont_a", "name": "R2"},
        ],
        "tiles": [
            {
                "tile_id": "public-shared-center",
                "continent_id": "cont_a",
                "region_id": "r1",
                "coordinates": {"x": 0, "y": 0},
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
                "tile_id": "newly_seen",
                "continent_id": "cont_a",
                "region_id": "r2",
                "coordinates": {"x": 1, "y": 0},
                "terrain": "hill",
                "biome": "temperate_hills",
                "elevation": 0.5,
                "water": None,
                "resources": ["stone"],
                "hazards": [],
                "landmark_ids": [],
                "blocks_travel": False,
            },
        ],
        "travel_edges": [
            {
                "from_tile_id": "public-shared-center",
                "to_tile_id": "newly_seen",
                "edge_id": "e1",
            }
        ],
        "landmarks": [],
        "resources": [],
        "hazards": [],
        "mysteries": [],
    }


def _empty_known_map(agent_ref: str) -> dict:
    from backend.world.fog_of_war import create_empty_known_map
    return create_empty_known_map(agent_ref)


def _known_tile(tick: int) -> dict:
    """A known-map tile entry in the shape the merge actually maintains."""
    return {
        "tile_id": "public-shared-center",
        "first_observed_tick": tick,
        "last_observed_tick": tick,
        "visit_count": 1,
        "confidence": 1.0,
        "observed_terrain": "grassland",
        "observed_biome": "temperate",
        "observed_resources": [],
        "observed_hazards": [],
        "notes": [],
        "agent_given_name": None,
    }


OBSERVATION_SEEN = {
    "tile_id": "public-shared-center",
    "visible_tiles": ["public-shared-center", "newly_seen"],
    "visible_tile_details": [
        {"tile_id": "public-shared-center", "terrain": "grassland"},
        {"tile_id": "newly_seen", "terrain": "hill"},
    ],
    "objects_here": [],
}


class TestTheDefect:
    """The pre-fix ordering, reproduced, so the regression cannot return."""

    def test_tile_observed_this_tick_is_absent_from_allowed_set(self):
        """Before the merge, a just-observed tile is NOT reachable. This is
        the defect; the test exists to document it, not to endorse it."""
        tm = _mini_true_map()
        km = _empty_known_map("east_adam")
        km["known_tiles"] = {"public-shared-center": _known_tile(1)}
        pre = derive_topology(tm, [km])
        assert "newly_seen" in OBSERVATION_SEEN["visible_tiles"]
        assert "newly_seen" not in pre["allowed_tile_ids"], (
            "pre-merge the just-seen tile is unreachable - this is the defect"
        )

    def test_after_merge_the_same_tile_is_reachable(self):
        tm = _mini_true_map()
        km = _empty_known_map("east_adam")
        km["known_tiles"] = {"public-shared-center": _known_tile(1)}
        merged = merge_observation(km, OBSERVATION_SEEN, 2)
        post = derive_topology(tm, [merged])
        assert "newly_seen" in post["allowed_tile_ids"]


class TestMergeIsIdempotentAndSafe:
    def test_merge_is_idempotent(self):
        km = _empty_known_map("east_adam")
        once = merge_observation(km, OBSERVATION_SEEN, 2)
        twice = merge_observation(once, OBSERVATION_SEEN, 3)
        assert set(once["known_tiles"]) == set(twice["known_tiles"])
        assert (
            twice["known_tiles"]["newly_seen"]["first_observed_tick"]
            == once["known_tiles"]["newly_seen"]["first_observed_tick"]
        ), "re-observing must not restamp first-seen"

    def test_merge_does_not_grant_capability_or_movement(self):
        km = _empty_known_map("east_adam")
        merged = merge_observation(km, OBSERVATION_SEEN, 2)
        text = json.dumps(merged).lower()
        for forbidden in ("capability", "movement_allowed", "runtime_policy"):
            assert forbidden not in text

    def test_merge_writes_only_the_agents_own_known_map(self, tmp_path):
        from backend.world.first_pair_fog_adapter import persist_known_map
        store = tmp_path / "store"
        store.mkdir()
        km = merge_observation(_empty_known_map("east_adam"), OBSERVATION_SEEN, 2)
        persist_known_map(store, "east_adam", km)
        written = json.loads(
            (store / "known_map_east_adam.json").read_text(encoding="utf-8")
        )
        assert "newly_seen" in written["known_tiles"]
        assert not (store / "world_state.json").exists(), (
            "merging a known map must not create or touch world state"
        )


class TestDegradedObservationDoesNotMerge:
    def test_fog_error_observation_is_not_a_merge_source(self):
        """A fail-closed observation carries only the agent's own tile; it
        cannot smuggle new known territory."""
        degraded = {
            "tile_id": "public-shared-center",
            "visible_tiles": ["public-shared-center"],
            "objects_here": [],
            "fog_error": "geography observation unavailable",
        }
        km = merge_observation(_empty_known_map("east_adam"), degraded, 2)
        assert set(km["known_tiles"]) <= {"public-shared-center"}
        assert "newly_seen" not in km["known_tiles"]


class TestOrderingIsEnforcedInSource:
    """Static guard: the merge call must precede the action call.

    A source-order assertion is deliberate here. The behavioural tests above
    prove the merge *can* happen before acting; this one proves the runtime
    actually *does* it, which is the whole defect.
    """

    def test_merge_precedes_action_in_the_heartbeat_loop(self):
        source = (WORLD_SIM / "backend" / "world"
                  / "first_pair_runtime.py").read_text(encoding="utf-8")
        loop_start = source.index("hb_observations: dict = {}")
        window = source[loop_start:loop_start + 6000]
        act_at = window.index("_execute_action(")
        merge_at = window.index("_merge_and_persist_known_map(")
        assert merge_at < act_at, (
            "known-map merge must occur before _execute_action so a tile "
            "observed this heartbeat is reachable this heartbeat"
        )
