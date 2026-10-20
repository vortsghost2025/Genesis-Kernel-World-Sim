"""Seed diverse foraging resources onto the true world map.

Adds the newly introduced food types into their native biomes:
- wild_apples: temperate_forest, temperate_valley (orchards/groves)
- nuts: highland, temperate_hills, dense_woodland (hazelnut/walnut trees)
- wild_grain: temperate_valley (wild barley/emmer stands in meadows)
- honeycomb: dense_woodland, temperate_forest (bee colonies in tree hollows)

Maintains deterministic distribution from coordinates and map seed.
Ensures cont_a_gen_0_-3 (East Adam's current highland post) carries nuts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import validate_true_map


def seed_resources_in_map(true_map: dict) -> tuple[dict, Counter, int]:
    seed_str = str(true_map.get("seed", "genesis-world-seed"))
    existing_res_ids = {r["resource_id"] for r in true_map.get("resources", [])}

    new_resources = []
    added_counts = Counter()

    for t in true_map["tiles"]:
        t_id = t["tile_id"]
        biome = t.get("biome")
        coords = t.get("coordinates", {})
        x, y = coords.get("x", 0), coords.get("y", 0)
        current_res = t.get("resources", [])

        # Deterministic hash roll 0..999
        h_val = int(hashlib.sha256(f"{seed_str}_{x}_{y}".encode("utf-8")).hexdigest()[:6], 16) % 1000

        kinds_to_add: list[tuple[str, int]] = []

        # 1. Nuts: highland, temperate_hills, dense_woodland (~6% of tiles, or specifically cont_a_gen_0_-3)
        if t_id == "cont_a_gen_0_-3" or (biome in ("highland", "temperate_hills", "dense_woodland") and h_val < 60):
            if "nuts" not in current_res:
                kinds_to_add.append(("nuts", 2))

        # 2. Wild Apples: temperate_forest, temperate_valley (~6% of tiles, h_val 60..119)
        if biome in ("temperate_forest", "temperate_valley") and 60 <= h_val < 120:
            if "wild_apples" not in current_res:
                kinds_to_add.append(("wild_apples", 3))

        # 3. Wild Grain: temperate_valley (~7% of tiles, h_val 120..189)
        if biome == "temperate_valley" and 120 <= h_val < 190:
            if "wild_grain" not in current_res:
                kinds_to_add.append(("wild_grain", 3))

        # 4. Honeycomb: dense_woodland, temperate_forest (~2.5% of tiles, h_val 190..214)
        if biome in ("dense_woodland", "temperate_forest") and 190 <= h_val < 215:
            if "honeycomb" not in current_res:
                kinds_to_add.append(("honeycomb", 1))

        for kind, amount in kinds_to_add:
            res_id = f"res_{t_id}_{kind}"
            if res_id not in existing_res_ids:
                new_resources.append({
                    "resource_id": res_id,
                    "kind": kind,
                    "amount": amount,
                    "renewable": True,
                    "tile_id": t_id,
                })
                existing_res_ids.add(res_id)
                current_res.append(kind)
                added_counts[kind] += 1

    true_map["resources"].extend(new_resources)
    return true_map, added_counts, len(new_resources)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed diverse foraging resources onto true_map.json")
    parser.add_argument("--apply", action="store_true", help="Apply changes directly to true_map.json")
    args = parser.parse_args()

    true_map_path = WORLD_SIM / "data" / "world" / "true_map.json"
    with open(true_map_path, "r", encoding="utf-8") as f:
        tm = json.load(f)

    print(f"Loaded true_map: {len(tm.get('tiles', []))} tiles, {len(tm.get('resources', []))} resources")

    updated_tm, counts, total = seed_resources_in_map(tm)
    print(f"New resources planned: {total}")
    for kind, count in sorted(counts.items()):
        print(f"  {kind}: {count} tiles")

    val = validate_true_map(updated_tm)
    if not val["ok"]:
        print(f"Validation FAILED: {val.get('errors')}")
        return 1
    print("Validation: OK (true map schema compliant)")

    if args.apply:
        temp_path = true_map_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(updated_tm, f, indent=2)
        temp_path.replace(true_map_path)
        print(f"Successfully applied and wrote to {true_map_path}")
    else:
        print("Dry run completed. Pass --apply to write to true_map.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
