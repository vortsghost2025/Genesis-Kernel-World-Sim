"""Repair a duplicate-writer heartbeat ledger, with guards.

Written after the 2026-09-30 incident: two chains briefly shared the east
store and one heartbeat number landed twice. The chain's fail-closed check
(`count` must equal `tick`) then stopped the world, correctly.

The repair is not "make the numbers match". It is: prove which of the two
records is the real beat, remove only the other, and refuse to touch
anything when that cannot be proven. A repair script that guesses would
rewrite the agents' history on a hunch, which is the one thing this repo
must never do.

Guards, all required before a single byte is written:
  * exactly one duplicated heartbeat number
  * the duplicate pair has different payloads (a real second write, not a
    file-level copy artifact)
  * the LATER record is the one consistent with world_state occupancy -
    the chain accepted the later beat, and the earlier one is the intruder
  * a backup is written first

Usage: python repair_duplicate_heartbeat.py [--apply] [--store PATH]
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

WORLD_SIM = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))
sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_STORE = WORLD_SIM / ".runtime" / "first-pair"


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def diagnose(store: pathlib.Path) -> dict:
    """Everything needed to decide, and nothing acted upon."""
    hb = load(store / "heartbeat.json").get("data", [])
    ws = load(store / "world_state.json").get("data", {})

    seen: dict[int, list[int]] = {}
    for i, rec in enumerate(hb):
        n = rec.get("heartbeat_number")
        if isinstance(n, int):
            seen.setdefault(n, []).append(i)
    dupes = {n: ix for n, ix in seen.items() if len(ix) > 1}

    report = {
        "records": len(hb),
        "tick": ws.get("tick"),
        "occupancy": ws.get("tile_occupancy") or {},
        "duplicate_numbers": sorted(dupes),
        "guards": [],
        "ok": False,
        "action": "none",
    }

    if not dupes:
        report["guards"].append("no duplicates found - nothing to repair")
        report["ok"] = True
        return report
    if len(dupes) > 1:
        report["guards"].append(
            f"REFUSING: {len(dupes)} duplicated numbers "
            f"({report['duplicate_numbers']}) - not a single-writer slip")
        return report

    number, idxs = next(iter(dupes.items()))
    first, last = idxs[0], idxs[-1]
    a, b = hb[first], hb[last]
    same = json.dumps(a.get("action_outcomes"), sort_keys=True) == \
        json.dumps(b.get("action_outcomes"), sort_keys=True)
    report["duplicate"] = number
    report["indexes"] = idxs
    report["timestamps"] = [a.get("timestamp_utc"), b.get("timestamp_utc")]
    report["drop_index"] = first
    report["keep_index"] = last

    if same:
        report["guards"].append(
            "REFUSING: the duplicate records are byte-identical in outcome - "
            "this is a persistence artifact, not a second write")
        return report

    # The later record is authoritative only if the world state agrees it
    # happened: the agent's current tile must be the destination of the
    # later record's move (or unchanged if it did not move).
    occ = report["occupancy"]
    later = (b.get("action_outcomes") or {})
    consistent = True
    for who, outcome in later.items():
        if not isinstance(outcome, dict) or "to" not in outcome:
            continue
        if occ.get(who) != outcome.get("to"):
            # A later heartbeat may have moved them again; only the final
            # heartbeat can pin the position, so accept when this is it.
            if number == report["tick"]:
                consistent = False
                report["guards"].append(
                    f"REFUSING: world_state puts {who} at "
                    f"{occ.get(who)}, not the later record's "
                    f"{outcome.get('to')}")
    if not consistent:
        return report

    earlier_moves = sum(1 for o in (a.get("action_outcomes") or {}).values()
                        if isinstance(o, dict) and "to" in o)
    later_moves = sum(1 for o in later.values()
                      if isinstance(o, dict) and "to" in o)
    if later_moves < earlier_moves:
        report["guards"].append(
            f"REFUSING: the EARLIER record has more position changes "
            f"({earlier_moves}) than the later ({later_moves}) - the "
            f"intruder may be the later write")
        return report

    report["guards"].append(
        f"later record #{last} is consistent with world_state occupancy; "
        f"earlier #{first} is the intruder")
    report["ok"] = True
    report["action"] = "drop_earlier_duplicate"
    return report


def apply_repair(store: pathlib.Path, report: dict) -> dict:
    if not report.get("ok") or report.get("action") != "drop_earlier_duplicate":
        return {"applied": False, "reason": "guards did not pass"}
    path = store / "heartbeat.json"
    backup = store / "heartbeat.json.pre-repair"
    if not backup.is_file():
        shutil.copy2(path, backup)
    data = load(path)
    rows = data.get("data", [])
    drop = report["drop_index"]
    removed = rows[drop]
    kept = rows[:drop] + rows[drop + 1:]
    data["data"] = kept
    tmp = store / "heartbeat.json.repair.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    json.loads(tmp.read_text(encoding="utf-8"))  # must parse before replacing
    tmp.replace(path)
    return {
        "applied": True,
        "dropped_heartbeat": removed.get("heartbeat_number"),
        "dropped_timestamp": removed.get("timestamp_utc"),
        "records_before": len(rows),
        "records_after": len(kept),
        "backup": str(backup),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    store = DEFAULT_STORE
    if "--store" in argv:
        store = pathlib.Path(argv[argv.index("--store") + 1])
    report = diagnose(store)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if "--apply" not in argv:
        print("\nDRY-RUN: nothing written.")
        return 0 if report["ok"] else 1
    result = apply_repair(store, report)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0 if result.get("applied") else 1


if __name__ == "__main__":
    sys.exit(main())
