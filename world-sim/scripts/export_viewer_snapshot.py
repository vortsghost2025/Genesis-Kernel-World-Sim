"""Export read-only viewer snapshots of ALL living pairs (east + west).

Reads each pair's canonical store (.runtime/first-pair*) and the true map
(data/world/true_map.json) and writes a single self-contained JS data file
that the static viewer (world-sim/viewer/index.html) loads via <script src>.

READ-ONLY: never writes to canonical state. Output is regenerable:
world-sim/viewer/viewer_data.js
world-sim/viewer/world_base.png  (full 200x200 true map, 1px/tile — the
viewer draws it dim as the unexplored world's ghost)

Usage:
    python world-sim/scripts/export_viewer_snapshot.py
    python world-sim/scripts/export_viewer_snapshot.py --slim --out PATH
        --slim: only tiles any agent has touched/known (web payload; the
        full 80k-tile map is never served to a browser — except as the
        pre-rendered backdrop PNG, which is ~40KB)
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"
VIEWER_DIR = WORLD_SIM / "viewer"
OUT_FILE = VIEWER_DIR / "viewer_data.js"
BASE_PNG = VIEWER_DIR / "world_base.png"

if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))

PAIRS = [
    ("east", RUNTIME_ROOT / "first-pair"),
    ("west", RUNTIME_ROOT / "first-pair-west"),
]


# --------------------------------------------------------------------------
# full-world backdrop PNG
#
# The explored snapshot only carries tiles civilization has touched, which
# renders as sparse dots on void. The full 200x200 true map exists, so we
# render it once, server-side, at 1px/tile into a tiny PNG. The viewer draws
# it dim — the unexplored world has presence, and the lit explored regions
# sit on top of their own ghost.
# --------------------------------------------------------------------------

# same palette the viewer uses (keep in sync with index.html BIOME table)
_PY_BIOME = {
    "deep_ravine": (22, 17, 32),
    "deep_lake": (16, 52, 88),
    "warm_coast": (196, 164, 106),
    "temperate_valley": (64, 118, 66),
    "temperate_hills": (104, 120, 66),
    "highland": (124, 116, 102),
    "temperate_forest": (42, 94, 52),
    "dense_woodland": (26, 72, 40),
    "dark_thicket": (20, 52, 42),
    "coastal_forest": (40, 90, 60),
    "coastal_cliffs": (118, 118, 128),
    "open_sea": (10, 34, 62),
}
_PY_TERRAIN_FALLBACK = {
    "forest": (42, 94, 52), "grassland": (64, 118, 66), "hill": (104, 120, 66),
    "mountain": (124, 116, 102), "desert": (200, 170, 100), "snow": (205, 214, 222),
    "coast": (196, 164, 106), "river": (34, 96, 148), "swamp": (58, 92, 56),
    "tundra": (150, 158, 166), "ocean": (10, 34, 62),
}


def _backdrop_color(tile: dict) -> tuple[int, int, int]:
    e = tile.get("elevation")
    if e is None:
        e = 0.5
    if tile.get("water"):
        b = (46, 128, 182) if tile["water"].get("drinkable") else (40, 82, 122)
        k = 0.75 + e * 0.5
        return (int(b[0] * k), int(b[1] * k), int(b[2] * k))
    b = _PY_BIOME.get(tile.get("biome") or "") or _PY_TERRAIN_FALLBACK.get(
        tile.get("terrain") or "", (40, 48, 62))
    k = 0.72 + e * 0.56
    r, g, bl = b[0] * k, b[1] * k, b[2] * k
    snow_line = 0.78 if tile.get("biome") == "highland" or tile.get("terrain") == "mountain" else 0.93
    if e > snow_line:
        m = min(1.0, (e - snow_line) / (1 - snow_line))
        r += (210 - r) * m
        g += (218 - g) * m
        bl += (226 - bl) * m
    return (int(r), int(g), int(bl))


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_world_backdrop(true_map: dict, out_path: Path) -> dict | None:
    """Render the FULL true map to a 1px/tile PNG. Returns world_size info."""
    tiles = true_map.get("tiles") or []
    if not tiles:
        return None
    xs = [t["coordinates"]["x"] for t in tiles if t.get("coordinates")]
    ys = [t["coordinates"]["y"] for t in tiles if t.get("coordinates")]
    if not xs:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w, h = max_x - min_x + 1, max_y - min_y + 1

    rows: list[bytes] = []
    empty = bytes((6, 9, 15, 255))
    grid: dict[tuple[int, int], bytes] = {}
    for t in tiles:
        c = t.get("coordinates")
        if not c:
            continue
        r, g, b = _backdrop_color(t)
        grid[(c["x"], c["y"])] = bytes((r, g, b, 255))
    for gy in range(min_y, max_y + 1):
        row = bytearray()
        for gx in range(min_x, max_x + 1):
            row += grid.get((gx, gy), empty)
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + row for row in rows)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + _png_chunk(b"IHDR", ihdr)
           + _png_chunk(b"IDAT", zlib.compress(raw, 9))
           + _png_chunk(b"IEND", b""))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png)
    return {
        "min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y,
        "width": w, "height": h,
        "png_bytes": len(png),
    }


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


def build_chronicle(heartbeats: list[dict], name_by_hash: dict,
                    limit: int = 24) -> list[dict]:
    """Notable events, newest last: builds, meals, questions, collapses.

    The show's script. Moves and gathers are noise; what an agent MADE,
    what it ATE, what it ASKED, and when a body failed are the beats a
    watcher actually follows.
    """
    events: list[dict] = []
    for rec in heartbeats[-120:]:
        hb = rec.get("heartbeat_number")
        acts = rec.get("action_taken") or {}
        outcomes = rec.get("action_outcomes") or {}
        if not isinstance(acts, dict):
            continue
        for who, action in acts.items():
            if not isinstance(action, dict):
                continue
            name = name_by_hash.get(who, who)
            at = action.get("action_type")
            outcome = outcomes.get(who) if isinstance(outcomes, dict) else {}
            outcome = outcome if isinstance(outcome, dict) else {}
            if at in ("build", "create_public_object"):
                events.append({"hb": hb, "kind": "build",
                               "who": name,
                               "text": f"built a {action.get('object_type', 'thing')}"})
            elif at == "eat":
                outcome_status = outcome.get("status")
                if outcome_status == "success":
                    events.append({"hb": hb, "kind": "eat",
                                   "who": name,
                                   "text": f"ate {action.get('resource_kind', 'something')}"})
            elif at == "ask_human":
                q = str(action.get("question", ""))[:90]
                if q:
                    events.append({"hb": hb, "kind": "ask",
                                   "who": name,
                                   "text": f"asked: {q}"})
            elif at in ("move", "gather", "no_action", "leave_public_message"):
                continue
            elif outcome.get("status") == "rejected" and "collapse" in str(
                    outcome.get("reason", "")):
                events.append({"hb": hb, "kind": "collapse",
                               "who": name,
                               "text": "collapsed"})
    return events[-limit:]


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

    # (The per-pair `pressure` block - food/goods ledgers and the famished
    # flag - is retired with the pressure model. Holdings still ship under
    # "inventories" below, which is the record of what agents own.)

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

    # Operator-authored messages: the human is a character who can speak.
    operator_messages = []
    ops_path = store / "operator_messages.json"
    if ops_path.exists():
        try:
            operator_messages = [
                {
                    "message_id": m.get("message_id"),
                    "author": m.get("author"),
                    "addressed_to": m.get("addressed_to"),
                    "text": m.get("text", ""),
                    "created_at_utc": m.get("created_at_utc"),
                }
                for m in read_json(ops_path).get("data", [])[-10:]
            ]
        except Exception:
            operator_messages = []

    try:
        from backend.world import survival
        weather_snapshot = survival.weather_forecast(
            pair_name, world_state.get("tick") or 0)
    except Exception:
        weather_snapshot = None

    return {
        "agents": agents,
        "exported_tick": world_state.get("tick"),
        "exported_at_utc": world_state.get("updated_at_utc"),
        "home_continent": home_continent,
        "current_positions": world_state.get("tile_occupancy", {}),
        "vitals": world_state.get("vitals", {}),
        "weather": weather_snapshot,
        "chronicle": build_chronicle(heartbeats, name_by_hash),
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
        "agent_asks": agent_asks[-10:],
        "operator_messages": operator_messages,
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
    world_size = write_world_backdrop(true_map, BASE_PNG)
    if world_size:
        print(f"WORLD-BACKDROP=OK {world_size['width']}x{world_size['height']} "
              f"({world_size['png_bytes']} bytes) -> {BASE_PNG.name}")
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
        "world_size": world_size,
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
