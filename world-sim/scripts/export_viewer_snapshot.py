"""Export read-only viewer snapshots of ALL living pairs (east + west).

Reads each pair's canonical store (.runtime/first-pair*) and the true map
(data/world/true_map.json) and writes a single self-contained JS data file
that the static viewer (world-sim/viewer/index.html) loads via <script src>.

READ-ONLY: never writes to canonical state. Output is regenerable:
world-sim/viewer/viewer_data.js

Usage:
    python world-sim/scripts/export_viewer_snapshot.py
    python world-sim/scripts/export_viewer_snapshot.py --slim --out PATH
        --slim: only tiles any agent has touched/known (web payload; the
        full 80k-tile map is never served to a browser)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"
VIEWER_DIR = WORLD_SIM / "viewer"
OUT_FILE = VIEWER_DIR / "viewer_data.js"

if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))

from backend.world.world_pressure import (  # noqa: E402
    FOOD_CAP,
    GOODS_CAP,
    FOOD_PER_HEARTBEAT,
    split_ledgers,
)

PAIRS = [
    ("east", RUNTIME_ROOT / "first-pair"),
    ("west", RUNTIME_ROOT / "first-pair-west"),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def reconstruct_positions(heartbeats: list[dict], start_tiles: dict) -> dict:
    positions = dict(start_tiles)
    timeline: dict[int, dict[str, str]] = {}
    for hb in heartbeats:
        actions = hb.get("action_taken") or {}
        if isinstance(actions, dict):
            for agent_id, action in actions.items():
                if agent_id not in positions or not isinstance(action, dict):
                    continue
                if action.get("action_type") == "move" and action.get("target_tile"):
                    positions[agent_id] = action["target_tile"]
        timeline[int(hb.get("heartbeat_number", 0))] = dict(positions)
    return {str(k): v for k, v in timeline.items()}


def build_pair_snapshot(pair_name: str, store: Path, true_map: dict) -> dict | None:
    """One pair's snapshot, or None if the store doesn't exist yet."""
    if not (store / "heartbeat.json").exists() or not (store / "world_state.json").exists():
        return None

    heartbeats = read_json(store / "heartbeat.json")["data"]
    world_state = read_json(store / "world_state.json")["data"]
    goals = read_json(store / "goals.json")["data"] if (store / "goals.json").exists() else []
    questions = (
        read_json(store / "questions.json")["data"] if (store / "questions.json").exists() else []
    )

    identity = read_json(store / "identity.json") if (store / "identity.json").exists() else {}
    idata = identity.get("data", identity)
    name_by_hash = {}
    for idk, short in (("adam_agent_id", "adam"), ("eve_agent_id", "eve")):
        if idata.get(idk):
            name_by_hash[idata[idk]] = short

    habitat = world_state.get("habitat", {})
    start_tiles = habitat.get("starting_tile_ids") or {}
    agents = sorted(start_tiles.keys()) or sorted(
        (world_state.get("tile_occupancy") or {}).keys()
    )

    known_maps = {}
    for agent in agents:
        p = store / f"known_map_{agent}.json"
        if p.exists():
            known_maps[agent] = read_json(p)

    # Charter (self-authored identity): latest version per agent, public like
    # messages — the show gets to read who they say they are.
    # Belongings (build layer): persisted holdings per agent, public like
    # messages — the show gets to see what they own.
    inventories = {}
    inventory_path = store / "inventory.json"
    if inventory_path.exists():
        try:
            inventories = read_json(inventory_path).get("data", {}) or {}
        except Exception:
            inventories = {}
    charters = {}
    charter_path = store / "charter.json"
    if charter_path.exists():
        try:
            cdata = read_json(charter_path).get("data", [])
            for rec in cdata:
                ref = rec.get("agent_ref", "")
                # latest = last appended for this owner (append-only store)
                charters[ref] = {
                    "text": rec.get("charter_text", ""),
                    "heartbeat": rec.get("heartbeat"),
                    "versions": sum(1 for x in cdata if x.get("agent_ref") == ref),
                }
        except Exception:
            charters = {}

    # name the "other" continent relative to where this pair lives
    home_continent = None
    for tid in (world_state.get("tile_occupancy") or {}).values():
        t = next((x for x in true_map["tiles"] if x["tile_id"] == tid), None)
        if t:
            home_continent = t["continent_id"]
            break

    def msg_sender(m):
        sid = m.get("sender_agent_id", "")
        return name_by_hash.get(sid, sid)

    # World pressure (docs/world_pressure_spec.md): per-agent physics view
    # derived from persisted holdings. "famished" here means "no food held
    # right now" — the between-ticks read of the same ledgers the agent
    # sees; the per-tick truth lives in heartbeat action_outcomes.
    pressure = {}
    for agent, holdings in (inventories or {}).items():
        led = split_ledgers(holdings)
        pressure[agent] = {
            "carrying": {
                "food_used": led["food"],
                "food_cap": FOOD_CAP,
                "goods_used": led["goods"],
                "goods_cap": GOODS_CAP,
            },
            "provisions": {
                "food_units": led["food"],
                "famished": led["food"] == 0,
            },
        }

    # Noncanonical agent asks: the show hears what the operator hears.
    # An agent in a catch-22 (e.g. refused construction) speaks here.
    agent_asks = []
    asks_path = store / "agent_questions.json"
    if asks_path.exists():
        try:
            for rec in read_json(asks_path).get("data", []):
                agent_asks.append({
                    "heartbeat": rec.get("heartbeat"),
                    "agent": rec.get("agent_ref", "?"),
                    "urgency": rec.get("urgency"),
                    "question": rec.get("question", ""),
                })
        except Exception:
            agent_asks = []

    return {
        "agents": agents,
        "exported_tick": world_state.get("tick"),
        "exported_at_utc": world_state.get("updated_at_utc"),
        "home_continent": home_continent,
        "current_positions": world_state.get("tile_occupancy", {}),
        "public_objects": world_state.get("public_objects", {}),
        "public_messages": [
            {**m, "sender": msg_sender(m)} for m in world_state.get("public_messages", [])
        ],
        "goals": goals,
        "questions": [
            {
                "question_id": q.get("question_id"),
                "heartbeat": q.get("heartbeat"),
                "question": q.get("question"),
                "status": q.get("status"),
                "answer": (q.get("provenance") or {}).get("answer"),
                "urgency": q.get("urgency"),
            }
            for q in questions
        ],
        "known_maps": known_maps,
        "charters": charters,
        "inventories": inventories,
        "pressure": pressure,
        "agent_asks": agent_asks[-10:],
        "heartbeats": extract_per_heartbeat(heartbeats),
        "position_timeline": reconstruct_positions(heartbeats, start_tiles),
    }


def extract_per_heartbeat(heartbeats: list[dict]) -> list[dict]:
    out = []
    for hb in heartbeats:
        actions = hb.get("action_taken") or {}
        outcomes = hb.get("action_outcomes") or {}
        slim_actions = {}
        if isinstance(actions, dict):
            for agent_id, action in actions.items():
                if not isinstance(action, dict):
                    continue
                outcome = outcomes.get(agent_id, {}) if isinstance(outcomes, dict) else {}
                if not isinstance(outcome, dict):
                    outcome = {}
                slim_actions[agent_id] = {
                    "type": action.get("action_type"),
                    "reason": action.get("reason", ""),
                    "target_tile": action.get("target_tile"),
                    "message": action.get("message"),
                    "recipient": action.get("recipient"),
                    "resource": action.get("resource_kind"),
                    "charter_text": action.get("charter_text"),
                    "object_id": action.get("object_id"),
                    "object_type": action.get("object_type"),
                    "description": action.get("description"),
                    "materials": action.get("materials"),
                    # execution outcome (world pressure era; absent in older
                    # records -> None): the frozen rejection strings are the
                    # census contract.
                    "outcome_status": outcome.get("status"),
                    "outcome_reason": outcome.get("reason"),
                }
        out.append(
            {
                "heartbeat": int(hb.get("heartbeat_number", 0)),
                "timestamp": hb.get("timestamp_utc", ""),
                "actions": slim_actions,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_FILE))
    ap.add_argument("--slim", action="store_true",
                    help="web payload: only tiles any agent has touched/known")
    args = ap.parse_args()
    out_path = Path(args.out)

    true_map = read_json(WORLD_SIM / "data" / "world" / "true_map.json")
    map_snapshot = {
        "continents": true_map.get("continents", []),
        "regions": true_map.get("regions", []),
        "tiles": true_map.get("tiles", []),
        "landmarks": true_map.get("landmarks", []),
        "travel_edges": true_map.get("travel_edges", []),
        "mysteries_hidden": bool(true_map.get("mysteries")),
    }

    pairs = {}
    for pair_name, store in PAIRS:
        snap = build_pair_snapshot(pair_name, store, true_map)
        if snap:
            pairs[pair_name] = snap

    if not pairs:
        print("NO PAIR STORES FOUND", file=sys.stderr)
        return 1

    # shared geography layer: home tiles per pair + known tiles anywhere
    shared_tiles: dict[str, dict] = {}
    for snap in pairs.values():
        for km in snap["known_maps"].values():
            for tid in km.get("known_tiles", {}):
                t = next((x for x in map_snapshot["tiles"] if x["tile_id"] == tid), None)
                if t:
                    shared_tiles[tid] = t
        for tid in list(snap["current_positions"].values()) + [
            t for t in (snap.get("position_timeline", {}).values())
            for t in t.values()
        ]:
            t2 = next((x for x in map_snapshot["tiles"] if x["tile_id"] == tid), None)
            if t2:
                shared_tiles[tid] = t2

    if args.slim:
        # web payload: extra trim of pair data (drop unneeded heavy fields)
        pass
    # always trim the embedded true_map to the tiles civilization has
    # touched - the viewer renders nothing else, and shipping 80k tiles to
    # a browser is dead weight either way
    rel_set = set(shared_tiles.keys())
    map_snapshot = {
        "continents": map_snapshot["continents"],
        "regions": map_snapshot["regions"],
        "tiles": [t for t in map_snapshot["tiles"] if t["tile_id"] in rel_set],
        "landmarks": [l for l in map_snapshot["landmarks"] if l["tile_id"] in rel_set],
        "travel_edges": [
            e for e in map_snapshot["travel_edges"]
            if e["from_tile_id"] in rel_set and e["to_tile_id"] in rel_set
        ],
        "mysteries_hidden": map_snapshot.get("mysteries_hidden", False),
    }

    snapshot = {
        "true_map": map_snapshot,
        "pairs": pairs,
        "shared_tiles": shared_tiles,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=None if args.slim else 1, ensure_ascii=False)
    out_path.write_text(
        "// Auto-generated by scripts/export_viewer_snapshot.py - read-only "
        "snapshot of all living civilizations.\nwindow.VIEWER_DATA = " + payload + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = {k: (v["exported_tick"], len(v["heartbeats"]),
                   len(v["public_messages"])) for k, v in pairs.items()}
    print(f"VIEWER-SNAPSHOT=OK slim={args.slim} pairs={list(pairs)} "
          f"details={summary} -> {out_path} ({len(payload)/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
