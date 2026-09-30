"""World-walls mutation script: invariants on fixture maps.

The real true map is 80,000 tiles / 83 MB. No test touches it; every test
builds a small fixture in tmp and drives the same mutate/check code the
real run uses. The mutation's own --dry-run/--apply flow is exercised
against fixtures too.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

import build_world_walls as bww  # noqa: E402


def _tile(tid, x, y, blocked=False):
    return {"tile_id": tid, "coordinates": {"x": x, "y": y},
            "terrain": "hill", "biome": "highland",
            "blocks_travel": blocked, "hazards": [], "resources": [],
            "water": {}}


def _fixture_map():
    """A minimal grid around the ring geometry: interior tiles, ring tiles
    on all four sides, edges crossing the ring (which must be stripped)."""
    r = bww.RING
    tiles, edges = [], []
    # Interior + ring coverage across every side
    coords = []
    for y in range(r["y_lo"], r["y_hi"] + 1):
        coords.append((r["west_x"], y))    # west wall column
        coords.append((r["east_x"], y))   # east wall column
        coords.append((r["west_x"] + 1, y))  # just inside
    for x in range(r["x_lo"], r["x_hi"] + 1):
        coords.append((x, r["north_y"]))  # north wall row
        coords.append((x, r["south_y"]))  # south wall row
        coords.append((x, r["south_y"] + 1))  # just inside
    seen = set()
    for x, y in coords:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        tiles.append(_tile(f"t_{x}_{y}", x, y))
    # An edge crossing the west wall (inside -> wall -> outside)
    inside = f"t_{r['west_x'] + 1}_0"
    wall = f"t_{r['west_x']}_0"
    outside = f"t_{r['west_x'] - 1}_0"
    tiles.append(_tile(outside, r["west_x"] - 1, 0))
    edges = [
        {"from_tile_id": inside, "to_tile_id": wall},
        {"from_tile_id": wall, "to_tile_id": outside},
        {"from_tile_id": inside, "to_tile_id": f"t_{r['west_x'] + 1}_1"},
    ]
    return {"tiles": tiles, "travel_edges": edges,
            "world_id": "fixture", "schema_version": "1"}


class TestRingGeometry:
    def test_all_four_sides_classify(self):
        r = bww.RING
        assert bww.ring_side_for(r["west_x"], 0) == "west"
        assert bww.ring_side_for(r["east_x"], 0) == "east"
        assert bww.ring_side_for(0, r["north_y"]) == "north"
        assert bww.ring_side_for(0, r["south_y"]) == "south"

    def test_interior_is_not_ring(self):
        assert bww.ring_side_for(0, 0) is None
        assert bww.ring_side_for(bww.RING["west_x"] + 1, 0) is None


class TestMutation:
    def test_ring_tiles_walled_and_blocking(self):
        data = _fixture_map()
        bww.mutate_map(data)
        ring = bww.ring_tile_ids(data)
        assert ring
        for t in data["tiles"]:
            if t["tile_id"] in ring:
                assert t["blocks_travel"] is True
                assert t["biome"] in ("deep_lake", "dark_thicket",
                                      "deep_ravine")

    def test_west_wall_is_lake_with_hazard(self):
        data = _fixture_map()
        bww.mutate_map(data)
        wall = next(t for t in data["tiles"]
                    if t["coordinates"]["x"] == bww.RING["west_x"]
                    and t["coordinates"]["y"] == 0)
        assert wall["biome"] == "deep_lake"
        assert "water_too_deep_to_wade" in wall["hazards"]
        assert wall["water"] == {"type": "lake", "drinkable": False}

    def test_edges_to_ring_stripped_edges_inside_kept(self):
        data = _fixture_map()
        report = bww.mutate_map(data)
        assert report["edges_stripped"] == 2
        assert report["edges_after"] == 1
        ring = bww.ring_tile_ids(data)
        for e in data["travel_edges"]:
            assert e["from_tile_id"] not in ring
            assert e["to_tile_id"] not in ring

    def test_interior_tiles_untouched(self):
        data = _fixture_map()
        before = {t["tile_id"]: dict(t)
                  for t in data["tiles"]
                  if bww.ring_side_for(t["coordinates"]["x"],
                                       t["coordinates"]["y"]) is None}
        bww.mutate_map(data)
        for t in data["tiles"]:
            if t["tile_id"] in before:
                assert t == before[t["tile_id"]]

    def test_tile_count_survives(self):
        data = _fixture_map()
        n = len(data["tiles"])
        bww.mutate_map(data)
        assert len(data["tiles"]) == n

    def test_idempotent_second_run_no_changes(self):
        data = _fixture_map()
        bww.mutate_map(data)
        assert bww.already_walled(data) is True
        snap = json.dumps(data)
        bww.mutate_map(data)  # must be a no-op on truth
        assert json.dumps(data) == snap


class TestInvariants:
    def test_clean_map_passes(self):
        data = _fixture_map()
        bww.mutate_map(data)
        assert bww.check_invariants(data) == []

    def test_surviving_edge_fails(self):
        data = _fixture_map()
        bww.mutate_map(data)
        r = bww.RING
        data["travel_edges"].append({
            "from_tile_id": f"t_{r['west_x'] + 1}_0",
            "to_tile_id": f"t_{r['west_x']}_0"})
        errs = bww.check_invariants(data)
        assert any("touches ring" in e for e in errs)

    def test_unblocked_ring_tile_fails(self):
        data = _fixture_map()
        bww.mutate_map(data)
        r = bww.RING
        t = next(t for t in data["tiles"]
                 if t["coordinates"]["x"] == r["west_x"]
                 and t["coordinates"]["y"] == 0)
        t["blocks_travel"] = False
        errs = bww.check_invariants(data)
        assert any("does not block" in e for e in errs)


class TestDryRunApplyFlow:
    def test_dry_run_writes_nothing(self, tmp_path):
        data = _fixture_map()
        path = tmp_path / "map.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        rc = bww.main(["--map", str(path)])
        assert rc == 0
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == data, "dry-run must not write"

    def test_apply_writes_and_validates(self, tmp_path):
        data = _fixture_map()
        path = tmp_path / "map.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        rc = bww.main(["--map", str(path), "--apply", "--skip-backup"])
        assert rc == 0
        written = json.loads(path.read_text(encoding="utf-8"))
        assert bww.already_walled(written)
        assert bww.check_invariants(written) == []

    def test_second_apply_is_noop(self, tmp_path, capsys):
        data = _fixture_map()
        path = tmp_path / "map.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert bww.main(["--map", str(path), "--apply", "--skip-backup"]) == 0
        snap = path.read_text(encoding="utf-8")
        assert bww.main(["--map", str(path), "--apply",
                         "--skip-backup"]) == 0
        assert "ALREADY STANDING" in capsys.readouterr().out
        assert path.read_text(encoding="utf-8") == snap
