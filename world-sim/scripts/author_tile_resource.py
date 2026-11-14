"""Author one resource onto one tile of the canonical true map.

Operator-authorized, 2026-11-14, for a specific live finding rather than as a
general licence to edit world data:

    the live audit (scripts/audit_tile_resources.py) went red on
    `cont_a_gen_-43_5:barren` -- east_adam occupies a temperate hill that was
    authored with NO resources at all, while the tile beside it
    (cont_a_gen_-43_6) carries stone 5 and clay 2. The operator chose to fix
    the world rather than record the defect in the accepted-findings register.

`data/world/true_map.json` is gitignored and generated, so this edit is a local
world-data change: nothing here is committed. The script exists so the fix is
reproducible after a regeneration, and so the change is guarded rather than
hand-written.

Safety gates (all must pass, else abort BEFORE writing):

  * `validate_true_map()` must pass on the result;
  * every pre-existing resource record must survive byte-exact (JSON value
    equality) and in order -- the only permitted addition is the new record;
  * every pre-existing tile must survive byte-exact EXCEPT the target tile,
    whose only permitted change is its `resources` list gaining the kind;
  * nothing else in the map may change at all.

Writes exactly one file (atomically, LF only) and prints before/after hashes
and a diff summary as deployment evidence. `--apply` is required to write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.fog_of_war import validate_true_map  # noqa: E402

CANONICAL_MAP = WORLD_SIM / "data" / "world" / "true_map.json"


class AuthorError(Exception):
    pass


def _j(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def resource_id_for(tile_id: str, kind: str) -> str:
    return f"res_{tile_id}_{kind}"


def author_tile_resource(
    true_map: dict,
    tile_id: str,
    kind: str,
    amount: int,
    renewable: bool = False,
) -> tuple[dict, dict]:
    """Return (new_map, summary). Pure: never mutates its input.

    Idempotent: if the record already exists with the same kind, the map is
    returned unchanged and the summary says so.
    """
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise AuthorError(f"amount must be a positive int, got {amount!r}")
    if not str(kind).strip():
        raise AuthorError("kind must be a non-empty string")

    tiles = true_map.get("tiles") or []
    target = next((t for t in tiles if t.get("tile_id") == tile_id), None)
    if target is None:
        raise AuthorError(f"tile not in true map: {tile_id}")

    res_id = resource_id_for(tile_id, kind)
    existing = {r.get("resource_id") for r in (true_map.get("resources") or [])}
    if res_id in existing:
        return true_map, {
            "tile_id": tile_id,
            "kind": kind,
            "resource_id": res_id,
            "changed": False,
            "reason": "already authored",
        }

    if kind in (target.get("resources") or []):
        # the tile already declares the kind but has no record: that is a
        # different, pre-existing inconsistency -- refuse rather than guess.
        raise AuthorError(
            f"{tile_id} already lists {kind!r} but has no resource record; "
            "refusing to author a duplicate")

    new_map = json.loads(json.dumps(true_map))  # deep copy, no shared refs
    if new_map.get("resources") is None:
        new_map["resources"] = []
    new_map["resources"].append({
        "resource_id": res_id,
        "kind": kind,
        "amount": amount,
        "renewable": bool(renewable),
        "tile_id": tile_id,
    })
    for t in new_map["tiles"]:
        if t.get("tile_id") == tile_id:
            t["resources"] = list(t.get("resources") or []) + [kind]
            break

    return new_map, {
        "tile_id": tile_id,
        "kind": kind,
        "amount": amount,
        "renewable": bool(renewable),
        "resource_id": res_id,
        "changed": True,
    }


def embed_gate(before: dict, after: dict, summary: dict) -> None:
    """Abort if anything beyond the declared single addition changed."""
    if not summary.get("changed"):
        return
    res_id = summary["resource_id"]

    before_res = before.get("resources") or []
    after_res = after.get("resources") or []
    stripped = [r for r in after_res if r.get("resource_id") != res_id]
    if _j(stripped) != _j(before_res):
        raise AuthorError("pre-existing resource records were altered")
    added = [r for r in after_res if r.get("resource_id") == res_id]
    if len(added) != 1:
        raise AuthorError(f"expected exactly one added record, got {len(added)}")

    for key in ("continents", "regions", "landmarks", "hazards",
                "mysteries", "travel_edges"):
        if key in before and _j(before.get(key)) != _j(after.get(key)):
            raise AuthorError(f"{key} changed")

    before_tiles = {t.get("tile_id"): t for t in (before.get("tiles") or [])}
    after_tiles = {t.get("tile_id"): t for t in (after.get("tiles") or [])}
    if set(before_tiles) != set(after_tiles):
        raise AuthorError("the tile set changed")
    changed_tiles = [tid for tid in before_tiles
                     if _j(before_tiles[tid]) != _j(after_tiles[tid])]
    if changed_tiles != [summary["tile_id"]]:
        raise AuthorError(f"tiles changed beyond the target: {changed_tiles}")
    bt, at = before_tiles[summary["tile_id"]], after_tiles[summary["tile_id"]]
    b_rest = {k: v for k, v in bt.items() if k != "resources"}
    a_rest = {k: v for k, v in at.items() if k != "resources"}
    if _j(b_rest) != _j(a_rest):
        raise AuthorError("the target tile changed beyond its resources list")
    want = list(bt.get("resources") or []) + [summary["kind"]]
    if (at.get("resources") or []) != want:
        raise AuthorError("the target tile's resources list is not before+kind")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tile", required=True, help="tile_id to author onto")
    parser.add_argument("--kind", required=True, help="resource kind, e.g. stone")
    parser.add_argument("--amount", type=int, required=True)
    parser.add_argument("--renewable", action="store_true")
    parser.add_argument("--apply", action="store_true",
                        help="write the change (otherwise dry-run)")
    parser.add_argument("--map", default=str(CANONICAL_MAP))
    args = parser.parse_args()

    path = Path(args.map)
    if not path.is_file():
        print(f"ERROR canonical map not found: {path}")
        return 1
    before = json.loads(path.read_text(encoding="utf-8"))
    before_sha = _sha256(path)

    try:
        after, summary = author_tile_resource(
            before, args.tile, args.kind, args.amount, args.renewable)
        embed_gate(before, after, summary)
    except AuthorError as exc:
        print(f"ABORT: {exc}")
        return 1

    if not summary.get("changed"):
        print(f"no change: {summary['reason']} ({summary['resource_id']})")
        return 0

    validation = validate_true_map(after)
    if not validation.get("ok"):
        print(f"ABORT: validate_true_map failed: {validation.get('errors')}")
        return 1

    print(f"tile      : {summary['tile_id']}")
    print(f"adding    : {summary['kind']} x{summary['amount']}"
          f" (renewable={summary['renewable']})")
    print(f"before    : {before_sha}")
    print("gates     : resource records byte-exact, tiles byte-exact except "
          "the target, true map schema valid")

    if not args.apply:
        print("\nDRY RUN - nothing written. Re-run with --apply to write.")
        return 0

    backup = path.with_name(
        f"{path.name}.pre-10qq-backup")
    backup.write_bytes(path.read_bytes())
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(after, fh, indent=2)
    tmp.replace(path)
    print(f"after     : {_sha256(path)}")
    print(f"backup    : {backup.name}")
    print(f"WROTE     : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
