"""10JE world-scale generator - scratch-only build tool.

Phase 10JE (implementation candidate for the 10JC design specification).

Generates a world-sized ``true_map.json`` candidate around the existing
canonical world. READ-ONLY against canonical data, scratch-only output.
Never edits ``world-sim/data``. Never runs at runtime. Never touches the
living store.

Core guarantees (10JC sections 3.3, 4, 13):

1. Embed, never regenerate: every record of the input map is carried
   byte-exact (JSON-value equality) - continents, regions, tiles,
   landmarks, mysteries, travel edges. The generator only FILLS
   coordinates the existing world does not occupy.
2. Collision is failure: any ID reuse, coordinate reuse, or an existing
   tile outside its continent's generation box aborts the run. There is
   no rename path.
3. Deterministic: same seed + same input map + same parameters produce a
   byte-identical output file.
4. Stdlib only. No network. No clock. Seeded hash-noise terrain.

Geometry (operator bullet list for 10JE buildout; 10JC section 18 track):
two continent boxes, default [-100,100) x [-100,100) (200x200 = 40,000
tiles per continent, ~80,000 total), which contain every existing
coordinate of both continents. An ocean frame fills the rim band of each
box (``blocks_travel: true``, terrain ``ocean``, biome ``open_sea``, no
edges) so the world's edge reads from inside as endless sea.

The terrain sampler is deliberately a seam: ``TerrainSampler`` protocol.
The initial implementation (SeededNoiseSampler) covers the operator's
200x200 + ocean-frame buildout; a real-Earth dataset sampler (10JC
section 5) can replace it without touching embed/edge/validation logic.

Known scope notes (recorded for review, not hidden):
- The committed 10JC spec describes the young-Earth template (section
  18.1, not yet operator-confirmed). This file implements the shared
  skeleton with the seeded-noise geometry from the operator's 10JE
  bullet list. The young-Earth sampler plugs into the same seam.
- Generated tiles are assigned to one generated region per continent
  (``<continent_id>_generated_expanse``). Real province regions are a
  young-Earth-sampler concern.

Usage:
    python world-sim/scripts/generate_world_scale.py [--seed SEED]
        [--base-map PATH] [--out DIR] [--rim N] [--box MIN MIN MAX MAX]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import validate_true_map  # noqa: E402

DEFAULT_BASE_MAP = WORLD_SIM / "data" / "world" / "true_map.json"
DEFAULT_SEED = "genesis_world_scale_10je_v1"

# Existing vocabulary (10JC section 5.6 reuse set) + the two additions the
# ocean frame requires (terrain "ocean", biome "open_sea").
LAND_TERRAINS = {"grassland", "forest", "hill", "mountain", "coast"}
LAND_BIOMES = {
    "temperate_valley", "temperate_forest", "temperate_hills", "highland",
    "dense_woodland", "warm_coast", "coastal_forest", "coastal_cliffs",
}
GENERATED_LANDMARK_KINDS = {
    "river", "tree", "mountain_peak", "cove", "rock_formation", "cliff_ledge",
}


class GenerationError(Exception):
    """Any failed invariant aborts generation; no partial artifact."""


class TerrainSampler(Protocol):
    """Pluggable terrain source. Sampling must be pure/deterministic."""

    def terrain_at(self, continent_id: str, x: int, y: int) -> dict[str, Any]:
        """Return tile content fields for a LAND cell at (x, y)."""
        ...


def _hash01(seed: str, *parts: Any) -> float:
    """Deterministic pseudo-random float in [0, 1) from seed + parts."""
    h = hashlib.sha256()
    h.update(seed.encode("utf-8"))
    for p in parts:
        h.update(b"|")
        h.update(str(p).encode("utf-8"))
    return int.from_bytes(h.digest()[:8], "big") / 2**64


class SeededNoiseSampler:
    """Value-noise terrain: coarse hash lattice, bilinear interpolation.

    Two independent fields (height, moisture) drive the existing terrain /
    biome vocabulary. Pure stdlib, fully deterministic.
    """

    LATTICE = 8  # cells between lattice anchors

    def __init__(self, seed: str) -> None:
        self.seed = seed

    def _field(self, name: str, continent_id: str, x: int, y: int) -> float:
        lat = self.LATTICE
        x0, y0 = (x // lat) * lat, (y // lat) * lat
        fx, fy = (x - x0) / lat, (y - y0) / lat
        v00 = _hash01(self.seed, name, continent_id, x0, y0)
        v10 = _hash01(self.seed, name, continent_id, x0 + lat, y0)
        v01 = _hash01(self.seed, name, continent_id, x0, y0 + lat)
        v11 = _hash01(self.seed, name, continent_id, x0 + lat, y0 + lat)
        top = v00 + (v10 - v00) * fx
        bot = v01 + (v11 - v01) * fx
        return top + (bot - top) * fy

    def terrain_at(self, continent_id: str, x: int, y: int) -> dict[str, Any]:
        h = self._field("height", continent_id, x, y)
        m = self._field("moisture", continent_id, x, y)
        water = None
        if h < 0.18:
            terrain, biome = "coast", "warm_coast"
        elif h < 0.42:
            if m > 0.75:
                # seeded inland river/lake on low, wet ground
                water = {"type": "river", "drinkable": True}
            terrain, biome = ("forest", "temperate_forest") if m > 0.55 else ("grassland", "temperate_valley")
        elif h < 0.62:
            if m > 0.65:
                terrain, biome = "forest", "dense_woodland"
            else:
                terrain, biome = "hill", "temperate_hills"
        elif h < 0.82:
            terrain, biome = "hill", "highland"
        else:
            terrain, biome = "mountain", "highland"
        return {
            "terrain": terrain,
            "biome": biome,
            "elevation": round(h, 3),
            "water": water,
            "resources": [],
            "hazards": [],
        }


def _json_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def generate_world(
    base_map: dict[str, Any],
    *,
    seed: str = DEFAULT_SEED,
    box: tuple[int, int, int, int] = (-100, -100, 100, 100),
    rim: int = 6,
    landmark_density: float = 0.004,
    sampler: TerrainSampler | None = None,
) -> dict[str, Any]:
    """Generate a world-expanded candidate map. Pure; returns data only.

    Raises GenerationError on any invariant violation. Never writes.
    """
    if sampler is None:
        sampler = SeededNoiseSampler(seed)
    min_x, min_y, max_x, max_y = box
    if rim < 1:
        raise GenerationError("rim must be >= 1")
    if max_x - min_x <= 2 * rim or max_y - min_y <= 2 * rim:
        raise GenerationError("box too small for rim band")

    required = ["schema_version", "world_id", "seed", "continents", "regions",
                "tiles", "landmarks", "resources", "hazards", "mysteries",
                "travel_edges"]
    for key in required:
        if key not in base_map:
            raise GenerationError(f"base map missing required key: {key}")

    continents = base_map["continents"]
    continent_ids = [c["continent_id"] for c in continents]
    if len(continent_ids) != len(set(continent_ids)):
        raise GenerationError("duplicate continent_id in base map")

    # ---- index existing records ------------------------------------------
    existing_ids: dict[str, set] = {
        "tile": {t["tile_id"] for t in base_map["tiles"]},
        "landmark": {lm["landmark_id"] for lm in base_map["landmarks"]},
        "region": {r["region_id"] for r in base_map["regions"]},
    }
    occupied: dict[tuple[str, int, int], dict] = {}
    for t in base_map["tiles"]:
        c = t["coordinates"]
        key = (t["continent_id"], int(c["x"]), int(c["y"]))
        if key in occupied:
            raise GenerationError(
                f"base map has two tiles at {key}: "
                f"{occupied[key]['tile_id']} and {t['tile_id']}"
            )
        # Every existing tile must lie inside its generation box.
        if not (min_x <= key[1] < max_x and min_y <= key[2] < max_y):
            raise GenerationError(
                f"existing tile {t['tile_id']} at ({key[1]},{key[2]}) lies "
                f"outside the generation box {box}"
            )
        occupied[key] = t

    # ---- per-continent generation ----------------------------------------
    out_tiles: list[dict] = []
    out_landmarks: list[dict] = []
    region_ids_used: set[str] = set(existing_ids["region"])
    landmark_seq = 0

    for continent in continents:
        cid = continent["continent_id"]
        region_id = f"{cid}_generated_expanse"
        if region_id in region_ids_used:
            raise GenerationError(f"generated region id collides: {region_id}")
        region_ids_used.add(region_id)

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                existing = occupied.get((cid, x, y))
                if existing is not None:
                    # EMBED: byte-exact, always wins (10JC 4.2).
                    out_tiles.append(existing)
                    continue
                in_rim = (x < min_x + rim or x >= max_x - rim
                          or y < min_y + rim or y >= max_y - rim)
                if in_rim:
                    terr = {
                        "terrain": "ocean", "biome": "open_sea",
                        "elevation": 0.0,
                        "water": {"type": "sea", "drinkable": False},
                        "resources": [], "hazards": [],
                        "blocks": True,
                    }
                else:
                    land = sampler.terrain_at(cid, x, y)
                    if land["terrain"] not in LAND_TERRAINS or land["biome"] not in LAND_BIOMES:
                        raise GenerationError(
                            f"sampler produced out-of-vocabulary terrain "
                            f"{land['terrain']}/{land['biome']} at ({cid},{x},{y})"
                        )
                    land["blocks"] = False
                    terr = land
                tile_id = f"{cid}_gen_{x}_{y}"
                if tile_id in existing_ids["tile"]:
                    raise GenerationError(f"generated tile id collides: {tile_id}")
                out_tiles.append({
                    "tile_id": tile_id,
                    "continent_id": cid,
                    "region_id": region_id if not in_rim else f"{cid}_generated_expanse",
                    "coordinates": {"x": x, "y": y},
                    "terrain": terr["terrain"],
                    "biome": terr["biome"],
                    "elevation": terr["elevation"],
                    "water": terr["water"],
                    "resources": list(terr["resources"]),
                    "hazards": list(terr["hazards"]),
                    "landmark_ids": [],
                    "blocks_travel": terr["blocks"],
                })
                if not in_rim and _hash01(seed, "lm", cid, x, y) < landmark_density:
                    landmark_seq += 1
                    lm_id = f"lm_{cid}_gen_{landmark_seq:05d}"
                    if lm_id in existing_ids["landmark"]:
                        raise GenerationError(f"generated landmark id collides: {lm_id}")
                    kind = _pick_landmark_kind(seed, cid, x, y, terr["terrain"])
                    out_landmarks.append({
                        "landmark_id": lm_id,
                        "continent_id": cid,
                        "tile_id": tile_id,
                        "kind": kind,
                        "hidden_name": f"Unnamed {kind.replace('_', ' ')}",
                        "description": f"A {kind.replace('_', ' ')}.",
                    })
                    out_tiles[-1]["landmark_ids"] = [lm_id]
        existing_ids["region"].add(region_id)

    # generated regions appended after existing ones (existing order kept)
    out_regions = list(base_map["regions"]) + [
        {"region_id": f"{c['continent_id']}_generated_expanse",
         "continent_id": c["continent_id"],
         "name": f"{c['name']} Generated Expanse"}
        for c in continents
    ]

    # ---- travel edges -----------------------------------------------------
    existing_edge_keys = {
        (e["from_tile_id"], e["to_tile_id"], e.get("mode", "walk"))
        for e in base_map["travel_edges"]
    }
    tile_by_coord = {
        (t["continent_id"], t["coordinates"]["x"], t["coordinates"]["y"]): t
        for t in out_tiles
    }
    generated_edges: list[dict] = []
    for (cid, x, y), t in tile_by_coord.items():
        if t["blocks_travel"]:
            continue
        for dx, dy in ((1, 0), (0, 1)):  # E and S only; both dirs emitted
            nb = tile_by_coord.get((cid, x + dx, y + dy))
            if nb is None or nb["blocks_travel"]:
                continue
            a, b = t["tile_id"], nb["tile_id"]
            for frm, to in ((a, b), (b, a)):
                if (frm, to, "walk") in existing_edge_keys:
                    continue  # existing edge embedded; do not duplicate
                generated_edges.append(
                    {"from_tile_id": frm, "to_tile_id": to, "mode": "walk"}
                )

    out_map = {
        "schema_version": base_map["schema_version"],
        "world_id": base_map["world_id"],
        "seed": base_map["seed"],
        "continents": list(base_map["continents"]),
        "regions": out_regions,
        "tiles": out_tiles,
        "landmarks": list(base_map["landmarks"]) + out_landmarks,
        "resources": [],   # 10JC section 9: top-level stays empty
        "hazards": [],     # 10JC section 9: top-level stays empty
        "mysteries": list(base_map["mysteries"]),  # authored-only, embedded
        "travel_edges": list(base_map["travel_edges"]) + generated_edges,
    }

    # ---- integrity gates ---------------------------------------------------
    _assert_embed(base_map, out_map)
    verdict = validate_true_map(out_map)
    if not verdict.get("ok"):
        raise GenerationError(f"validate_true_map failed: {verdict.get('errors')}")
    return out_map


def _pick_landmark_kind(seed: str, cid: str, x: int, y: int, terrain: str) -> str:
    by_terrain = {
        "grassland": ["tree", "rock_formation"],
        "forest": ["tree", "tree", "rock_formation"],
        "hill": ["rock_formation", "cliff_ledge"],
        "mountain": ["mountain_peak", "cliff_ledge"],
        "coast": ["cove", "rock_formation"],
    }
    opts = by_terrain.get(terrain, ["rock_formation"])
    kinds = [k for k in opts if k in GENERATED_LANDMARK_KINDS] or ["rock_formation"]
    return kinds[int(_hash01(seed, "lmkind", cid, x, y) * len(kinds)) % len(kinds)]


def _assert_embed(base_map: dict[str, Any], out_map: dict[str, Any]) -> None:
    """Every base-map record must survive byte-exact (JSON-value equality)."""
    def key_map(records: list[dict], id_field: str) -> dict:
        return {r[id_field]: r for r in records}

    base_tiles = key_map(base_map["tiles"], "tile_id")
    out_tiles = key_map(out_map["tiles"], "tile_id")
    for tid, t in base_tiles.items():
        if tid not in out_tiles:
            raise GenerationError(f"embed violation: tile missing: {tid}")
        if not _json_equal(t, out_tiles[tid]):
            raise GenerationError(f"embed violation: tile altered: {tid}")
    for coll, idf in (("landmarks", "landmark_id"), ("regions", "region_id"),
                      ("continents", "continent_id"), ("mysteries", "mystery_id")):
        base = key_map(base_map[coll], idf)
        out = key_map(out_map[coll], idf)
        for rid, rec in base.items():
            if rid not in out or not _json_equal(rec, out[rid]):
                raise GenerationError(f"embed violation in {coll}: {rid}")
    base_edges = {
        json.dumps(e, sort_keys=True) for e in base_map["travel_edges"]
    }
    out_edges = {json.dumps(e, sort_keys=True) for e in out_map["travel_edges"]}
    for e in base_edges:
        if e not in out_edges:
            raise GenerationError(f"embed violation: travel edge lost: {e}")
    if not _json_equal(base_map["resources"], out_map["resources"]):
        raise GenerationError("embed violation: top-level resources changed")
    if not _json_equal(base_map["hazards"], out_map["hazards"]):
        raise GenerationError("embed violation: top-level hazards changed")


def write_candidate(out_map: dict[str, Any], out_dir: Path, *, seed: str,
                    base_map_path: Path, box: tuple, rim: int) -> tuple[Path, Path]:
    """Write the candidate map + manifest into a scratch directory."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / "true_map.candidate.json"
    payload = json.dumps(out_map, indent=2, ensure_ascii=False)
    map_path.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    manifest = {
        "generator": "world-sim/scripts/generate_world_scale.py",
        "generator_phase": "10JE (scratch-only)",
        "seed": seed,
        "box": list(box),
        "rim": rim,
        "base_map": str(base_map_path),
        "output": str(map_path),
        "output_sha256": digest,
        "counts": {
            "continents": len(out_map["continents"]),
            "regions": len(out_map["regions"]),
            "tiles": len(out_map["tiles"]),
            "landmarks": len(out_map["landmarks"]),
            "mysteries": len(out_map["mysteries"]),
            "travel_edges": len(out_map["travel_edges"]),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_write": False,
    }
    manifest_path = out_dir / "generation_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    return map_path, manifest_path


def main() -> int:
    ap = argparse.ArgumentParser(description="10JE scratch world-scale generator")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--base-map", default=str(DEFAULT_BASE_MAP))
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "genesis_worldgen"))
    ap.add_argument("--rim", type=int, default=6)
    ap.add_argument("--box", type=int, nargs=4, default=[-100, -100, 100, 100],
                    metavar=("MIN_X", "MIN_Y", "MAX_X", "MAX_Y"))
    args = ap.parse_args()

    base_map_path = Path(args.base_map)
    if not base_map_path.exists():
        print(f"BASE MAP NOT FOUND: {base_map_path}", file=sys.stderr)
        return 1
    base_map = json.loads(base_map_path.read_text(encoding="utf-8"))

    try:
        out_map = generate_world(
            base_map, seed=args.seed, box=tuple(args.box), rim=args.rim,
        )
    except GenerationError as exc:
        print(f"GENERATION FAILED: {exc}", file=sys.stderr)
        return 2

    map_path, manifest_path = write_candidate(
        out_map, Path(args.out), seed=args.seed, base_map_path=base_map_path,
        box=tuple(args.box), rim=args.rim,
    )
    print(f"WORLDGEN=OK tiles={len(out_map['tiles'])} "
          f"landmarks={len(out_map['landmarks'])} "
          f"edges={len(out_map['travel_edges'])}")
    print(f"candidate: {map_path}")
    print(f"manifest:  {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
