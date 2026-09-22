"""Civilization status viewer — a readable snapshot of Adam and Eve's world.

Usage: python civilization_status.py
"""
import json
from pathlib import Path

STORE = Path(r"S:\Genesis Kernel World Sim\world-sim\.runtime\first-pair")

def load(name):
    return json.loads((STORE / name).read_text(encoding="utf-8"))

def main():
    hb = load("heartbeat.json").get("data", [])
    ws = load("world_state.json").get("data", {})
    mem = load("memory.json").get("data", {})
    goals = load("goals.json").get("data", [])
    questions = load("questions.json").get("data", [])
    km_adam = load("known_map_east_adam.json")
    km_eve = load("known_map_east_eve.json")

    tick = ws.get("tick", 0)
    occ = ws.get("tile_occupancy", {})
    msgs = ws.get("public_messages", [])
    objs = ws.get("public_objects", {})

    print("=" * 70)
    print("  ADAM & EVE — CIVILIZATION STATUS")
    print("=" * 70)
    print(f"  Tick: {tick}  |  Heartbeats: {len(hb)}")
    print(f"  Adam: {occ.get('east_adam', '?')}  |  Eve: {occ.get('east_eve', '?')}")
    print(f"  Co-located: {'YES' if occ.get('east_adam') == occ.get('east_eve') else 'NO'}")
    print()

    # Objects
    print("  PUBLIC OBJECTS:")
    for obj_id, obj in objs.items():
        desc = obj.get("public_description", obj.get("description", "?"))
        print(f"    {obj_id}: {desc[:80]}")
    print()

    # Messages (last 5)
    print("  RECENT MESSAGES (last 5):")
    for m in msgs[-5:]:
        hb_num = m.get("heartbeat", "?")
        text = m.get("message", "?")
        # Try to figure out who sent it
        sender = "Adam" if "Hi Eve" in text or "Eve," in text[:5] else "Eve" if "Hi Adam" in text or "Adam," in text[:6] else "?"
        print(f"    [{sender} @ hb{hb_num}] {text[:100]}")
    print()

    # Goals
    print("  ACTIVE GOALS:")
    for g in goals:
        if g.get("status") in ("active", "in_progress"):
            print(f"    {g.get('goal_id', '?')}: {g.get('description', '?')[:100]}")
    print()

    # Answered questions
    print("  ANSWERED QUESTIONS:")
    for q in questions:
        if q.get("status") == "answered":
            answer = q.get("provenance", {}).get("answer", "?")
            print(f"    {q.get('question_id', '?')}: {answer[:100]}")
    print()

    # Known tiles
    print("  ADAM'S KNOWN WORLD:")
    for tid in sorted(km_adam.get("known_tiles", {}).keys()):
        visits = km_adam["known_tiles"][tid].get("visit_count", 0)
        print(f"    {tid} (visited {visits}x)")
    print()

    print("  EVE'S KNOWN WORLD:")
    for tid in sorted(km_eve.get("known_tiles", {}).keys()):
        visits = km_eve["known_tiles"][tid].get("visit_count", 0)
        print(f"    {tid} (visited {visits}x)")
    print()

    # Known landmarks
    adam_lms = km_adam.get("known_landmarks", {})
    eve_lms = km_eve.get("known_landmarks", {})
    print("  DISCOVERED LANDMARKS:")
    for lm_id, lm in adam_lms.items():
        known_by = "both" if lm_id in eve_lms else "Adam"
        print(f"    {lm_id} ({lm.get('kind', '?')}) — known by {known_by}")
        print(f"      {lm.get('description', '?')[:80]}")
    for lm_id, lm in eve_lms.items():
        if lm_id not in adam_lms:
            print(f"    {lm_id} ({lm.get('kind', '?')}) — known by Eve only")
            print(f"      {lm.get('description', '?')[:80]}")
    print()

    # Last heartbeat cognition
    if hb:
        last = hb[-1]
        print("  LAST HEARTBEAT ACTIONS:")
        for agent, action in last.get("action_taken", {}).items():
            at = action.get("action_type", "?")
            if at == "move":
                print(f"    {agent}: moved to {action.get('target_tile', '?')}")
            elif at == "leave_public_message":
                print(f"    {agent}: left a message")
            elif at == "create_public_object":
                print(f"    {agent}: created {action.get('object_id', '?')}")
            elif at == "no_action" or at is None:
                print(f"    {agent}: no action")
            else:
                print(f"    {agent}: {at}")
    print()

    # Recent memories (last 3 per agent)
    print("  ADAM'S RECENT MEMORIES:")
    for m in mem.get("east_adam", [])[-3:]:
        print(f"    [{m.get('type', '?')}] {m.get('content', '?')[:100]}")
    print()
    print("  EVE'S RECENT MEMORIES:")
    for m in mem.get("east_eve", [])[-3:]:
        print(f"    [{m.get('type', '?')}] {m.get('content', '?')[:100]}")
    print()

    print("=" * 70)


if __name__ == "__main__":
    main()
