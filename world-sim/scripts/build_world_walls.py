"""Build the world walls: ring placement, edge stripping, invariants.

`docs/world_walls_spec.md` §4. This script is the ONLY sanctioned writer of
the enclosure into the true map. The load-bearing step is EDGE STRIPPING:
`derive_topology` filters known tiles by travel edges, NOT by the
`blocks_travel` flag - a surviving edge would make the ring walkable while
labeled impassable. Verified: 0 edges touch blocked tiles today; this
script must preserve that invariant at the ring.

Safety shape:
  * dry-run by default: reports what would change, writes nothing.
  * --apply: backup FIRST (true_map.pre-walls-bak.json), then atomic write,
    then validate + invariant checks after.
  * idempotent: a second run detects the ring already standing and no-ops.
  * NEVER silently shrinks the world: tile count must survive unchanged.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
DATA_ROOT = WORLD_SIM / "data"
TRUE_MAP = DATA_ROOT / "world" / "true_map.json"
BACKUP = TRUE_MAP.with_suffix(".json.pre-walls-bak")

# Ring geometry (world_walls_spec §1, recomputed from live positions at
# spec time: Adam x=-49 walking west, Eve x=+59-63 east; walls 4 ahead).
RING = {
    "west_x": -53,    # column of deep_lake
    "east_x": 63,     # column of deep_lake
    "north_y": 7,     # row of dark_thicket
    "south_y": -15,   # row of deep_ravine
    "y_lo": -14,     # column span (inclusive)
    "y_hi": 6,
    "x_lo": -53,     # row span (inclusive)
    "x_hi": 63,
}

WALL_SHAPES = {
    "west": {
        "terrain": "ocean", "biome": "deep_lake",
        "water": {"type": "lake", "drinkable": False},
        "hazards": ["water_too_deep_to_wade"],
    },
    "east": {
        "terrain": "ocean", "biome": "deep_lake",
        "water": {"type": "lake", "drinkable": False},
        "hazards": ["water_too_deep_to_wade"],
    },
    "north": {
        "terrain": "forest", "biome": "dark_thicket",
        "water": {},
        "hazards": ["impenetrable_dark"],
    },
    "south": {
        "terrain": "mountain", "biome": "deep_ravine",
        "water": {},
        "hazards": ["sheer_drop"],
    },
}


def ring_side_for(x: int, y: int) -> str | None:
    """Which ring wall a coordinate belongs to, if any. Corners resolve
    to a side deterministically (columns take precedence on overlap; the
    spans below make corner tiles belong to rows only when outside the
    column span)."""
    r = RING
    if x == r["west_x"] and r["y_lo"] <= y <= r["y_hi"]:
        return "west"
    if x == r["east_x"] and r["y_lo"] <= y <= r["y_hi"]:
        return "east"
    if y == r["north_y"] and r["x_lo"] <= x <= r["x_hi"]:
        return "north"
    if y == r["south_y"] and r["x_lo"] <= x <= r["x_hi"]:
        return "south"
    return None


def ring_tile_ids(data: dict) -> set[str]:
    out = set()
    for t in data.get("tiles", []):
        c = t.get("coordinates") or {}
        if ring_side_for(c.get("x"), c.get("y")):
            out.add(t.get("tile_id"))
    return out


def already_walled(data: dict) -> bool:
    """Idempotence check: every ring tile already carries its wall biome."""
    ring = set()
    for t in data.get("tiles", []):
        c = t.get("coordinates") or {}
        side = ring_side_for(c.get("x"), c.get("y"))
        if side:
            ring.add(t.get("tile_id"))
            if t.get("biome") != WALL_SHAPES[side]["biome"]:
                return False
            if not t.get("blocks_travel"):
                return False
    return bool(ring)


def mutate_map(data: dict) -> dict:
    """Apply the ring + strip incident edges IN the parsed map dict.

    Returns a report with exact counts. Does not touch the filesystem -
    tests call this against fixtures; only --apply against the real map
    writes, and only after the backup exists.
    """
    tile_index = {t.get("tile_id"): t for t in data.get("tiles", [])
                  if isinstance(t, dict)}
    changed = 0
    for t in data.get("tiles", []):
        c = t.get("coordinates") or {}
        side = ring_side_for(c.get("x"), c.get("y"))
        if not side:
            continue
        shape = WALL_SHAPES[side]
        t["terrain"] = shape["terrain"]
        t["biome"] = shape["biome"]
        t["water"] = dict(shape["water"])
        t["hazards"] = list(shape["hazards"])
        t["blocks_travel"] = True
        t["resources"] = []
        changed += 1

    ring_ids = set(tile_index.get(tid) and tid or tid
                   for tid in ring_tile_ids(data))
    edges_before = len(data.get("travel_edges", []))
    kept = []
    stripped = 0
    for e in data.get("travel_edges", []):
        if (e.get("from_tile_id") in ring_ids
                or e.get("to_tile_id") in ring_ids):
            stripped += 1
            continue
        kept.append(e)
    data["travel_edges"] = kept

    return {
        "ring_tiles": changed,
        "edges_before": edges_before,
        "edges_stripped": stripped,
        "edges_after": len(kept),
        "tile_count": len(data.get("tiles", [])),
    }


def check_invariants(data: dict) -> list[str]:
    """Post-mutation invariant checks. Empty list = all hold."""
    errors = []
    ring = ring_tile_ids(data)
    if not ring:
        return ["ring is empty - geometry produced no tiles"]
    for tid in ring:
        t = next((t for t in data["tiles"] if t.get("tile_id") == tid), None)
        if t is None:
            errors.append(f"ring tile {tid} vanished")
            continue
        if not t.get("blocks_travel"):
            errors.append(f"ring tile {tid} does not block travel")
    for e in data.get("travel_edges", []):
        if (e.get("from_tile_id") in ring
                or e.get("to_tile_id") in ring):
            errors.append(
                f"edge still touches ring: {e.get('from_tile_id')}<->"
                f"{e.get('to_tile_id')}")
            break
    if len(data.get("tiles", [])) != 80000 and "fixture" not in data.get(
            "world_id", ""):
        errors.append(f"tile count changed: {len(data.get('tiles', []))}")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--map", default=str(TRUE_MAP))
    p.add_argument("--apply", action="store_true",
                   help="mutate the map; without it, dry-run only")
    p.add_argument("--skip-backup", action="store_true",
                   help="test-only: no backup file (fixtures)")
    args = p.parse_args(argv)

    path = Path(args.map)
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"loaded {path} — {len(data['tiles'])} tiles, "
          f"{len(data['travel_edges'])} edges", flush=True)

    if already_walled(data):
        print("RING ALREADY STANDING — idempotent no-op.", flush=True)
        return 0

    report = mutate_map(data)
    print(json.dumps(report, indent=2), flush=True)

    errors = check_invariants(data)
    if errors:
        for e in errors:
            print(f"INVARIANT FAIL: {e}", flush=True)
        return 1
    print("invariants hold", flush=True)

    if not args.apply:
        print("DRY-RUN: nothing written.", flush=True)
        return 0

    if not args.skip_backup:
        if not BACKUP.is_file():
            shutil.copy2(path, BACKUP)
            print(f"backup written: {BACKUP}", flush=True)
        else:
            print(f"backup already present: {BACKUP}", flush=True)

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    # Validate the written file before replacing truth.
    written = json.loads(tmp.read_text(encoding="utf-8"))
    post = check_invariants(written)
    if post:
        tmp.unlink(missing_ok=True)
        for e in post:
            print(f"POST-WRITE INVARIANT FAIL: {e}", flush=True)
        return 1
    tmp.replace(path)
    print(f"WRITTEN: {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
