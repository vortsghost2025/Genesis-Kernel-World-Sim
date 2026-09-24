"""Tests for region naming + rare discovery content (scratch-only).

Region namer: determinism, coverage, authored-region preservation,
validator compliance. Rare discoveries: determinism, eligibility rules
(far from known, right terrain, no shared tiles), embed integrity for all
existing records.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent


def load_mod(name):
    spec = importlib.util.spec_from_file_location(
        name, WORLD_SIM / "scripts" / "world_content" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rn = load_mod("region_namer")
rd = load_mod("rare_discoveries")


def make_world() -> dict:
    """Compact synthetic planet: 2 continents, authored heartlands, and a
    deterministic generated belt with real elevation/water gradients."""
    tiles = []
    for cid, (ox, oy) in (("cont_a", (0, 0)), ("cont_b", (48, 48))):
        for x in range(-12, 13):
            for y in range(-12, 13):
                ax, ay = ox + x, oy + y
                r = abs(x) + abs(y)
                if r >= 15:
                    terrain, biome, blocks, elev = "ocean", "open_sea", True, 0.0
                    water = {"type": "sea", "drinkable": False}
                else:
                    water = {"type": "river", "drinkable": True} if (x == 0 and r >= 6) else None
                    if r >= 10:
                        terrain, elev = "mountain", round(r / 14, 3)
                    elif r >= 7:
                        terrain, elev = "hill", round(r / 15, 3)
                    elif r >= 4:
                        terrain, elev = "forest", round(r / 20, 3)
                    else:
                        terrain, elev = "grassland", round(r / 20, 3)
                    biome, blocks = "test_biome", False
                tiles.append({
                    "tile_id": f"{cid}_gen_{ax}_{ay}", "continent_id": cid,
                    "region_id": f"{cid}_generated_expanse",
                    "coordinates": {"x": ax, "y": ay}, "terrain": terrain,
                    "biome": biome, "elevation": elev, "water": water,
                    "resources": [], "hazards": [], "landmark_ids": [],
                    "blocks_travel": blocks,
                })
    # authored heartlands (must survive untouched)
    tiles.append({
        "tile_id": "public-shared-center", "continent_id": "cont_a",
        "region_id": "cont_a_first_pair_habitat",
        "coordinates": {"x": 0, "y": -1}, "terrain": "grassland",
        "biome": "temperate_valley", "elevation": 0.2, "water": None,
        "resources": [], "hazards": [], "landmark_ids": ["lm_meeting_stone_center"],
        "blocks_travel": False,
    })
    return {
        "schema_version": "7B.1", "world_id": "test_world", "seed": "test_seed",
        "continents": [{"continent_id": "cont_a", "name": "Alpha"},
                       {"continent_id": "cont_b", "name": "Beta"}],
        "regions": [
            {"region_id": "cont_a_first_pair_habitat", "continent_id": "cont_a", "name": "First Pair Habitat"},
            {"region_id": "cont_a_generated_expanse", "continent_id": "cont_a", "name": "Alpha Continent Generated Expanse"},
            {"region_id": "cont_b_generated_expanse", "continent_id": "cont_b", "name": "Beta Continent Generated Expanse"},
        ],
        "tiles": tiles,
        "landmarks": [{
            "landmark_id": "lm_meeting_stone_center", "continent_id": "cont_a",
            "tile_id": "public-shared-center", "kind": "meeting_stone",
            "description": "stone",
        }],
        "resources": [], "hazards": [],
        "mysteries": [{"mystery_id": "mst_test", "tile_id": "cont_a_gen_1_1",
                       "kind": "repeating_sound", "reveal_threshold": 3}],
        "travel_edges": [{"from_tile_id": "public-shared-center",
                          "to_tile_id": "cont_a_gen_0_0", "mode": "walk"}],
    }


# ---- region namer ----------------------------------------------------------

def test_deterministic():
    a = rn.name_regions(make_world())
    b = rn.name_regions(make_world())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_every_generated_tile_named():
    out = rn.name_regions(make_world())
    assert [t for t in out["tiles"] if t["region_id"].endswith("_generated_expanse")] == []
    assert [r for r in out["regions"] if r["region_id"].endswith("_generated_expanse")] == []


def test_authored_records_preserved_byte_exact():
    base = make_world()
    out = rn.name_regions(base)
    before = {t["tile_id"]: t for t in base["tiles"]}
    after = {t["tile_id"]: t for t in out["tiles"]}
    for tid, t in before.items():
        if not t["region_id"].endswith("_generated_expanse"):
            assert after[tid] == t, f"authored tile altered: {tid}"
    authored_regions = {r["region_id"]: r for r in base["regions"]
                        if not r["region_id"].endswith("_generated_expanse")}
    after_regions = {r["region_id"]: r for r in out["regions"]}
    for rid, r in authored_regions.items():
        assert after_regions[rid] == r
    assert out["landmarks"] == base["landmarks"]
    assert out["travel_edges"] == base["travel_edges"]
    assert out["mysteries"] == base["mysteries"]


def test_region_names_human_readable():
    out = rn.name_regions(make_world())
    names = [r["name"] for r in out["regions"]
             if r["region_id"] != "cont_a_first_pair_habitat"]
    assert len(names) == len(set(names))  # unique
    assert all(n.startswith("The ") for n in names)


def test_sea_regions_exist_per_continent():
    out = rn.name_regions(make_world())
    seas = {c: f"{c}_sea" in {r["region_id"] for r in out["regions"]}
            for c in ("cont_a", "cont_b")}
    assert all(seas.values())


def test_manifest_counts():
    base = make_world()
    out = rn.name_regions(base)
    m = rn.naming_manifest(base, out)
    gen_before = sum(1 for t in base["tiles"]
                     if t["region_id"].endswith("_generated_expanse"))
    assert m["tiles_moved_to_named_regions"] == gen_before
    assert m["regions_after"] > m["regions_before"]


def test_validator_accepts_named_world():
    import sys
    sys.path.insert(0, str(WORLD_SIM))
    from backend.world.fog_of_war import validate_true_map
    out = rn.name_regions(make_world())
    v = validate_true_map(out)
    assert v["ok"], v["errors"]


# ---- rare discoveries ---------------------------------------------------------

def test_placements_deterministic():
    w = make_world()
    a, _ = rd.place_discoveries(w, set(), "seed1")
    b, _ = rd.place_discoveries(w, set(), "seed1")
    assert json.dumps(a["landmarks"], sort_keys=True) == json.dumps(b["landmarks"], sort_keys=True)


def test_placements_respect_rules():
    w = make_world()
    known = {"cont_a_gen_0_0", "public-shared-center"}
    out, manifest = rd.place_discoveries(w, known, "seed1")
    tile_by_id = {t["tile_id"]: t for t in out["tiles"]}
    seen_tiles = set()
    for lm in out["landmarks"]:
        if not lm["landmark_id"].startswith("lm_") or lm["landmark_id"] == "lm_meeting_stone_center":
            continue
        tid = lm["tile_id"]
        assert tid not in known
        assert tid not in seen_tiles  # one wonder per tile
        seen_tiles.add(tid)
        assert lm["landmark_id"] in tile_by_id[tid]["landmark_ids"]
        assert not tile_by_id[tid]["blocks_travel"]
    assert len(seen_tiles) == len(rd.RARE_DISCOVERIES)
    # mystery tile untouched
    mst = tile_by_id["cont_a_gen_1_1"]
    assert not any(lm["tile_id"] == "cont_a_gen_1_1"
                   for lm in out["landmarks"] if lm["landmark_id"] != "lm_meeting_stone_center")


def test_no_placement_on_known_radius():
    w = make_world()
    # declare a broad known area; placement must stay 8+ away
    by_id = {t["tile_id"]: t for t in w["tiles"]}
    known = {"cont_a_gen_0_0"}
    out, _ = rd.place_discoveries(w, known, "seed1")
    kx, ky = by_id["cont_a_gen_0_0"]["coordinates"]["x"], by_id["cont_a_gen_0_0"]["coordinates"]["y"]
    for lm in out["landmarks"]:
        if lm["landmark_id"] == "lm_meeting_stone_center":
            continue
        c = by_id[lm["tile_id"]]["coordinates"]
        dist = abs(c["x"] - kx) + abs(c["y"] - ky)
        # only continent A wonders are subject to this known area
        if lm["continent_id"] == "cont_a":
            assert dist > rd.EXCLUSION_RADIUS


def test_wonder_content_complete():
    for w in rd.RARE_DISCOVERIES:
        assert w["hidden_name"] and len(w["description"]) > 80
        assert w["kind"]
        assert w["landmark_id"].startswith("lm_")


def test_world_records_preserved_except_landmark_additions():
    base = make_world()
    out, _ = rd.place_discoveries(base, set(), "seed1")
    before = {t["tile_id"]: t for t in base["tiles"]}
    after = {t["tile_id"]: t for t in out["tiles"]}
    for tid, t in before.items():
        a, b = t, after[tid]
        bb = dict(b); bb["landmark_ids"] = a["landmark_ids"]
        if b["landmark_ids"] != a["landmark_ids"]:
            # a wonder landed here; landmark_ids grew, and a water-bearing
            # wonder may also SET the tile's water (the wonder IS the water)
            bb["water"] = a["water"]
            if b.get("water") != a.get("water"):
                assert a.get("water") is None  # never displaces existing
        assert bb == a  # everything else untouched
    for k in ("continents", "regions", "mysteries", "travel_edges"):
        assert out[k] == base[k]
    assert len(base["landmarks"]) + len(rd.RARE_DISCOVERIES) == len(out["landmarks"])
