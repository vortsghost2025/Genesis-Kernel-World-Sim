"""Export read-only viewer snapshots of ALL living pairs (east + west).

Reads each pair's canonical store (.runtime/first-pair*) and the true map
(data/world/true_map.json) and writes a single self-contained JS data file
that the static viewer (world-sim/viewer/index.html) loads via <script src>.

READ-ONLY: never writes to canonical state. Output is regenerable:
world-sim/viewer/viewer_data.js

Usage:
    python world-sim/scripts/export_viewer_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"
VIEWER_DIR = WORLD_SIM / "viewer"
OUT_FILE = VIEWER_DIR / "viewer_data.js"

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

    return {
        "pair": pair_name,
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
        "heartbeats": extract_per_heartbeat(heartbeats),
        "position_timeline": reconstruct_positions(heartbeats, start_tiles),
    }


def extract_per_heartbeat(heartbeats: list[dict]) -> list[dict]:
    out = []
    for hb in heartbeats:
        actions = hb.get("action_taken") or {}
        slim_actions = {}
        if isinstance(actions, dict):
            for agent_id, action in actions.items():
                if not isinstance(action, dict):
                    continue
                slim_actions[agent_id] = {
                    "type": action.get("action_type"),
                    "reason": action.get("reason", ""),
                    "target_tile": action.get("target_tile"),
                    "message": action.get("message"),
                    "recipient": action.get("recipient"),
                    "resource": action.get("resource_kind"),
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

    snapshot = {
        "true_map": map_snapshot,
        "pairs": pairs,
        "shared_tiles": shared_tiles,
    }

    VIEWER_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=1, ensure_ascii=False)
    OUT_FILE.write_text(
        "// Auto-generated by scripts/export_viewer_snapshot.py - read-only "
        "snapshot of all living civilizations.\nwindow.VIEWER_DATA = " + payload + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = {k: (v["exported_tick"], len(v["heartbeats"]),
                   len(v["public_messages"])) for k, v in pairs.items()}
    print(f"VIEWER-SNAPSHOT=OK pairs={list(pairs)} details={summary} -> {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
