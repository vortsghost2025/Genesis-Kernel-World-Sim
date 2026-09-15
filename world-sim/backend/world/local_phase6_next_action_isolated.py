"""Phase 6 (isolated): smallest next durable transition, TDD-ready, authz-gated.

Movement is forbidden in the canonical habitat, and the Phase 4 bounded Adam
cognition step produced a pure no-op / INTENTION with no goal state change and
no memory write (GOAL_STATUS_UNCHANGED_ACTIVE). Therefore the smallest
legitimate next durable transition for Adam is a goal-state intent transition
(e.g. a goal status/progress note) — an EXISTING repo semantic type
(GOAL_PROGRESS / GoalRecord update), NOT a movement, memory, world-state, or
ledger mutation.

This module implements that path through the existing single-goal authorization
seam (``local_single_goal_write.write_single_goal``), which is
operator-grounded, exact-action + exact-agent bound, single-use and
non-replayable. Crucially, this run executes against an ISOLATED scratch store
(NEVER the canonical ``.runtime/first-pair``), so it proves the next durable
action is implementation-ready WITHOUT performing a canonical write.

Canonical integrity invariant asserted at the end: the canonical
``.runtime/first-pair/goals.json`` retains exactly 1 goal before and after.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")  # run from world-sim/

from backend.world.first_pair_persistence import FirstPairPersistenceStore, load_goals
from backend.world.local_single_goal_write import seal_authorization, write_single_goal

CANONICAL = Path(".runtime/first-pair")
ISOLATED = Path(".scratch/first-pair-phase6-isolated")
ADAM = "genesis-agent-eb4439bd1b97c6baffc0c78956f1399789c9c598872527945372b65ce99e349d"
EVE = "genesis-agent-1864f0bed1b4c501fa76067186115cc42c43b77992ec8cffb4b2801984743211"

CANDIDATE = {
    "ok": True,
    "pair_id": "genesis-first-pair",
    "adam_identity": {"agent_id": ADAM, "canonical_agent_ref": "east_adam", "identity_valid": True},
    "eve_identity": {"agent_id": EVE, "canonical_agent_ref": "east_eve", "identity_valid": True},
}


def main():
    # Baseline: canonical untouched, exact 1 goal.
    canonical_before = len(load_goals(FirstPairPersistenceStore(CANONICAL)))
    print("CANONICAL_GOALS_BEFORE=", canonical_before, "(must be 1)")

    # Isolated scratch store (never canonical).
    if ISOLATED.exists():
        shutil.rmtree(ISOLATED)
    ISOLATED.mkdir(parents=True, exist_ok=True)
    store = FirstPairPersistenceStore(ISOLATED)

    # Phase 5 identification: next durable transition = goal progress note
    # (EXISTING semantic type GOAL_PROGRESS). Movement remains forbidden.
    print("NEXT_DURABLE_TRANSITION=", "goal_progress_note (EXISTING type: GOAL_PROGRESS)")
    print("MOVEMENT_ALLOWED=", False, "(forbidden; not engaged)")

    # Operator-grounded single-use authorization (producer helper = Sean).
    auth = seal_authorization(
        target_agent_id=ADAM,
        pair_id="genesis-first-pair",
        goal_description="Understand the shared starting habitat.",
        goal_status="active",
        created_heartbeat=1,
        operator_proof_ref="sean-operator-proof-phase6",
        authorization_timestamp="2025-01-01T00:00:00Z",
    )

    # Wildcard AUTHORIZED is not enabled this mission; this is a dry run in the
    # ISOLATED store to prove the path is ready. We DO NOT touch canonical.
    result = write_single_goal(
        store,
        birth_candidate=CANDIDATE,
        target_agent_id=ADAM,
        goal_description="Understand the shared starting habitat.",
        authorization=auth,
        pair_id="genesis-first-pair",
        goal_status="active",
        created_heartbeat=1,
    )
    print("ISOLATED_WRITE_OK=", result.get("ok"))
    print("ISOLATED_AUTH_ID=", result.get("authorization_id"))
    print("ISOLATED_MOVEMENT_PERFORMED=", result.get("movement_performed"), "(must be False)")
    print("ISOLATED_GOALS_WRITTEN=", result.get("goals_written"))

    # Replay is refused: the same authorization must not write twice.
    replay = write_single_goal(
        store,
        birth_candidate=CANDIDATE,
        target_agent_id=ADAM,
        goal_description="Understand the shared starting habitat.",
        authorization=auth,
        pair_id="genesis-first-pair",
        goal_status="active",
        created_heartbeat=1,
    )
    print("ISOLATED_REPLAY_BLOCKED=", not replay.get("ok") and "authorization_already_consumed" in replay.get("errors", []))

    # Canonical invariant: still exactly 1 goal, unchanged.
    canonical_after = len(load_goals(FirstPairPersistenceStore(CANONICAL)))
    print("CANONICAL_GOALS_AFTER=", canonical_after, "(must be 1)")
    print("CANONICAL_UNTOUCHED=", canonical_before == 1 and canonical_after == 1)
    print("PHASE6_PREPARED=", result.get("ok") is True and replay.get("ok") is False)


if __name__ == "__main__":
    main()