"""Arc census export - the evidence for what the world did, in the repo.

Every claim this project makes about agent behavior is a measurement,
and a measurement that lives only in a conversation is not auditable.
This turns the canonical stores into a committed record: one markdown
file per arc, with the numbers, so "the deadlock was fixed" or "the
retirement did nothing" can be checked later by anyone reading the
history rather than taking anyone's word for it.

READ-ONLY with respect to the world: it never writes to a store, the
true map, or any runtime state. Its only output is a file under
docs/arcs/.

Census contents, per arc:
  * the two deadlock measures (food ledger, known_tiles growth) that the
    epistemic spec named as decisive
  * action census per agent, and the build objects they made, with the
    stated purpose each agent gave them
  * every rejection reason, which is where a rigged board shows up
  * questions asked and whether anything was ever heard
  * operator messages sent

Usage:
    python world-sim/scripts/export_arc_census.py --from 801 --to 900
    python world-sim/scripts/export_arc_census.py --from 701 --to 800 --dry-run
    python world-sim/scripts/export_arc_census.py --index
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"
ARCS_DIR = WORLD_SIM / "docs" / "arcs"
INDEX_PATH = ARCS_DIR / "README.md"
SCRATCH = WORLD_SIM / ".scratch" / "arcs"

PAIRS = {
    "east": RUNTIME_ROOT / "first-pair",
    "west": RUNTIME_ROOT / "first-pair-west",
}

FOOD_KINDS = ("wild_berries", "mushrooms", "edible_roots", "fish", "shellfish")

# Phrases that mark an object as inventory housekeeping rather than
# something the agent wanted. Counted, not judged: the whole point of
# the 5-of-5 finding in the pressure spec was that the agents SAID this.
_HOUSEKEEPING = (
    "overcapacity",
    "over capacity",
    "excess",
    "reduce goods",
    "free goods",
    "free up",
    "capacity",
    "clear inventory",
    "reduce inventory",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def food_units(holdings) -> int:
    if not isinstance(holdings, dict):
        return 0
    return sum(
        amount for kind, amount in holdings.items()
        if kind in FOOD_KINDS
        and isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
    )


def goods_units(holdings) -> int:
    if not isinstance(holdings, dict):
        return 0
    return sum(
        amount for kind, amount in holdings.items()
        if kind not in FOOD_KINDS
        and isinstance(amount, int) and not isinstance(amount, bool) and amount > 0
    )


def is_housekeeping(text: str) -> bool:
    low = (text or "").lower()
    return any(phrase in low for phrase in _HOUSEKEEPING)


def arc_id(start: int, end: int) -> str:
    return f"arc_{start:04d}_{end:04d}"


# ---------------------------------------------------------------------------
# Census (pure over already-loaded data)
# ---------------------------------------------------------------------------


def census_pair(store: Path, start: int, end: int) -> dict:
    """One pair's census for a heartbeat range. Tolerates missing files."""
    out = {
        "tick_now": None,
        "agents": {},
        "actions": {},
        "rejections": {},
        "builds": [],
        "asks": [],
        "capability_requests": Counter(),
        "objects": [],
        "known_tiles": {},
    }
    if not Path(store).is_dir():
        return out

    hb_path = store / "heartbeat.json"
    if hb_path.is_file():
        heartbeats = read_json(hb_path).get("data", [])
        if heartbeats:
            out["tick_now"] = heartbeats[-1].get("heartbeat_number")
        in_arc = [
            h for h in heartbeats
            if start <= (h.get("heartbeat_number") or 0) <= end
        ]
        out["arc_ticks"] = len(in_arc)
        actions = Counter()
        rejections = Counter()
        for hb in in_arc:
            for ref, act in (hb.get("action_taken") or {}).items():
                if isinstance(act, dict):
                    actions[(ref, act.get("action_type"))] += 1
                out_action = (hb.get("action_outcomes") or {}).get(ref, {})
                if isinstance(out_action, dict) and out_action.get("status") == "rejected":
                    rejections[str(out_action.get("reason", ""))] += 1
            for ref, act in (hb.get("action_taken") or {}).items():
                if not isinstance(act, dict):
                    continue
                if act.get("action_type") == "build":
                    desc = act.get("description") or ""
                    out["builds"].append({
                        "heartbeat": hb.get("heartbeat_number"),
                        "agent": ref,
                        "object_type": act.get("object_type", ""),
                        "object_id": act.get("object_id", ""),
                        "materials": act.get("materials") or {},
                        "description": desc,
                        "housekeeping": is_housekeeping(desc),
                    })
                if act.get("action_type") == "ask_human":
                    out["asks"].append({
                        "heartbeat": hb.get("heartbeat_number"),
                        "agent": ref,
                        "question": act.get("question", ""),
                        "urgency": act.get("urgency", ""),
                    })
        out["actions"] = {f"{ref}:{act}": n for (ref, act), n in actions.most_common()}
        out["rejections"] = dict(rejections.most_common(12))

    inv_path = store / "inventory.json"
    if inv_path.is_file():
        for ref, holdings in (read_json(inv_path).get("data") or {}).items():
            out["agents"][ref] = {
                "food": food_units(holdings),
                "goods": goods_units(holdings),
                "holdings": holdings,
            }

    ws_path = store / "world_state.json"
    if ws_path.is_file():
        data = read_json(ws_path).get("data", {})
        for obj_id, obj in (data.get("public_objects") or {}).items():
            if not isinstance(obj, dict):
                continue
            desc = obj.get("public_description") or ""
            out["objects"].append({
                "object_id": obj_id,
                "object_type": obj.get("object_type", ""),
                "created_heartbeat": obj.get("created_heartbeat"),
                "materials": obj.get("materials"),
                "housekeeping": is_housekeeping(desc),
                "description": desc,
            })
        for req in data.get("capability_requests") or []:
            if isinstance(req, dict):
                out["capability_requests"][
                    f"{req.get('capability_id')}:{req.get('status', 'pending')}"
                ] += 1

    for km in Path(store).glob("known_map_*.json"):
        ref = km.stem.replace("known_map_", "")
        try:
            data = read_json(km).get("data", read_json(km))
        except (OSError, json.JSONDecodeError):
            continue
        tiles = data.get("known_tiles") or {}
        firsts = [
            v.get("first_observed_tick")
            for v in tiles.values()
            if isinstance(v, dict) and v.get("first_observed_tick") is not None
        ]
        out["known_tiles"][ref] = {
            "total": len(tiles),
            "new_in_arc": sum(1 for t in firsts if t is not None and start <= t <= end),
            "myths": len(data.get("myths") or {}),
        }

    return out


