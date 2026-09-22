"""Phase 10JB-3 — First-pair fog migration script.

Modes:
  --scratch   Run the full migration against a scratch copy. Produces
              the true-map extension candidate and seeds known maps
              from heartbeat history. No canonical writes.

  --manifest  Print the migration manifest (what WOULD change).

  --apply     (FUTURE — requires explicit operator authorization)
              Apply the migration to canonical state.

The true-map extension adds (10IZ §4):
  - region cont_a_first_pair_habitat on continent cont_a
  - three habitat tiles at coordinates (-1,-1), (0,-1), (1,-1)
  - meeting-stone landmark lm_meeting_stone_center
  - internal habitat edges (bidirectional)
  - two initial door edges (bidirectional)

The living-store migration adds (10IZ §5, §6):
  - known_map_east_adam.json (seeded from heartbeat history)
  - known_map_east_eve.json (seeded from heartbeat history)
  - runtime-policy-first-pair-002 (derived topology)

No existing record is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from backend.world.fog_of_war import validate_true_map
from backend.world.first_pair_fog_adapter import (
    derive_topology,
    load_true_map,
    persist_known_map,
    seed_known_map_from_history,
)
from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    load_heartbeat_history,
)

WORLD_SIM = Path(__file__).resolve().parents[1]
DATA_ROOT = WORLD_SIM / "data"
TRUE_MAP_PATH = DATA_ROOT / "world" / "true_map.json"
CANONICAL_STORE = WORLD_SIM / ".runtime" / "first-pair"

HABITAT_REGION_ID = "cont_a_first_pair_habitat"
HABITAT_TILES = [
    {
        "tile_id": "public-start-adam",
        "continent_id": "cont_a",
        "region_id": HABITAT_REGION_ID,
        "coordinates": {"x": -1, "y": -1},
        "terrain": "grassland",
        "biome": "temperate_valley",
        "elevation": 0,
        "water": None,
        "resources": [],
        "hazards": [],
        "landmark_ids": [],
        "blocks_travel": False,
    },
    {
        "tile_id": "public-shared-center",
        "continent_id": "cont_a",
        "region_id": HABITAT_REGION_ID,
        "coordinates": {"x": 0, "y": -1},
        "terrain": "grassland",
        "biome": "temperate_valley",
        "elevation": 0,
        "water": None,
        "resources": [],
        "hazards": [],
        "landmark_ids": ["lm_meeting_stone_center"],
        "blocks_travel": False,
    },
    {
        "tile_id": "public-start-eve",
        "continent_id": "cont_a",
        "region_id": HABITAT_REGION_ID,
        "coordinates": {"x": 1, "y": -1},
        "terrain": "grassland",
        "biome": "temperate_valley",
        "elevation": 0,
        "water": None,
        "resources": [],
        "hazards": [],
        "landmark_ids": [],
        "blocks_travel": False,
    },
]

MEETING_STONE_LANDMARK = {
    "landmark_id": "lm_meeting_stone_center",
    "continent_id": "cont_a",
    "tile_id": "public-shared-center",
    "kind": "meeting_stone",
    "description": (
        "Adam & Eve — founded on contact, cooperation, and shared ground. "
        "The center is our meeting point. Established at heartbeat 7 — "
        "all future travelers welcome."
    ),
}

HABITAT_REGION = {
    "region_id": HABITAT_REGION_ID,
    "continent_id": "cont_a",
    "name": "First Pair Habitat",
}

HABITAT_EDGES = [
    # Internal habitat edges (bidirectional pairs)
    {"from_tile_id": "public-start-adam", "to_tile_id": "public-shared-center", "mode": "walk"},
    {"from_tile_id": "public-shared-center", "to_tile_id": "public-start-adam", "mode": "walk"},
    {"from_tile_id": "public-shared-center", "to_tile_id": "public-start-eve", "mode": "walk"},
    {"from_tile_id": "public-start-eve", "to_tile_id": "public-shared-center", "mode": "walk"},
    # Door A: center ↔ origin_000 (bidirectional)
    {"from_tile_id": "public-shared-center", "to_tile_id": "cont_a_origin_000", "mode": "walk"},
    {"from_tile_id": "cont_a_origin_000", "to_tile_id": "public-shared-center", "mode": "walk"},
    # Door B: eve-start ↔ origin_001 (bidirectional)
    {"from_tile_id": "public-start-eve", "to_tile_id": "cont_a_origin_001", "mode": "walk"},
    {"from_tile_id": "cont_a_origin_001", "to_tile_id": "public-start-eve", "mode": "walk"},
]


def build_extended_true_map() -> dict:
    """Build the true-map extension candidate from the canonical map."""
    original = load_true_map(DATA_ROOT)
    extended = json.loads(json.dumps(original))  # deep copy

    # Add region
    if HABITAT_REGION_ID not in [r["region_id"] for r in extended["regions"]]:
        extended["regions"].append(dict(HABITAT_REGION))

    # Add tiles
    existing_tile_ids = {t["tile_id"] for t in extended["tiles"]}
    for tile in HABITAT_TILES:
        if tile["tile_id"] not in existing_tile_ids:
            extended["tiles"].append(dict(tile))

    # Add meeting stone landmark
    existing_landmark_ids = {l["landmark_id"] for l in extended["landmarks"]}
    if "lm_meeting_stone_center" not in existing_landmark_ids:
        extended["landmarks"].append(dict(MEETING_STONE_LANDMARK))

    # Add travel edges
    existing_edges = {
        (e["from_tile_id"], e["to_tile_id"]) for e in extended["travel_edges"]
    }
    for edge in HABITAT_EDGES:
        key = (edge["from_tile_id"], edge["to_tile_id"])
        if key not in existing_edges:
            extended["travel_edges"].append(dict(edge))

    # Validate
    result = validate_true_map(extended)
    if not result["ok"]:
        raise SystemExit(f"RED: extended true map invalid: {result['errors'][:5]}")

    return extended


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_scratch(scratch_dir: Path) -> dict:
    """Run the full migration against a scratch copy. No canonical writes."""
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True)

    # 1. Copy the canonical store to scratch
    store_scratch = scratch_dir / "first-pair"
    shutil.copytree(CANONICAL_STORE, store_scratch)

    # 2. Hash all original files for byte-preservation proof
    original_hashes = {}
    for p in sorted(store_scratch.rglob("*")):
        if p.is_file():
            original_hashes[str(p.relative_to(store_scratch))] = hash_bytes(p.read_bytes())

    # 3. Build the extended true-map candidate
    extended_map = build_extended_true_map()
    map_path = scratch_dir / "true_map_extended_candidate.json"
    map_path.write_text(json.dumps(extended_map, indent=2), newline="\n")
    map_hash = hash_bytes(map_path.read_bytes())

    # 4. Load heartbeat history from the scratch store
    store = FirstPairPersistenceStore(store_scratch)
    heartbeats = load_heartbeat_history(store)

    # Get actual agent IDs from identity
    identity = json.loads((store_scratch / "identity.json").read_text(encoding="utf-8"))
    adam_agent_id = identity.get("data", {}).get("adam_agent_id", "")
    eve_agent_id = identity.get("data", {}).get("eve_agent_id", "")

    hb_dicts = []
    for hb in heartbeats:
        hb_dicts.append({
            "heartbeat_number": hb.heartbeat_number,
            "action_taken": hb.action_taken if hasattr(hb, "action_taken") else {},
            "world_mutations": [
                {
                    "acting_agent_id": mut.get("acting_agent_id", ""),
                    "action_type": mut.get("action_type", ""),
                    "input": mut.get("input", {}),
                    "outcome": mut.get("outcome", {}),
                }
                for mut in hb.world_mutations
            ],
        })

    # 5. Seed known maps from history (passing actual agent IDs)
    km_adam = seed_known_map_from_history(
        hb_dicts, "east_adam", "public-start-adam", agent_id=adam_agent_id
    )
    km_eve = seed_known_map_from_history(
        hb_dicts, "east_eve", "public-start-eve", agent_id=eve_agent_id
    )
    persist_known_map(store_scratch, "east_adam", km_adam)
    persist_known_map(store_scratch, "east_eve", km_eve)

    # 6. Derive policy-002 topology
    topology = derive_topology(extended_map, [km_adam, km_eve])
    policy_002 = {
        "policy_id": "runtime-policy-first-pair-002",
        "status": "active",
        "movement_grant_ref": "grant-movement-001",
        "topology": topology,
    }

    # 7. Verify byte preservation of all original files
    violation = []
    for rel_path, original_hash in original_hashes.items():
        current = store_scratch / rel_path
        if not current.is_file():
            violation.append(f"DELETED: {rel_path}")
        elif hash_bytes(current.read_bytes()) != original_hash:
            violation.append(f"CHANGED: {rel_path}")

    # 8. Identify additive files
    current_files = {
        str(p.relative_to(store_scratch))
        for p in store_scratch.rglob("*")
        if p.is_file()
    }
    additive_files = sorted(current_files - set(original_hashes.keys()))

    report = {
        "scratch_root": str(scratch_dir),
        "heartbeat_count": len(hb_dicts),
        "original_files": len(original_hashes),
        "additive_files": additive_files,
        "byte_violations": violation,
        "true_map_candidate_sha256": map_hash,
        "known_map_adam_tiles": sorted(km_adam["known_tiles"].keys()),
        "known_map_eve_tiles": sorted(km_eve["known_tiles"].keys()),
        "known_map_adam_landmarks": sorted(km_adam["known_landmarks"].keys()),
        "known_map_eve_landmarks": sorted(km_eve["known_landmarks"].keys()),
        "policy_002_allowed_tiles": topology["allowed_tile_ids"],
        "policy_002_adjacency": {
            t["tile_id"]: t["adjacent"] for t in topology["tiles"]
        },
    }

    report_path = scratch_dir / "migration_report.json"
    report_path.write_text(json.dumps(report, indent=2), newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="First-pair fog migration")
    parser.add_argument("--scratch", type=str, default="", help="Scratch output directory")
    parser.add_argument("--manifest", action="store_true", help="Print migration manifest only")
    args = parser.parse_args()

    if args.manifest:
        extended = build_extended_true_map()
        print(f"Original tiles: {len(load_true_map(DATA_ROOT)['tiles'])}")
        print(f"Extended tiles: {len(extended['tiles'])}")
        print(f"New tiles: {[t['tile_id'] for t in HABITAT_TILES]}")
        print(f"New landmark: {MEETING_STONE_LANDMARK['landmark_id']}")
        print(f"New edges: {len(HABITAT_EDGES)}")
        print(f"New region: {HABITAT_REGION_ID}")
        print("Canonical writes: NONE (manifest mode)")
        return 0

    if args.scratch:
        scratch = Path(args.scratch)
        report = run_scratch(scratch)
        print(json.dumps(report, indent=2))
        if report["byte_violations"]:
            print("RED: BYTE VIOLATIONS DETECTED")
            return 1
        print("GREEN: scratch migration clean — all original files byte-preserved")
        return 0

    print("Specify --scratch <dir> or --manifest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
