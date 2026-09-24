"""Deploy world content (named regions + rare discoveries) to canonical map.

Operator-authorized deployment phase. Applies the pure transforms from
the world-content side branch to the CURRENT canonical true map:

    S:\\Genesis Kernel World Sim\\world-sim\\data\\world\\true_map.json

Transforms (both already tested, both pure/in-memory):

1. scripts.world_content.region_namer.name_regions
   Generated tiles leave the catch-all expanse regions and join named
   regions; authored regions remain byte-exact.
2. scripts.world_content.rare_discoveries.place_discoveries
   Adds the 8 authored wonders as new landmarks (plus landmark_ids / water
   updates on the wonder tiles only), far from everything the pair knows.

Safety gates (all must pass, else abort BEFORE writing):

- every pre-existing region/landmark/mystery/resource/edge record
  survives byte-exact (JSON-value equality);
- every pre-existing tile survives byte-exact EXCEPT generated tiles whose
  only changes are region_id (naming), and wonder tiles whose only
  changes are region_id + landmark_ids (+ water where the wonder IS the
  water);
- no generated tile may be deleted or modified beyond the above;
- validate_true_map() must pass on the final map;
- no mystery record is touched.

Writes exactly one file: the canonical true map. Prints before/after
hashes and a diff summary as deployment evidence.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import validate_true_map  # noqa: E402
from scripts.world_content.region_namer import name_regions, naming_manifest  # noqa: E402
from scripts.world_content.rare_discoveries import place_discoveries  # noqa: E402

CANONICAL_MAP = WORLD_SIM / "data" / "world" / "true_map.json"
SEED = "genesis_content_10je_v1"


class DeployError(Exception):
    pass


def _j(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def embed_gate(before: dict, after: dict) -> None:
    """Abort if anything pre-existing was altered beyond declared deltas."""
    # non-tile collections: byte-exact
    for key in ("continents", "mysteries", "travel_edges", "hazards"):
        if _j(before[key]) != _j(after[key]):
            raise DeployError(f"{key} changed")
    # resources: byte-exact (order + content)
    if _j(before.get("resources", [])) != _j(after.get("resources", [])):
        raise DeployError("resources changed")
    # authored regions: byte-exact; only expanse regions may disappear
    before_regions = {r["region_id"]: r for r in before["regions"]}
    after_regions = {r["region_id"]: r for r in after["regions"]}
    for rid, r in before_regions.items():
        if rid.endswith("_generated_expanse"):
            continue
        if rid not in after_regions or _j(after_regions[rid]) != _j(r):
            raise DeployError(f"authored region altered: {rid}")
    # authored landmarks: byte-exact
    before_lm = {lm["landmark_id"]: lm for lm in before["landmarks"]}
    after_lm = {lm["landmark_id"]: lm for lm in after["landmarks"]}
    for lid, lm in before_lm.items():
        if lid not in after_lm or _j(after_lm[lid]) != _j(lm):
            raise DeployError(f"existing landmark altered: {lid}")
    # tiles: embedded byte-exact; generated tiles may change ONLY:
    #   region_id (always), landmark_ids (wonder tiles), water (lake wonder)
    auth_tiles = {t["tile_id"]: t for t in before["tiles"]}
    gen_changed = 0
    for t in after["tiles"]:
        tid = t["tile_id"]
        orig = auth_tiles.get(tid)
        if orig is None:
            raise DeployError(f"new tile appeared: {tid}")
        if _j(orig) == _j(t):
            continue
        if "_gen_" not in tid:
            raise DeployError(f"authored tile altered: {tid}")
        probe = dict(t)
        probe["region_id"] = orig["region_id"]
        allowed = {"region_id"}
        if probe["landmark_ids"] != orig["landmark_ids"]:
            allowed.add("landmark_ids")
            probe["landmark_ids"] = orig["landmark_ids"]
        if t.get("water") != orig.get("water"):
            if orig.get("water") is None:
                allowed.add("water")
                probe["water"] = None
            else:
                raise DeployError(f"existing water displaced on {tid}")
        if _j(probe) != _j(orig):
            raise DeployError(f"generated tile changed beyond {allowed}: {tid}")
        gen_changed += 1
    if len(after["tiles"]) != len(before["tiles"]):
        raise DeployError("tile count changed")
    return None


def main() -> int:
    if not CANONICAL_MAP.exists():
        print(f"CANONICAL MAP MISSING: {CANONICAL_MAP}", file=sys.stderr)
        return 1

    before_raw = CANONICAL_MAP.read_bytes()
    before_hash = hashlib.sha256(before_raw).hexdigest()
    before = json.loads(before_raw.decode("utf-8"))

    # live known tiles (read-only) - wonders keep away from them
    known: set[str] = set()
    for agent in ("east_adam", "east_eve"):
        p = WORLD_SIM / ".runtime" / "first-pair" / f"known_map_{agent}.json"
        if p.exists():
            known |= set(json.loads(p.read_text(encoding="utf-8"))
                         .get("known_tiles", {}).keys())

    named = name_regions(before)
    named_manifest = naming_manifest(before, named)
    placed, discovery_manifest = place_discoveries(
        named, known_tile_ids=known, seed=SEED)

    embed_gate(before, placed)
    verdict = validate_true_map(placed)
    if not verdict.get("ok"):
        print(f"VALIDATION FAILED: {verdict.get('errors')}", file=sys.stderr)
        return 2

    payload = json.dumps(placed, indent=2, ensure_ascii=False)
    after_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    CANONICAL_MAP.write_text(payload, encoding="utf-8", newline="\n")

    print("DEPLOY=OK")
    print(f"before_sha256: {before_hash}")
    print(f"after_sha256:  {after_hash}")
    print(f"tiles: {len(before['tiles'])} -> {len(placed['tiles'])}")
    print(f"regions: {len(before['regions'])} -> {len(placed['regions'])}"
          f" ({named_manifest['tiles_moved_to_named_regions']} gen tiles renamed)")
    print(f"landmarks: {len(before['landmarks'])} -> {len(placed['landmarks'])}"
          f" (+{discovery_manifest['count']} wonders)")
    print(f"resources: {len(before.get('resources', []))} -> {len(placed.get('resources', []))}")
    print(f"edges: {len(before['travel_edges'])} -> {len(placed['travel_edges'])}")
    print(f"known tiles avoided: {len(known)}")
    for p in discovery_manifest["placements"]:
        print(f"  wonder {p['landmark_id']} -> {p['tile_id']}"
              f" @({p['coordinates']['x']},{p['coordinates']['y']}) [{p['terrain']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
