"""First-pair state evidence export — read-only snapshot of the canonical store.

Loads the canonical first-pair store through the existing persistence
contract and writes a JSON evidence record: identity, world state, goals,
questions, heartbeat history, memory, and provenance. Never mutates the
store, never runs heartbeats, never calls a model.

Usage (from world-sim/):
    python scripts/export_first_pair_state_evidence.py --out path/to/evidence.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    load_goals,
    load_heartbeat_history,
    load_questions,
    load_relationship_events,
    load_runtime_policy,
    load_capability_grant,
    load_memory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only first-pair state evidence export")
    parser.add_argument("--out", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    store = FirstPairPersistenceStore(None)
    evidence: dict = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "exporter": "scripts/export_first_pair_state_evidence.py",
        "claim_scope": "operator_proof",
    }

    identity_raw = store._read_json(store._path("identity.json"))
    if identity_raw and identity_raw.get("type") == "identity_record":
        idata = identity_raw["data"]
        evidence["identity"] = {
            "adam_agent_id": idata.get("adam_agent_id"),
            "eve_agent_id": idata.get("eve_agent_id"),
            "pair_id": idata.get("pair_id"),
        }

    world_raw = store._read_json(store._path("world_state.json"))
    if world_raw and world_raw.get("type") == "world_state_record":
        wdata = world_raw["data"]
        evidence["world_state"] = {
            "tick": wdata.get("tick"),
            "tile_occupancy": wdata.get("tile_occupancy"),
            "public_messages_count": len(wdata.get("public_messages", [])),
            "public_objects_count": len(wdata.get("public_objects", {})),
        }

    evidence["goals"] = [
        {
            "goal_id": g.goal_id,
            "agent_id": g.agent_id,
            "description": g.description,
            "status": g.status,
            "created_heartbeat": g.created_heartbeat,
        }
        for g in load_goals(store)
    ]

    evidence["questions"] = [
        {
            "question_id": q.question_id,
            "asking_agent_id": q.asking_agent_id,
            "status": q.status,
            "heartbeat": q.heartbeat,
        }
        for q in load_questions(store)
    ]

    history = load_heartbeat_history(store)
    evidence["heartbeat_history"] = [
        {
            "heartbeat_number": h.heartbeat_number,
            "timestamp_utc": h.timestamp_utc,
            "world_mutations_count": len(h.world_mutations),
        }
        for h in history
    ]

    policy = load_runtime_policy(store)
    grant = load_capability_grant(store)
    evidence["authorities"] = {
        "runtime_policy": {
            "policy_id": policy.policy_id,
            "status": policy.status,
            "movement_grant_ref": policy.movement_grant_ref,
        } if policy else None,
        "capability_grant": {
            "grant_id": grant.grant_id,
            "capability_id": grant.capability_id,
            "status": grant.status,
        } if grant else None,
    }

    rel_events = load_relationship_events(store)
    evidence["relationship_events_count"] = len(rel_events) if rel_events else 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), newline="\n")
    print(f"EVIDENCE_EXPORTED={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
