"""Export a read-only viewer snapshot of the living first-pair world.

Reads the canonical first-pair store (.runtime/first-pair) and the true map
(data/world/true_map.json) and writes a single self-contained JS data file
that the static viewer (world-sim/viewer/index.html) loads via <script src>.

READ-ONLY: this script never writes to canonical state. Its only output is
world-sim/viewer/viewer_data.js, which is regenerable at any time.

Usage:
    python world-sim/scripts/export_viewer_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME = WORLD_SIM / ".runtime" / "first-pair"
VIEWER_DIR = WORLD_SIM / "viewer"
OUT_FILE = VIEWER_DIR / "viewer_data.js"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def reconstruct_positions(heartbeats: list[dict]) -> dict[int, dict[str, str]]:
    """Replay move actions to get each agent's tile after each heartbeat.

    Start positions come from the habitat declaration: Adam and Eve begin on
    their own start tiles. Each heartbeat may contain a move action per agent.
    """
    positions: dict[str, str] = {
        "east_adam": "public-start-adam",
        "east_eve": "public-start-eve",
    }
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
    return timeline


def extract_per_heartbeat(heartbeats: list[dict]) -> list[dict]:
    """Trim each heartbeat record to what the viewer needs."""
    out = []
    for hb in heartbeats:
        actions = hb.get("action_taken") or {}
        slim_actions = {}
        if isinstance(actions, dict):
            for agent_id, action in actions.items():
                if not isinstance(action, dict):
                    continue
                entry = {
                    "type": action.get("action_type"),
                    "reason": action.get("reason", ""),
                    "target_tile": action.get("target_tile"),
                    "message": action.get("message"),
                    "recipient": action.get("recipient"),
                }
                slim_actions[agent_id] = entry
        out.append(
            {
                "heartbeat": int(hb.get("heartbeat_number", 0)),
                "timestamp": hb.get("timestamp_utc", ""),
                "actions": slim_actions,
            }
        )
    return out


def main() -> int:
    missing = [
        p
        for p in [
            RUNTIME / "heartbeat.json",
            RUNTIME / "world_state.json",
            RUNTIME / "goals.json",
            RUNTIME / "questions.json",
            RUNTIME / "known_map_east_adam.json",
            RUNTIME / "known_map_east_eve.json",
            WORLD_SIM / "data" / "world" / "true_map.json",
        ]
        if not p.exists()
    ]
    if missing:
        for p in missing:
            print(f"MISSING REQUIRED FILE: {p}", file=sys.stderr)
        return 1

    heartbeats = read_json(RUNTIME / "heartbeat.json")["data"]
    world_state = read_json(RUNTIME / "world_state.json")["data"]
    goals = read_json(RUNTIME / "goals.json")["data"]
    questions = read_json(RUNTIME / "questions.json")["data"]
    known_adam = read_json(RUNTIME / "known_map_east_adam.json")
    known_eve = read_json(RUNTIME / "known_map_east_eve.json")
    true_map = read_json(WORLD_SIM / "data" / "world" / "true_map.json")

    position_timeline = reconstruct_positions(heartbeats)

    snapshot = {
        "exported_tick": world_state.get("tick"),
        "exported_at_utc": world_state.get("updated_at_utc"),
        "current_positions": world_state.get("tile_occupancy", {}),
        "public_objects": world_state.get("public_objects", {}),
        "public_messages": world_state.get("public_messages", []),
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
        "known_maps": {"east_adam": known_adam, "east_eve": known_eve},
        "true_map": {
            "continents": true_map.get("continents", []),
            "regions": true_map.get("regions", []),
            "tiles": true_map.get("tiles", []),
            "landmarks": true_map.get("landmarks", []),
            "travel_edges": true_map.get("travel_edges", []),
        },
        "heartbeats": extract_per_heartbeat(heartbeats),
        "position_timeline": {str(k): v for k, v in position_timeline.items()},
    }

    VIEWER_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=1, ensure_ascii=False)
    OUT_FILE.write_text(
        "// Auto-generated by scripts/export_viewer_snapshot.py - read-only "
        "snapshot of the living world.\nwindow.VIEWER_DATA = " + payload + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    n_hb = len(heartbeats)
    n_msg = len(snapshot["public_messages"])
    print(
        f"VIEWER-SNAPSHOT=OK tick={snapshot['exported_tick']} "
        f"heartbeats={n_hb} messages={n_msg} -> {OUT_FILE}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