def known_tiles_growth(known: dict, ref: str, total_if_absent: int = 0) -> int:
    return (known.get(ref) or {}).get("new_in_arc", 0)


def render_census(start: int, end: int, pairs: dict) -> str:
    when = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Arc census HB{start}-{end}",
        "",
        f"_Exported {when} by `scripts/export_arc_census.py` from the canonical",
        "stores. Read-only export: nothing in the world was changed to produce",
        "this file. Regenerate with the same `--from/--to`._",
        "",
    ]

    housekeeping = 0
    built = 0
    for name, data in pairs.items():
        lines.append(f"## {name} pair")
        lines.append("")
        lines.append(f"- ticks in arc: **{data.get('arc_ticks', 0)}**")
        lines.append(f"- store tick at export: **{data.get('tick_now')}**")
        lines.append("")

        if data.get("agents"):
            lines.append("### Holdings now")
            lines.append("")
            lines.append("| agent | food | goods | holdings |")
            lines.append("|---|---|---|---|")
            for ref, info in sorted(data["agents"].items()):
                held = ", ".join(
                    f"{k} {v}" for k, v in sorted((info["holdings"] or {}).items())
                ) or "-"
                lines.append(
                    f"| {ref} | {info['food']} | {info['goods']} | {held} |")
            lines.append("")

        if data.get("known_tiles"):
            lines.append("### Knowledge growth (the decisive measure)")
            lines.append("")
            lines.append("| agent | known tiles | new in arc | myths |")
            lines.append("|---|---|---|---|")
            for ref, info in sorted(data["known_tiles"].items()):
                lines.append(
                    f"| {ref} | {info['total']} | **{info['new_in_arc']}** "
                    f"| {info['myths']} |")
            lines.append("")

        if data.get("actions"):
            lines.append("### Action census")
            lines.append("")
            for key, n in list(data["actions"].items())[:12]:
                lines.append(f"- `{key}`: {n}")
            lines.append("")

        if data.get("rejections"):
            lines.append("### Rejections (where a rigged board shows up)")
            lines.append("")
            for reason, n in list(data["rejections"].items())[:10]:
                lines.append(f"- {n}x `{reason}`")
            lines.append("")

        if data.get("builds"):
            lines.append("### Build attempts in this arc")
            lines.append("")
            for b in data["builds"][:20]:
                mark = " _(housekeeping)_" if b["housekeeping"] else ""
                desc = b["description"].replace("\n", " ")[:110]
                lines.append(
                    f"- HB{b['heartbeat']} `{b['agent']}` **{b['object_type']}**"
                    f" {json.dumps(b['materials'], sort_keys=True)}{mark} — {desc}")
            built += len(data["builds"])
            housekeeping += sum(1 for b in data["builds"] if b["housekeeping"])
            lines.append("")

        if data.get("asks"):
            lines.append("### Questions asked")
            lines.append("")
            for a in data["asks"][:20]:
                q = a["question"].replace("\n", " ")[:220]
                lines.append(f"- HB{a['heartbeat']} `{a['agent']}` ({a['urgency']}): {q}")
            lines.append("")

        if data.get("objects"):
            novel = [o for o in data["objects"] if o.get("materials")]
            lines.append(f"### Objects on the board ({len(data['objects'])}, "
                         f"{len(novel)} from the build layer)")
            lines.append("")
            for o in sorted(data["objects"], key=lambda x: (x.get("created_heartbeat") or 0)):
                mark = " _(housekeeping)_" if o["housekeeping"] else ""
                desc = o["description"].replace("\n", " ")[:100]
                lines.append(
                    f"- HB{o['created_heartbeat']} **{o['object_type']}**"
                    f"{mark} — {desc}")
            lines.append("")

        if data.get("capability_requests"):
            lines.append("### Capability requests by status")
            lines.append("")
            for key, n in data["capability_requests"].most_common():
                lines.append(f"- {n}x `{key}`")
            lines.append("")

    lines.append("## Arc totals")
    lines.append("")
    lines.append(f"- build attempts: **{built}**")
    lines.append(f"- of those, housekeeping-stated: **{housekeeping}**")
    lines.append("")
    return "\n".join(lines)


