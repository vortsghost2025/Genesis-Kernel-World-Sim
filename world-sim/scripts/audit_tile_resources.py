"""Tile resource audit - can an agent actually acquire anything where it stands?

Standing guard from §3.4 of docs/epistemic_pressure_spec.md.

Two pressure phases were designed by reasoning about what agents would
find interesting, and both were wrong in ways this one table would have
shown. east_adam's home tile yields exactly one wild_berry per
heartbeat; the consumption rule removed exactly one per heartbeat. His
food was pinned at 0 for over 100 heartbeats and he reported it as a
bug at HB797. The East pair's 0% build rate was not apathy - it was two
agents correctly refusing to act on a board where action was impossible,
and it was read as "the world asks nothing of them."

READ-ONLY. This tool never writes to the true map, a store, or any
runtime state. It answers one question per occupied tile and prints it.

Usage:
    python world-sim/scripts/audit_tile_resources.py
    python world-sim/scripts/audit_tile_resources.py --consumption 1
    python world-sim/scripts/audit_tile_resources.py --tile cont_b_origin_001
    python world-sim/scripts/audit_tile_resources.py --json OUT
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
TRUE_MAP = WORLD_SIM / "data" / "world" / "true_map.json"
RUNTIME_ROOT = WORLD_SIM / ".runtime"
PAIRS = ("first-pair", "first-pair-west")

# Findings the operator has knowingly accepted. Keyed "<tile>:<status>".
# Adding a resource to a barren tile means removing its entry here, which
# is deliberate: the guard then fails until a human updates the record.
ACCEPTED_FINDINGS = {
    "public-shared-center:barren": (
        "operator accepted 2026-09-26: east_eve's post is a meeting "
        "point, not a resource site. Her gather attempts there fail "
        "truthfully and that is the correct world. Changing this means "
        "authoring resources onto a public tile (world-sim/data, which "
        "requires explicit operator authorization)."
    ),
    # "west-start-adam:barren" lived here from 2026-09-26 until 2026-11-14.
    # It is now FIXED rather than accepted: the operator authorized authoring a
    # resource, and scripts/author_tile_resource.py put stone x2 on the tile,
    # matching its sibling origin west-start-eve. Deleting the entry is the
    # deliberate act described above -- if that tile ever goes barren again,
    # the guard fails until a human looks at it.
}


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def tile_offer_health(resources, consumption_per_tick=0) -> dict:
    """Can an agent standing on this tile acquire anything net?

    resources: the resource records authored for one tile.
    consumption_per_tick: what the shipped physics removes each
        heartbeat. 0 once the metabolism is retired.

    Fail-closed on malformed input: a malformed record is REPORTED, never
    silently skipped, because the whole point of this tool is that a
    silent skip is how a deadlock hides.
    """
    consumption = consumption_per_tick if _is_int(consumption_per_tick) else 0
    if consumption < 0:
        consumption = 0

    findings: list[str] = []
    malformed = 0
    total_yield = 0
    kinds: list[str] = []

    for rec in resources or []:
        if not isinstance(rec, dict):
            malformed += 1
            continue
        kind = rec.get("kind")
        amount = rec.get("amount")
        if not isinstance(kind, str) or not kind.strip() or not _is_int(amount):
            malformed += 1
            continue
        if amount > 0:
            total_yield += amount
            kinds.append(kind)

    if malformed:
        findings.append(
            f"{malformed} malformed resource record(s) - reported, not skipped")
        status = "malformed"
    elif total_yield <= 0:
        findings.append("no resources available on this tile")
        status = "barren"
    else:
        net = total_yield - consumption
        if net <= 0:
            findings.append(
                f"yield {total_yield}/heartbeat is exactly cancelled by "
                f"consumption {consumption}/heartbeat - an agent can never "
                f"accumulate here (net {net})")
            status = "deadlock"
        else:
            status = "healthy"
        return {
            "status": status,
            "net_gain": net,
            "total_yield": total_yield,
            "consumption": consumption,
            "kinds": sorted(set(kinds)),
            "findings": findings,
        }

    return {
        "status": status,
        "net_gain": total_yield - consumption,
        "total_yield": total_yield,
        "consumption": consumption,
        "kinds": sorted(set(kinds)),
        "findings": findings,
    }


def audit_true_map(true_map, occupy, consumption_per_tick=0, accepted=None,
                   transient=None) -> dict:
    """Audit each requested tile against the authored map.

    `transient` names tiles occupied only by a DOWNED agent (see
    `occupied_tiles_by_state`). A non-healthy transient tile is REPORTED in
    `tiles` with its status, but it is not counted as blocking and needs no
    accepted-findings entry, because a crawling body is not deadlocked by the
    tile its body is crossing.
    """
    accepted = accepted or {}
    occupy_set = set(occupy or ())
    transient = set(transient or ())
    # Defence in depth: if a caller ever lists a tile as BOTH settled and
    # transient, the settled reading wins. A guard must err toward red.
    transient -= occupy_set
    by_tile: dict[str, list] = {}
    for rec in (true_map or {}).get("resources", []) or []:
        if isinstance(rec, dict) and isinstance(rec.get("tile_id"), str):
            by_tile.setdefault(rec["tile_id"], []).append(rec)

    tiles = []
    blocking = 0
    accepted_count = 0
    transient_count = 0
    for tile_id in sorted(occupy_set | transient):
        health = tile_offer_health(
            by_tile.get(tile_id, []), consumption_per_tick)
        key = f"{tile_id}:{health['status']}"
        entry = {
            "tile_id": tile_id,
            "status": health["status"],
            "net_gain": health["net_gain"],
            "kinds": health["kinds"],
            "findings": health["findings"],
        }
        if health["status"] != "healthy":
            if key in accepted:
                entry["accepted"] = accepted[key]
                accepted_count += 1
            elif tile_id in transient:
                entry["transient"] = ("occupied only by a collapsed body, "
                                      "which crawls on; reported, not blocking")
                transient_count += 1
            else:
                blocking += 1
        tiles.append(entry)

    return {
        "consumption_per_tick": consumption_per_tick,
        "tiles": tiles,
        "blocking": blocking,
        "accepted_count": accepted_count,
        "transient_count": transient_count,
    }


def occupied_tiles() -> list[str]:
    """Every tile an agent can currently be standing on, both pairs."""
    settled, transient = occupied_tiles_by_state()
    return sorted(set(settled) | set(transient))


def occupied_tiles_by_state() -> tuple[list[str], list[str]]:
    """Occupied tiles, split into (settled, transient).

    Phase 10QX. Before 10QI a collapsed body stayed where it fell, so an
    "occupied tile" meant a place an agent lives and must be able to gather
    from. 10QI gave a collapsed body its legs -- it CRAWLS one tile per
    heartbeat -- so a downed agent's tile is where its body is lying in
    transit. It is not deadlocked there: it can crawl off, and its survival
    runs through the crawl and the tile's auto-feed.

    Measured 2026-11-14: 116 of the 652 tiles in the west explored box carry no
    resources at all, so treating every tile a crawling body crossed as a
    blocking finding was a treadmill of one-tile fixes. A transient tile is
    still REPORTED (see `render_audit`), never hidden -- the same shape the
    accepted-findings register already uses.

    A tile is transient only when EVERY agent on it is downed, and it is not a
    pair's authored habitat tile: a standing agent still makes it settled.
    """
    occupied: dict[str, set[str]] = {}
    standing: dict[str, int] = {}
    for pair in PAIRS:
        path = RUNTIME_ROOT / pair / "world_state.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
        except (OSError, json.JSONDecodeError):
            continue
        vitals = data.get("vitals") or {}
        for ref, tile in (data.get("tile_occupancy") or {}).items():
            if not isinstance(tile, str):
                continue
            occupied.setdefault(tile, set()).add(ref)
            if not (vitals.get(ref) or {}).get("downed"):
                standing[tile] = standing.get(tile, 0) + 1

    habitat_tiles = set()
    for pair in PAIRS:
        path = RUNTIME_ROOT / pair / "world_state.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8")).get("data", {})
        except (OSError, json.JSONDecodeError):
            continue
        habitat = data.get("habitat") or {}
        habitat_tiles.update(
            t for t in (habitat.get("starting_tile_ids") or {}).values()
            if isinstance(t, str))

    settled, transient = [], []
    for tile in sorted(occupied):
        if standing.get(tile) or tile in habitat_tiles:
            settled.append(tile)
        else:
            transient.append(tile)
    settled = sorted(set(settled) | habitat_tiles)
    return settled, transient


def render_audit(result: dict) -> str:
    lines = [
        "TILE RESOURCE AUDIT "
        f"(consumption {result['consumption_per_tick']}/heartbeat)",
        "-" * 60,
    ]
    for tile in result["tiles"]:
        if tile["status"] == "healthy":
            mark = "OK "
        elif tile.get("accepted") or tile.get("transient"):
            mark = "-- "
        else:
            mark = "!! "
        lines.append(
            f"{mark}{tile['tile_id']:<34} {tile['status']:<9} "
            f"net {tile['net_gain']:>4}  {','.join(tile['kinds']) or '-'}"
        )
        for finding in tile["findings"]:
            lines.append(f"    - {finding}")
        if tile.get("accepted"):
            lines.append(f"    (accepted: {tile['accepted']})")
        if tile.get("transient"):
            lines.append(f"    (transient: {tile['transient']})")
    lines.append("-" * 60)
    lines.append(
        f"blocking findings: {result['blocking']} | "
        f"operator-accepted: {result['accepted_count']} | "
        f"transient (collapsed body crawling): {result.get('transient_count', 0)}"
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--consumption", type=int, default=0,
                    help="what the shipped physics removes per heartbeat")
    ap.add_argument("--tile", action="append", default=[],
                    help="audit this tile (repeatable); default: occupied tiles")
    ap.add_argument("--map", default=str(TRUE_MAP))
    ap.add_argument("--json", default="", help="also write a machine-readable copy")
    args = ap.parse_args()

    if not Path(args.map).is_file():
        print(f"AUDIT_ERROR: true map not found: {args.map}")
        return 1
    true_map = json.loads(Path(args.map).read_text(encoding="utf-8"))
    if args.tile:
        occupy, transient = args.tile, []
    else:
        occupy, transient = occupied_tiles_by_state()
    result = audit_true_map(
        true_map, occupy, args.consumption, accepted=ACCEPTED_FINDINGS,
        transient=transient)
    print(render_audit(result))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
        print(f"AUDIT_JSON={out}")
    return 1 if result["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
