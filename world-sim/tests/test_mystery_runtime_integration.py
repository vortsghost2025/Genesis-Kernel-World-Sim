"""Mystery runtime integration — occupancy-based reveals, live in the heartbeat.

Implements docs/mystery_runtime_integration_spec.md:
- accrual + reveal at the observation-build seam (same-tick hint visibility)
- occupancy-only evidence, per-agent, fail-closed
- hints via observation key 'unsettled_reports', reveals via 'discoveries'
- no-leak: agent-facing observation carries no mystery ids/thresholds
- revealed state survives the post-action known-map merge
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.world.first_pair_persistence import FirstPairPersistenceStore
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.mystery_reveal import (
    apply_reveal,
    accrue_mystery_evidence,
    project_discoveries,
    project_unsettled_reports,
)
from backend.world.first_pair_fog_adapter import (
    create_empty_known_map,
    load_known_map,
    merge_observation,
    persist_known_map,
)

WORLD_SIM = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MYSTERY_TILE = "mystery-tile"
NEIGHBOR_TILE = "neighbor-tile"


def _mini_true_map() -> dict:
    return {
        "schema_version": "7B.1",
        "world_id": "test-world",
        "seed": 42,
        "continents": [{"continent_id": "cont_a", "name": "Test Continent"}],
        "regions": [
            {"region_id": "r_summit", "continent_id": "cont_a", "name": "East Crown"},
        ],
        "tiles": [
            {
                "tile_id": MYSTERY_TILE,
                "continent_id": "cont_a",
                "region_id": "r_summit",
                "terrain": "mountain",
                "biome": "alpine",
                "coordinates": {"x": 3, "y": 0},
                "resources": [],
                "hazards": [],
                "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": NEIGHBOR_TILE,
                "continent_id": "cont_a",
                "region_id": "r_summit",
                "terrain": "hill",
                "biome": "highland",
                "coordinates": {"x": 3, "y": 1},
                "resources": [],
                "hazards": [],
                "landmark_ids": [],
                "blocks_travel": False,
            },
        ],
        "landmarks": [],
        "resources": [],
        "hazards": [],
        "mysteries": [
            {
                "mystery_id": "mst_test_echo",
                "tile_id": MYSTERY_TILE,
                "kind": "repeating_sound",
                "reveal_threshold": 3,
            },
        ],
        "travel_edges": [[MYSTERY_TILE, NEIGHBOR_TILE]],
    }


def _fresh_store(tmp_path: Path) -> FirstPairPersistenceStore:
    return FirstPairPersistenceStore(tmp_path / ".runtime" / "first-pair")


def _fog_runtime(tmp_path: Path, monkeypatch) -> FirstPairRuntime:
    """Runtime with fog active: known-map files present + mini true map."""
    store = _fresh_store(tmp_path)
    data_root = tmp_path / "data"
    (data_root / "world").mkdir(parents=True)
    (data_root / "world" / "true_map.json").write_text(
        json.dumps(_mini_true_map()), encoding="utf-8", newline="\n"
    )
    for ref in ("east_adam", "east_eve"):
        persist_known_map(store.root, ref, create_empty_known_map(ref))
    monkeypatch.setattr(FirstPairRuntime, "_get_data_root", lambda self: data_root)
    rt = FirstPairRuntime(heartbeat_limit=1, store=store)
    rt.run()  # initialize identity/world state via one stub heartbeat
    assert rt._fog_active(), "fog gate must be active for the mystery seam"
    return rt


def _known(rt: FirstPairRuntime, ref: str) -> dict:
    return load_known_map(rt._store.root, ref)


# ---------------------------------------------------------------------------
# Runtime mystery step (accrual + reveal at the seam)
# ---------------------------------------------------------------------------


class TestMysteryStep:
    def test_accrues_on_occupancy_and_persists(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        km_before = json.dumps(_known(rt, "east_adam"), sort_keys=True)
        km = rt._mystery_step(_known(rt, "east_adam"), MYSTERY_TILE, "east_adam", 101)
        rec = km["myths"][0]
        assert rec["evidence"] == 1
        assert rec["status"] == "gathering"
        # persisted
        persisted = _known(rt, "east_adam")
        assert persisted["myths"][0]["evidence"] == 1
        assert json.dumps(km_before, sort_keys=True) != json.dumps(persisted, sort_keys=True)

    def test_no_accrual_off_tile(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        km = rt._mystery_step(_known(rt, "east_adam"), NEIGHBOR_TILE, "east_adam", 101)
        assert km.get("myths", []) == []
        # nothing persisted: store content unchanged
        assert _known(rt, "east_adam").get("myths", []) == []

    def test_full_ladder_same_tick_visibility(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        # tick 1: first hint visible in the same heartbeat's observation
        obs1 = rt._get_fog_observation("east_adam", MYSTERY_TILE, [], heartbeat_number=101)
        assert obs1.get("unsettled_reports")
        assert "wind drops" in obs1["unsettled_reports"][0]["report"]
        assert "discoveries" not in obs1
        # tick 2: deeper hint
        obs2 = rt._get_fog_observation("east_adam", MYSTERY_TILE, [], heartbeat_number=102)
        assert "Steady as a heartbeat" in obs2["unsettled_reports"][0]["report"]
        assert "discoveries" not in obs2
        # tick 3: reveal — hint channel empties (key absent, per spec), discovery appears same tick
        obs3 = rt._get_fog_observation("east_adam", MYSTERY_TILE, [], heartbeat_number=103)
        assert "unsettled_reports" not in obs3
        assert obs3.get("discoveries")
        assert "Singing Stone" in obs3["discoveries"][0]["name_and_description"]

    def test_per_agent_independence(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        rt._mystery_step(_known(rt, "east_adam"), MYSTERY_TILE, "east_adam", 101)
        eve_km = _known(rt, "east_eve")
        assert eve_km.get("myths", []) == []

    def test_fail_closed_on_malformed_mystery(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        bad_map = _mini_true_map()
        bad_map["mysteries"] = [{"mystery_id": "mst_bad", "tile_id": MYSTERY_TILE}]
        before = _known(rt, "east_adam")
        km = rt._mystery_step(before, MYSTERY_TILE, "east_adam", 101, true_map=bad_map)
        assert km.get("myths", []) == []

    def test_revealed_state_survives_post_action_merge(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        # stand on the tile three times (accrue to reveal)
        km = _known(rt, "east_adam")
        for tick in (101, 102, 103):
            km, _ = accrue_mystery_evidence(km, _mini_true_map()["mysteries"][0],
                                            {"tile_id": MYSTERY_TILE}, tick)
            km, revealed = apply_reveal(km, _mini_true_map()["mysteries"][0], tick)
        assert revealed is not None
        persist_known_map(rt._store.root, "east_adam", km)
        # post-action merge (as the heartbeat does after acting) must keep it
        obs = rt._get_fog_observation("east_adam", NEIGHBOR_TILE, [], heartbeat_number=103)
        merged = merge_observation(_known(rt, "east_adam"), obs, 103)
        assert merged["myths"][0]["status"] == "confirmed"
        assert "lm_mystery_mst_test_echo" in merged["known_landmarks"]

    def test_no_new_keys_without_evidence(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        obs = rt._get_fog_observation("east_adam", NEIGHBOR_TILE, [], heartbeat_number=101)
        assert "unsettled_reports" not in obs
        assert "discoveries" not in obs

    def test_no_leak_in_observation(self, tmp_path, monkeypatch):
        rt = _fog_runtime(tmp_path, monkeypatch)
        for tick in (101, 102, 103):
            obs = rt._get_fog_observation(
                "east_adam", MYSTERY_TILE, [], heartbeat_number=tick
            )
        # spec §3.2: the hint/discovery channels must carry no mechanism
        # words, no ids, no coordinates — ids may appear only in the normal
        # tile-detail channel, never inside hints or discoveries
        channels = obs.get("unsettled_reports", []) + obs.get("discoveries", [])
        blob = json.dumps(channels).lower()
        for forbidden in (
            "mst_", "threshold", "mystery", "true_map", "known_map",
            "mystery-tile", "cont_a", "r_summit", "landmark_id",
        ):
            assert forbidden not in blob, f"leak: {forbidden}"


# ---------------------------------------------------------------------------
# Projections (pure module additions)
# ---------------------------------------------------------------------------


class TestProjections:
    def test_project_discoveries_excludes_normal_landmarks(self):
        km = create_empty_known_map("east_adam")
        km["known_landmarks"]["lm_mystery_mst_x"] = {
            "kind": "singing_rock",
            "description": "The Singing Stone. It hums.",
        }
        km["known_landmarks"]["lm_normal"] = {
            "kind": "river",
            "description": "A river.",
        }
        d = project_discoveries(km)
        assert len(d) == 1
        assert d[0]["kind"] == "singing_rock"
        assert "Singing Stone" in d[0]["name_and_description"]

    def test_project_unsettled_confirmed_excluded(self):
        km = create_empty_known_map("east_adam")
        km["myths"] = [
            {"id": "myth_a", "claim": "a vague feeling", "confidence": 0.3,
             "status": "gathering"},
            {"id": "myth_b", "claim": "confirmed thing", "confidence": 1.0,
             "status": "confirmed"},
        ]
        reports = project_unsettled_reports(km)
        assert len(reports) == 1
        assert reports[0]["report"] == "a vague feeling"
