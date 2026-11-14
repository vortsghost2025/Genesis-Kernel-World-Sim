"""The operator-authorized single-tile resource authoring tool.

Operator chose to FIX the live finding rather than record it: east_adam
occupies `cont_a_gen_-43_5`, a temperate hill authored with no resources,
while the tile beside it carries stone and clay.

These tests pin the guards, because the whole point of the tool is that it can
only do the one declared thing: the transform is pure, idempotent, refuses
unknown tiles, and the embed gate aborts if anything else in the map moves.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from author_tile_resource import (  # noqa: E402
    AuthorError,
    author_tile_resource,
    embed_gate,
    resource_id_for,
)


def _map() -> dict:
    return {
        "schema_version": "7B.1",
        "tiles": [
            {
                "tile_id": "cont_a_gen_-43_5", "continent_id": "cont_a",
                "region_id": "reg_1", "coordinates": {"x": -43, "y": 5},
                "terrain": "hill", "biome": "temperate_hills",
                "resources": [], "hazards": [], "landmark_ids": [],
                "blocks_travel": False,
            },
            {
                "tile_id": "cont_a_gen_-43_6", "continent_id": "cont_a",
                "region_id": "reg_1", "coordinates": {"x": -43, "y": 6},
                "terrain": "hill", "biome": "temperate_hills",
                "resources": ["stone", "clay"], "hazards": [],
                "landmark_ids": [], "blocks_travel": False,
            },
        ],
        "resources": [
            {"resource_id": "res_cont_a_gen_-43_6_stone", "kind": "stone",
             "amount": 5, "renewable": False, "tile_id": "cont_a_gen_-43_6"},
            {"resource_id": "res_cont_a_gen_-43_6_clay", "kind": "clay",
             "amount": 2, "renewable": False, "tile_id": "cont_a_gen_-43_6"},
        ],
        "continents": [{"continent_id": "cont_a", "name": "East"}],
        "regions": [{"region_id": "reg_1", "name": "Hills"}],
    }


def test_authoring_adds_the_record_and_the_tile_listing():
    before = _map()
    after, summary = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    assert summary["changed"] is True
    assert summary["resource_id"] == "res_cont_a_gen_-43_5_stone"
    rec = next(r for r in after["resources"]
               if r["resource_id"] == "res_cont_a_gen_-43_5_stone")
    assert rec["kind"] == "stone" and rec["amount"] == 4
    assert rec["renewable"] is False
    target = next(t for t in after["tiles"]
                  if t["tile_id"] == "cont_a_gen_-43_5")
    assert target["resources"] == ["stone"]


def test_the_transform_never_mutates_its_input():
    before = _map()
    snapshot = copy.deepcopy(before)
    author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    assert before == snapshot


def test_the_output_shares_no_mutable_state_with_the_input():
    """Regression: the first version appended the input's OWN record dicts onto
    the returned list, so editing the result silently edited the original and
    the embed gate could not see it."""
    before = _map()
    after, _ = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    after["resources"][0]["amount"] = 999
    after["tiles"][0]["biome"] = "swamp"
    assert before["resources"][0]["amount"] == 5
    assert before["tiles"][0]["biome"] == "temperate_hills"


def test_it_is_idempotent_so_re_running_cannot_duplicate():
    once, _ = author_tile_resource(_map(), "cont_a_gen_-43_5", "stone", 4)
    twice, summary = author_tile_resource(once, "cont_a_gen_-43_5", "stone", 4)
    assert summary["changed"] is False
    assert twice is once
    assert len([r for r in twice["resources"]
                if r["resource_id"] == "res_cont_a_gen_-43_5_stone"]) == 1


def test_an_unknown_tile_is_refused():
    with pytest.raises(AuthorError):
        author_tile_resource(_map(), "cont_a_gen_99_99", "stone", 4)


def test_a_nonpositive_amount_is_refused():
    for bad in (0, -3, True):
        with pytest.raises(AuthorError):
            author_tile_resource(_map(), "cont_a_gen_-43_5", "stone", bad)


def test_a_tile_listing_the_kind_without_a_record_is_refused():
    """Do not paper over a pre-existing inconsistency by guessing."""
    broken = _map()
    broken["tiles"][0]["resources"] = ["stone"]
    with pytest.raises(AuthorError):
        author_tile_resource(broken, "cont_a_gen_-43_5", "stone", 4)


def test_the_gate_accepts_exactly_its_own_change():
    before = _map()
    after, summary = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    embed_gate(before, after, summary)  # must not raise


def test_the_gate_aborts_when_a_preexisting_record_moves():
    before = _map()
    after, summary = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    after["resources"][0]["amount"] = 999  # somebody altered an existing deposit
    with pytest.raises(AuthorError):
        embed_gate(before, after, summary)


def test_the_gate_aborts_when_a_foreign_tile_changes():
    before = _map()
    after, summary = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    next(t for t in after["tiles"]
         if t["tile_id"] == "cont_a_gen_-43_6")["biome"] = "swamp"
    with pytest.raises(AuthorError):
        embed_gate(before, after, summary)


def test_the_gate_aborts_when_the_target_changes_beyond_its_resources():
    before = _map()
    after, summary = author_tile_resource(before, "cont_a_gen_-43_5", "stone", 4)
    target = next(t for t in after["tiles"]
                  if t["tile_id"] == "cont_a_gen_-43_5")
    target["hazards"] = ["rockslide"]
    with pytest.raises(AuthorError):
        embed_gate(before, after, summary)


def test_resource_id_convention_matches_the_existing_records():
    """Every authored record in the real map follows res_<tile>_<kind>."""
    assert resource_id_for("cont_a_gen_-43_5", "stone") == "res_cont_a_gen_-43_5_stone"


@pytest.mark.skipif(
    not (WORLD_SIM / "data" / "world" / "true_map.json").is_file(),
    reason="true map is gitignored; generate it first",
)
def test_the_live_map_still_satisfies_the_audit_for_the_authored_tile():
    """The finding this tool was authorized to fix is actually fixed."""
    true_map = json.loads(
        (WORLD_SIM / "data" / "world" / "true_map.json").read_text(encoding="utf-8"))
    resources = {}
    for rec in true_map.get("resources", []):
        resources.setdefault(rec.get("tile_id"), []).append(rec)
    tile = "cont_a_gen_-43_5"
    if tile not in {t.get("tile_id") for t in true_map.get("tiles", [])}:
        pytest.skip("tile absent from this generated map")
    yield_total = sum(r.get("amount", 0) for r in resources.get(tile, [])
                      if isinstance(r.get("amount"), int))
    assert yield_total > 0, (
        f"{tile} is still un-gatherable; run "
        f"scripts/author_tile_resource.py --tile {tile} --kind stone --amount 4 --apply")
