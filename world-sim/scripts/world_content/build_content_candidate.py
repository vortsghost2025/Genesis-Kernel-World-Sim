"""Build the world-content candidate: named regions + rare discoveries.

Reads the canonical true map and the live known maps (READ-ONLY), applies:

1. region_namer.name_regions  - wilderness bucket regions become named
   regions ("The Southern Meadows", "The Encircling Sea"...)
2. rare_discoveries.place_discoveries - 8 authored wonders placed far
   from everything known

Then validates with the existing fog validator and writes scratch
evidence (candidate map + manifest) to --out.

NEVER writes to canonical data. Output default: temp/genesis_world_content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import validate_true_map  # noqa: E402
from scripts.world_content.mystery_reveal import MYSTERY_LIBRARY  # noqa: E402
from scripts.world_content.region_namer import name_regions, naming_manifest  # noqa: E402
from scripts.world_content.rare_discoveries import place_discoveries  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-map",
                    default=str(WORLD_SIM / "data" / "world" / "true_map.json"))
    ap.add_argument("--seed", default="genesis_content_10je_v1")
    ap.add_argument("--out", default=str(
        Path(r"S:\KILO-CLEAN-SOURCE\profile\local\Temp\opencode") / "genesis_world_content"))
    args = ap.parse_args()

    base_path = Path(args.base_map)
    if not base_path.exists():
        print(f"BASE MAP NOT FOUND: {base_path}", file=sys.stderr)
        return 1
    base = json.loads(base_path.read_text(encoding="utf-8"))

    # known tiles from the live store (read-only) - wonders keep away
    known: set[str] = set()
    for agent in ("east_adam", "east_eve"):
        p = WORLD_SIM / ".runtime" / "first-pair" / f"known_map_{agent}.json"
        if p.exists():
            km = json.loads(p.read_text(encoding="utf-8"))
            known |= set(km.get("known_tiles", {}).keys())

    named = name_regions(base)
    named_manifest = naming_manifest(base, named)

    placed, discovery_manifest = place_discoveries(
        named, known_tile_ids=known, seed=args.seed)

    verdict = validate_true_map(placed)
    if not verdict.get("ok"):
        print(f"CANDIDATE INVALID: {verdict.get('errors')}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / "true_map.content_candidate.json"
    payload = json.dumps(placed, indent=2, ensure_ascii=False)
    map_path.write_text(payload, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    manifest = {
        "phase": "world-content side branch (scratch-only)",
        "generator": "world-sim/scripts/world_content/build_content_candidate.py",
        "base_map": str(base_path),
        "seed": args.seed,
        "canonical_write": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output": str(map_path),
        "output_sha256": digest,
        "known_tiles_excluded": len(known),
        "region_naming": named_manifest,
        "rare_discoveries": discovery_manifest,
        "mystery_library_kinds": sorted(MYSTERY_LIBRARY.keys()),
        "counts": {
            "tiles": len(placed["tiles"]),
            "regions": len(placed["regions"]),
            "landmarks": len(placed["landmarks"]),
            "mysteries": len(placed["mysteries"]),
            "travel_edges": len(placed["travel_edges"]),
        },
    }
    manifest_path = out_dir / "content_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")
    print(f"CONTENT-CANDIDATE=OK tiles={len(placed['tiles'])} "
          f"regions={len(placed['regions'])} landmarks={len(placed['landmarks'])}")
    print(f"regions named: {named_manifest['tiles_moved_to_named_regions']} tiles moved")
    print(f"discoveries: {discovery_manifest['count']} placed "
          f"(known tiles excluded: {len(known)})")
    print(f"candidate: {map_path}")
    print(f"manifest:  {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
