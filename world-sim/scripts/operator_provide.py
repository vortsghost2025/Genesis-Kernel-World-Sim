"""The operator's hand: leave a provision on an agent's tile.

WHY THIS EXISTS

The operator desk answered every request matching "provide|give me|feed me|
send me|bring me" with a hard-coded line: "The operator does not hand out
anything." Measured 2026-11-13, the agents had asked for water, food, clay
and emergency provision 100+ times across both lanes while three of four sat
collapsed at thirst 100, and the door was bolted by policy rather than by
physics.

Operator, 2026-11-13: "the agent in your spot is responsible to help them/
teach them/respond them/fix issues. you are their god. i am the viewer."

HOW IT WORKS, AND WHY IT QUEUES

This script does NOT write world_state.json. It could not: a heartbeat that
began before the write saves its own copy when it persists, and the provision
vanishes - measured the same day, eight provisions written straight into the
live store were gone by the next completed heartbeat.

So it ENQUEUES into .runtime/<pair>/operator_provisions_pending.json and the
runtime applies the queue during its own read-modify-write
(`_apply_operator_provision_queue`), idempotent by object_id. The provision
becomes a real object on the target's tile, which is where the world's own
rescue paths read from: `_downed_tile_drink` reads contents.fresh_water,
`_downed_tile_feed` reads materials, and a standing agent can drink or extract
with ordinary actions. It carries creator_agent_id "the operator" and
provenance "operator-provision", so the world's history says a human hand put
it there.

Every act is appended to .runtime/<pair>/operator_provisions.json, and the
amount is capped per act so this cannot become an unbounded tap.

Usage:
    python world-sim/scripts/operator_provide.py --pair east --to east_adam \
        --kind fresh_water --amount 3 --reason "collapsed at thirst 100"
    python world-sim/scripts/operator_provide.py --pair both --to all \
        --kind fresh_water --amount 3 --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))

PAIRS = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
MAX_PER_ACT = 5
DRINKABLE = "fresh_water"


def _occ(pair_dir: Path) -> tuple[dict, int]:
    raw = json.loads((pair_dir / "world_state.json").read_text(encoding="utf-8"))
    state = raw.get("data", raw)
    return (state.get("tile_occupancy") or {}), int(state.get("tick") or 0)


def enqueue(pair: str, to: str, kind: str, amount: int, reason: str,
            apply: bool) -> dict:
    pair_dir = PAIRS[pair]
    occ, tick = _occ(pair_dir)
    targets = dict(occ) if to == "all" else ({to: occ[to]} if to in occ else {})
    if not targets:
        return {"pair": pair, "error": f"unknown target {to!r}"}

    obj_ids = [k for k in json.loads(
        (pair_dir / "world_state.json").read_text(encoding="utf-8")
    ).get("data", {}).get("public_objects", {}) if "operator-provision" in k]

    acts = []
    for i, (agent_ref, tile) in enumerate(sorted(targets.items())):
        obj_id = f"operator-provision-hb{tick}-{kind}-{i + 1}"
        suffix = 1
        while obj_id in obj_ids or any(a["object_id"] == obj_id for a in acts):
            suffix += 1
            obj_id = f"operator-provision-hb{tick}-{kind}-{i + 1}-{suffix}"
        acts.append({"object_id": obj_id, "agent_ref": agent_ref,
                     "tile_id": tile, "kind": kind, "amount": int(amount),
                     "reason": reason})

    result = {"pair": pair, "tick": tick, "kind": kind, "amount": amount,
              "acts": acts, "queued": bool(apply)}
    if not apply:
        return result

    queue_path = pair_dir / "operator_provisions_pending.json"
    existing = []
    if queue_path.is_file():
        try:
            existing = json.loads(queue_path.read_text(encoding="utf-8")).get("acts", [])
        except Exception:
            existing = []
    existing.extend(acts)
    queue_path.write_text(json.dumps({"acts": existing}, indent=1),
                          encoding="utf-8", newline="\n")

    ledger = pair_dir / "operator_provisions.json"
    logged = []
    if ledger.is_file():
        try:
            logged = json.loads(ledger.read_text(encoding="utf-8")).get("acts", [])
        except Exception:
            logged = []
    logged.append({"at_utc": datetime.now(timezone.utc).isoformat(),
                   "tick": tick, "kind": kind, "amount": int(amount),
                   "reason": reason, "acts": acts})
    ledger.write_text(json.dumps({"acts": logged}, indent=1),
                      encoding="utf-8", newline="\n")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", choices=["east", "west", "both"], required=True)
    ap.add_argument("--to", required=True,
                    help="an agent_ref (east_adam, west_eve, ...) or 'all'")
    ap.add_argument("--kind", required=True,
                    help="a resource kind, e.g. fresh_water or edible_roots")
    ap.add_argument("--amount", type=int, default=3)
    ap.add_argument("--reason", default="")
    ap.add_argument("--apply", action="store_true",
                    help="without this it is a dry run and nothing is queued")
    args = ap.parse_args()

    if args.amount < 1 or args.amount > MAX_PER_ACT:
        print(f"REFUSED: --amount must be 1..{MAX_PER_ACT} "
              f"(this is a hand, not a tap)")
        return 2

    pairs = ["east", "west"] if args.pair == "both" else [args.pair]
    for name in pairs:
        res = enqueue(name, args.to, args.kind, args.amount, args.reason,
                      args.apply)
        if "error" in res:
            print(f"{name}: {res['error']}")
            continue
        state = "QUEUED (applied by the next heartbeat)" if res["queued"] else "DRY-RUN"
        print(f"{name}: {state} tick={res['tick']}")
        for a in res["acts"]:
            print(f"    {a['agent_ref']} at {a['tile_id']} -> {a['object_id']} "
                  f"({a['amount']} x {a['kind']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
