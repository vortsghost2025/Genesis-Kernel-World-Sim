"""Region naming transformation - pure, deterministic, scratch-only.

The 10JE expansion dropped ~40k generated tiles per continent into two
catch-all regions ("cont_a_generated_expanse" / "cont_b_generated_expanse").
That is honest bookkeeping and terrible geography. This module renames the
wilderness into named regions an agent can actually perceive:
"The Southern Meadows" reads like a place; "generated expanse" reads like
a build artifact.

Hard rules:

1. This is a DATA TRANSFORMATION of a candidate true map. It reads a map
   dict in memory (loaded from canonical data by the caller) and returns a
   NEW dict. It never writes files. The caller writes to scratch only.
2. Authored regions are sacred: any region whose tiles predate the
   generator is preserved byte-exact, and its tiles are never reassigned.
3. Every generated (``_gen_``) tile is reassigned from its catch-all
   expanse region into exactly one named region. When the transform
   finishes, no tile references the expanse regions and the expanse
   regions themselves are gone.
4. Deterministic: same input map -> same region layout, same names,
   byte-identical candidate.
5. Ocean is real geography here: the ocean frame becomes each continent's
   sea region (named, bounded, still blocks_travel).

Naming scheme (deterministic, seeded word-lists, human-readable):
- 8 compass sectors per continent computed from the box center.
- Land tiles in a sector are sub-grouped by dominant terrain:
  grassland->Meadows, forest->Wildwood, hill->Marches, mountain->Teeth,
  coast->Reaches ("The Southern Meadows", "The Northwestern Teeth"...).
- A sector+terrain group below MIN_CLUSTER_TILES is merged into its
  sector's neighbor to avoid sliver regions.
- Ocean tiles per continent -> one sea region per continent.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

GENERATED_SUFFIX = "_generated_expanse"
MIN_CLUSTER_TILES = 400  # sector groups smaller than this merge away

SECTOR_WORDS = {
    "N": "Northern", "NE": "Northeastern", "E": "Eastern", "SE": "Southeastern",
    "S": "Southern", "SW": "Southwestern", "W": "Western", "NW": "Northwestern",
}
TERRAIN_WORDS = {
    "grassland": ["Meadows", "Fields"],
    "forest": ["Wildwood", "Greenhollows"],
    "hill": ["Marches", "Terraces"],
    "mountain": ["Teeth", "Spines"],
    "coast": ["Reaches", "Shores"],
}
SEA_NAMES = {"cont_a": "The Encircling Sea", "cont_b": "The Outer Blue"}


def _sector(cx: float, cy: float, x: float, y: float) -> str:
    dx, dy = x - cx, y - cy
    # screen coordinates: -y is north
    import math

    ang = math.degrees(math.atan2(-dy, dx)) % 360.0
    # center = E, rotate so sectors are 8 equal pies
    idx = int(((ang + 22.5) % 360) // 45)
    return ["E", "NE", "N", "NW", "W", "SW", "S", "SE"][idx]


def _pick(words: list[str], key: str) -> str:
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
    return words[h % len(words)]


def name_regions(true_map: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW true map with generated tiles in named regions.

    Existing authored regions and their tiles are untouched. Raises
    ValueError if any generated tile would be left unassigned.
    """
    out = copy.deepcopy(true_map)
    tiles = out["tiles"]

    gen = [t for t in tiles if t["region_id"].endswith(GENERATED_SUFFIX)]
    authored_region_ids = {r["region_id"] for r in out["regions"]
                           if not r["region_id"].endswith(GENERATED_SUFFIX)}
    if not gen:
        return out  # nothing to transform

    # continent box centers from overall per-continent extents
    by_cont: dict[str, list[dict]] = {}
    for t in tiles:
        by_cont.setdefault(t["continent_id"], []).append(t)

    sea_region_id: dict[str, str] = {}
    assignments: dict[str, str] = {}  # tile_id -> new region_id
    new_regions: dict[str, dict] = {}

    for cont_id, ctile in by_cont.items():
        xs = [t["coordinates"]["x"] for t in ctile]
        ys = [t["coordinates"]["y"] for t in ctile]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0

        cont_gen = [t for t in ctile if t["region_id"].endswith(GENERATED_SUFFIX)]
        if not cont_gen:
            continue

        # sea first
        sea_id = f"{cont_id}_sea"
        sea_region_id[cont_id] = sea_id
        for t in cont_gen:
            if t["terrain"] == "ocean":
                assignments[t["tile_id"]] = sea_id
        if any(assignments.get(t["tile_id"]) == sea_id for t in cont_gen):
            new_regions[sea_id] = {
                "region_id": sea_id,
                "continent_id": cont_id,
                "name": SEA_NAMES.get(cont_id, "The Endless Sea"),
            }

        # land: sector -> terrain groups
        groups: dict[tuple[str, str], list[dict]] = {}
        for t in cont_gen:
            if t["terrain"] == "ocean":
                continue
            sec = _sector(cx, cy, t["coordinates"]["x"], t["coordinates"]["y"])
            groups.setdefault((sec, t["terrain"]), []).append(t)

        # merge undersized groups into the sector's largest other group
        sizes = {k: len(v) for k, v in groups.items()}
        for (sec, terr), members in sorted(groups.items(), key=lambda kv: len(kv[1])):
            if terr == "ocean" or not members:
                continue
            if sizes[(sec, terr)] < MIN_CLUSTER_TILES:
                candidates = [
                    (k, len(v)) for k, v in groups.items()
                    if k[0] == sec and k != (sec, terr) and v
                ]
                if candidates:
                    tgt = max(candidates, key=lambda kv: kv[1])[0]
                    groups[tgt].extend(members)
                    members.clear()
                # else: sole terrain group in the sector - keep it regardless

        used_names = {r["name"] for r in new_regions.values()}
        for (sec, terr), members in sorted(groups.items()):
            if not members:
                continue
            words = TERRAIN_WORDS.get(terr, ["Reaches"])
            # names must be unique across the whole world: two continents may
            # both want "The Northern Fields" - the loser takes the variant.
            tried = []
            word = None
            for i in range(len(words)):
                cand = words[(int(hashlib.sha256(
                    f"{cont_id}|{sec}|{terr}".encode()).hexdigest()[:8], 16) + i)
                    % len(words)]
                name = f"The {SECTOR_WORDS[sec]} {cand}"
                if name not in used_names:
                    word = cand
                    break
                tried.append(name)
            if word is None:
                word = tried[0].replace(f"The {SECTOR_WORDS[sec]} ", "")
                name = f"The Far {SECTOR_WORDS[sec]} {word}"
            rid = f"{cont_id}_{SECTOR_WORDS[sec].lower()}_{word.lower()}"
            n = 2
            base = rid
            while rid in new_regions:
                rid = f"{base}_{n}"
                n += 1
            new_regions[rid] = {"region_id": rid, "continent_id": cont_id,
                                "name": name}
            used_names.add(name)
            for t in members:
                assignments[t["tile_id"]] = rid

    # apply
    for t in tiles:
        if t["tile_id"] in assignments:
            t["region_id"] = assignments[t["tile_id"]]

    # drop the emptied expanse regions, add the named ones
    out["regions"] = [r for r in out["regions"]
                      if not r["region_id"].endswith(GENERATED_SUFFIX)]
    out["regions"].extend(new_regions[rid] for rid in sorted(new_regions))

    # verify completeness
    leftover = [t["tile_id"] for t in tiles
                if t["region_id"].endswith(GENERATED_SUFFIX)]
    if leftover:
        raise ValueError(f"naming incomplete: {len(leftover)} generated tiles unassigned")

    # verify every tile references an existing region
    region_ids = {r["region_id"] for r in out["regions"]}
    bad = [t["tile_id"] for t in tiles if t["region_id"] not in region_ids]
    if bad:
        raise ValueError(f"naming produced dangling region refs: {bad[:5]}")

    return out


def naming_manifest(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Summary evidence for the transformation (recorded alongside output)."""
    counts: dict[str, int] = {}
    for t in after["tiles"]:
        counts[t["region_id"]] = counts.get(t["region_id"], 0) + 1
    moved = sum(
        1 for tb, ta in zip(before["tiles"], after["tiles"])
        if tb["tile_id"] == ta["tile_id"] and tb["region_id"] != ta["region_id"]
    )
    return {
        "tiles_moved_to_named_regions": moved,
        "regions_before": len(before["regions"]),
        "regions_after": len(after["regions"]),
        "new_region_sizes": {r["region_id"]: counts.get(r["region_id"], 0)
                             for r in after["regions"]
                             if r["region_id"] not in
                             {x["region_id"] for x in before["regions"]}},
    }