def export(start: int, end: int, dry_run: bool = False) -> dict:
    pairs = {name: census_pair(store, start, end)
             for name, store in PAIRS.items()}
    text = render_census(start, end, pairs)
    target = ARCS_DIR / f"{arc_id(start, end)}.md"
    if not dry_run:
        ARCS_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": str(target),
        "bytes": len(text.encode("utf-8")),
        "written": not dry_run,
    }


def build_index() -> str:
    """Regenerate the arc index from whatever files exist."""
    if not ARCS_DIR.is_dir():
        return ""
    entries = sorted(
        p for p in ARCS_DIR.glob("arc_*.md") if p.name != "README.md"
    )
    lines = [
        "# Arc censuses",
        "",
        "One file per arc of world history, exported read-only from the",
        "canonical stores by `scripts/export_arc_census.py`. These are the",
        "measurements behind the specs in `docs/` — if a claim about agent",
        "behavior is made anywhere, the numbers behind it should be here.",
        "",
        "| arc | ticks | file |",
        "|---|---|---|",
    ]
    for p in entries:
        m = re.match(r"arc_(\d+)_(\d+)\.md", p.name)
        if not m:
            continue
        lines.append(
            f"| HB{m.group(1)}-{m.group(2)} | {int(m.group(2)) - int(m.group(1)) + 1} "
            f"| [{p.name}]({p.name}) |"
        )
    lines.append("")
    return "\n".join(lines)


def write_index(dry_run: bool = False) -> dict:
    text = build_index()
    if not dry_run and text:
        ARCS_DIR.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text(text, encoding="utf-8", newline="\n")
    return {"path": str(INDEX_PATH), "written": bool(text) and not dry_run}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="end", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--index", action="store_true",
                    help="regenerate docs/arcs/README.md from existing files")
    args = ap.parse_args()

    if args.index:
        print(json.dumps(write_index(args.dry_run), indent=2))
        return 0
    if args.start > args.end:
        print("ARC_ERROR: --from must be <= --to")
        return 1
    result = export(args.start, args.end, args.dry_run)
    print(json.dumps(result, indent=2))
    if not args.dry_run:
        print(json.dumps(write_index(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
