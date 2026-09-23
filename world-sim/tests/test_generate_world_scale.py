"""Tests for the 10JE scratch world-scale generator.

Scratch/fixture only: these tests never read world-sim/data, never touch
the living store, never call providers, and never write outside pytest
tmp dirs. The base worlds are built in-test or loaded from the existing
committed fixture tests/fixtures/fog_of_war/phase7e_true_map_seed_v1.json.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
FIXTURE = WORLD_SIM / "tests" / "fixtures" / "fog_of_war" / "phase7e_true_map_seed_v1.json"
GENERATOR_PATH = WORLD_SIM / "scripts" / "generate_world_scale.py"

spec = importlib.util.spec_from_file_location("generate_world_scale", GENERATOR_PATH)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def tiny_base() -> dict:
    """Minimal 2-continuum world with habitat-style tiles, a landmark,
    a mystery, and edges inside a small coordinate range."""
    return {
        "schema_version": "7B.1",
        "world_id": "tiny_test_world",
        "seed": "tiny_seed",
        "continents": [
            {"continent_id": "cont_a", "name": "Alpha"},
            {"continent_id": "cont_b", "name": "Beta"},
        ],
        "regions": [
            {"region_id": "cont_a_origin_valley", "continent_id": "cont_a", "name": "Origin Valley"},
            {"region_id": "cont_b_dawn_isle", "continent_id": "cont_b", "name": "Dawn Isle"},
        ],
        "tiles": [
            {
                "tile_id": "public-start-adam", "continent_id": "cont_a",
                "region_id": "cont_a_origin_valley",
                "coordinates": {"x": -1, "y": -1}, "terrain": "grassland",
                "biome": "temperate_valley", "elevation": 0.2, "water": None,
                "resources": [], "hazards": [], "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": "public-shared-center", "continent_id": "cont_a",
                "region_id": "cont_a_origin_valley",
                "coordinates": {"x": 0, "y": -1}, "terrain": "grassland",
                "biome": "temperate_valley", "elevation": 0.2, "water": None,
                "resources": [], "hazards": [],
                "landmark_ids": ["lm_meeting_stone_center"],
                "blocks_travel": False,
            },
            {
                "tile_id": "public-start-eve", "continent_id": "cont_a",
                "region_id": "cont_a_origin_valley",
                "coordinates": {"x": 1, "y": -1}, "terrain": "grassland",
                "biome": "temperate_valley", "elevation": 0.2, "water": None,
                "resources": [], "hazards": [], "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": "cont_b_origin_000", "continent_id": "cont_b",
                "region_id": "cont_b_dawn_isle",
                "coordinates": {"x": 50, "y": 50}, "terrain": "coast",
                "biome": "warm_coast", "elevation": 0.1,
                "water": {"type": "sea", "drinkable": False},
                "resources": [], "hazards": [], "landmark_ids": [],
                "blocks_travel": False,
            },
        ],
        "landmarks": [
            {
                "landmark_id": "lm_meeting_stone_center", "continent_id": "cont_a",
                "tile_id": "public-shared-center", "kind": "meeting_stone",
                "description": "Adam & Eve - founded at the center.",
            },
        ],
        "resources": [],
        "hazards": [],
        "mysteries": [
            {"mystery_id": "mst_test", "tile_id": "public-shared-center",
             "kind": "hum", "reveal_threshold": 3},
        ],
        "travel_edges": [
            {"from_tile_id": "public-start-adam", "to_tile_id": "public-shared-center", "mode": "walk"},
            {"from_tile_id": "public-shared-center", "to_tile_id": "public-start-adam", "mode": "walk"},
            {"from_tile_id": "public-shared-center", "to_tile_id": "public-start-eve", "mode": "walk"},
            {"from_tile_id": "public-start-eve", "to_tile_id": "public-shared-center", "mode": "walk"},
        ],
    }


SMALL_BOX = (-5, -5, 55, 55)  # contains all tiny_base coordinates


def test_deterministic_byte_identical():
    a = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    b = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_seed_changes_output():
    a = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    b = gen.generate_world(tiny_base(), seed="s2", box=SMALL_BOX, rim=2)
    assert json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)


def test_embed_byte_exact_all_records():
    base = tiny_base()
    out = gen.generate_world(base, seed="s1", box=SMALL_BOX, rim=2)
    tiles = {t["tile_id"]: t for t in out["tiles"]}
    for t in base["tiles"]:
        assert tiles[t["tile_id"]] == t, f"tile altered: {t['tile_id']}"
    landmarks = {lm["landmark_id"]: lm for lm in out["landmarks"]}
    for lm in base["landmarks"]:
        assert landmarks[lm["landmark_id"]] == lm
    assert out["mysteries"] == base["mysteries"]
    assert out["continents"] == base["continents"]
    assert out["resources"] == [] and out["hazards"] == []
    for r in base["regions"]:
        assert r in out["regions"]
    edge_keys = {json.dumps(e, sort_keys=True) for e in out["travel_edges"]}
    for e in base["travel_edges"]:
        assert json.dumps(e, sort_keys=True) in edge_keys
    # seed/world_id/schema_version untouched
    for k in ("schema_version", "world_id", "seed"):
        assert out[k] == base[k]


def test_generation_fills_box_and_counts():
    out = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    w = SMALL_BOX[2] - SMALL_BOX[0]
    h = SMALL_BOX[3] - SMALL_BOX[1]
    expected = 2 * w * h  # two continents
    assert len(out["tiles"]) == expected
    assert {c["region_id"] for c in out["regions"]} >= {
        "cont_a_generated_expanse", "cont_b_generated_expanse"
    }


def test_ocean_frame_blocked_and_edgeless():
    out = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    min_x, min_y, max_x, max_y = SMALL_BOX
    blocked, ocean = 0, 0
    for t in out["tiles"]:
        x, y = t["coordinates"]["x"], t["coordinates"]["y"]
        in_rim = (x < min_x + 2 or x >= max_x - 2 or y < min_y + 2 or y >= max_y - 2)
        if t["tile_id"].startswith("public-") or t["tile_id"] == "cont_b_origin_000":
            continue  # embedded records are exempt from the frame
        if in_rim:
            ocean += 1
            assert t["terrain"] == "ocean"
            assert t["biome"] == "open_sea"
            assert t["blocks_travel"] is True
            if t["blocks_travel"]:
                blocked += 1
    assert ocean > 0 and blocked == ocean
    edge_ids = set()
    for e in out["travel_edges"]:
        edge_ids.add(e["from_tile_id"])
        edge_ids.add(e["to_tile_id"])
    for t in out["tiles"]:
        if t["blocks_travel"] and t["tile_id"].endswith(("_gen_" + str(t["coordinates"]["x"]) + "_" + str(t["coordinates"]["y"]))):
            assert t["tile_id"] not in edge_ids


def test_edges_four_neighbor_symmetric():
    out = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    by_id = {t["tile_id"]: t for t in out["tiles"]}
    edge_set = {(e["from_tile_id"], e["to_tile_id"]) for e in out["travel_edges"]}
    gen_pairs = [
        (a, b) for a, b in edge_set
        if "_gen_" in a or "_gen_" in b
    ]
    for a, b in gen_pairs:
        ta, tb = by_id[a], by_id[b]
        dx = abs(ta["coordinates"]["x"] - tb["coordinates"]["x"])
        dy = abs(ta["coordinates"]["y"] - tb["coordinates"]["y"])
        assert (dx, dy) in ((1, 0), (0, 1)), f"non-adjacent edge {a}->{b}"
        assert ta["continent_id"] == tb["continent_id"], f"cross-continent edge {a}->{b}"
        assert (b, a) in edge_set, f"asymmetric generated edge {a}->{b}"


def test_collision_out_of_box_aborts():
    base = tiny_base()
    base["tiles"][0] = copy.deepcopy(base["tiles"][0])
    base["tiles"][0]["coordinates"] = {"x": 500, "y": 500}
    with pytest.raises(gen.GenerationError, match="outside the generation box"):
        gen.generate_world(base, seed="s1", box=SMALL_BOX, rim=2)


def test_collision_duplicate_coordinate_aborts():
    base = tiny_base()
    dup = copy.deepcopy(base["tiles"][1])
    dup["tile_id"] = "public-copy-center"
    base["tiles"].append(dup)
    with pytest.raises(gen.GenerationError, match="two tiles at"):
        gen.generate_world(base, seed="s1", box=SMALL_BOX, rim=2)


def test_vocabulary_contained():
    out = gen.generate_world(load_fixture(), seed="s1", box=(-100, -100, 100, 100), rim=6)
    allowed_terrain = gen.LAND_TERRAINS | {"ocean"}
    allowed_biome = gen.LAND_BIOMES | {"open_sea"}
    for t in out["tiles"]:
        assert t["terrain"] in allowed_terrain, t["terrain"]
        assert t["biome"] in allowed_biome, t["biome"]
    for lm in out["landmarks"]:
        assert lm["kind"] in gen.GENERATED_LANDMARK_KINDS | {"river", "tree", "mountain_peak", "cove", "rock_formation", "cliff_ledge"}


def test_fixture_world_embed_and_validate():
    base = load_fixture()
    out = gen.generate_world(base, seed="s1", box=(-100, -100, 100, 100), rim=6)
    tiles = {t["tile_id"]: t for t in out["tiles"]}
    for t in base["tiles"]:
        assert tiles[t["tile_id"]] == t
    edge_keys = {json.dumps(e, sort_keys=True) for e in out["travel_edges"]}
    for e in base["travel_edges"]:
        assert json.dumps(e, sort_keys=True) in edge_keys
    assert len(out["tiles"]) == 2 * 200 * 200
    assert len(out["mysteries"]) == len(base["mysteries"])


def test_write_candidate_to_tmp(tmp_path):
    out = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    map_path, manifest_path = gen.write_candidate(
        out, tmp_path, seed="s1", base_map_path=Path("fixture.json"),
        box=SMALL_BOX, rim=2,
    )
    loaded = json.loads(map_path.read_text(encoding="utf-8"))
    assert len(loaded["tiles"]) == len(out["tiles"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["canonical_write"] is False
    assert manifest["counts"]["tiles"] == len(out["tiles"])
    assert manifest["output_sha256"]


def test_no_mysteries_generated():
    out = gen.generate_world(tiny_base(), seed="s1", box=SMALL_BOX, rim=2)
    assert out["mysteries"] == tiny_base()["mysteries"]
    # generation produced many landmark kinds, none of them is a mystery path
    assert all(m["mystery_id"] == "mst_test" for m in out["mysteries"])
