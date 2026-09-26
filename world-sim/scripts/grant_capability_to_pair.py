"""Operator capability-grant tool: answers agent request_capability requests.

Appends an additional grant to a pair's store via the append-only extra-grants
mechanism (never touches the legacy movement grant in capability_grant.json).
The granted capability appears in both agents' context at their next
heartbeat under "Your active capabilities".

Governed operator action: this is the answer side of the request_capability
loop. Agents ask; this tool lets the operator say yes.

Usage:
    python world-sim/scripts/grant_capability_to_pair.py <pair> <capability_id> \
        [--grant-id ID] [--scope TEXT] [--reason TEXT] [--provenance TAG]

Example (answering the West pair's 135 gather requests):
    python world-sim/scripts/grant_capability_to_pair.py west gather \
        --reason "You have and always had permission to gather." \
        --provenance sean-operator-2026-09-25
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    CapabilityGrantRecord,
    FirstPairPersistenceStore,
    append_capability_grant,
    load_extra_capability_grants,
)

PAIR_STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pair", choices=sorted(PAIR_STORES))
    ap.add_argument("capability_id")
    ap.add_argument("--grant-id", default="")
    ap.add_argument("--scope", default="as requested by the agents")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--provenance", required=True)
    args = ap.parse_args()

    store = FirstPairPersistenceStore(PAIR_STORES[args.pair])
    grant_id = args.grant_id or f"grant-{args.capability_id}-{args.pair}-001"

    existing_ids = [g.grant_id for g in load_extra_capability_grants(store)]
    if grant_id in existing_ids:
        print(f"GRANT=ALREADY_PRESENT grant_id={grant_id}")
        return 0

    grant = CapabilityGrantRecord(
        grant_id=grant_id,
        capability_id=args.capability_id,
        scope=args.scope,
        reason=args.reason,
        operator_provenance=args.provenance,
    ).seal()
    appended = append_capability_grant(store, grant)
    if not appended:
        print(f"GRANT=FAILED grant_id={grant_id}")
        return 1

    print(f"GRANT=OK pair={args.pair} capability={args.capability_id} grant_id={grant_id}")
    print(f"agents will see it in 'Your active capabilities' at their next heartbeat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
