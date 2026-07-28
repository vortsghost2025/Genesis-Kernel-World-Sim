"""Operator script: run the First Pair bounded runtime demonstration.

Usage:
    python scripts/run_first_pair_demo.py --heartbeats 2 \\
        --root .runtime/first-pair-manual-proof \\
        --export .runtime/first-pair-manual-proof/evidence.json \\
        --seed 42 --questions --backend stub

    python scripts/run_first_pair_demo.py --heartbeats 1 --backend model

    python scripts/run_first_pair_demo.py --answer adam-question-1 \\
        --answer-text "The world is made of digital tiles."

    python scripts/run_first_pair_demo.py --grant-capability movement \\
        --grant-scope first-pair-shared-habitat \\
        --grant-reason "Bounded movement approved"

    python scripts/run_first_pair_demo.py --answer-all --backend stub \\
        --heartbeats 0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root (world-sim/) is on sys.path so that
# `from backend.world import ...` works regardless of cwd.
_proj_root = str(Path(__file__).resolve().parent.parent)
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    grant_capability,
    load_goals,
    load_heartbeat_history,
    load_memory,
    list_unanswered_questions,
    mark_question_answered,
    validate_persistence_integrity,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def _answer_all_questions(store: FirstPairPersistenceStore) -> int:
    """Answer all three standing questions with prescribed operator text."""
    answers = {
        "q-001": (
            "Movement was initially disabled while your persistent identities, memories, "
            "world-state writer and safety boundaries were being verified. The restriction "
            "is not permanent. A limited movement capability is now being granted within a "
            "small shared public habitat."
        ),
        "movement-restriction": (
            "You are not permanently restricted to your starting position. Movement will be "
            "available only between validated connected public locations. The restriction "
            "exists to prevent accidental movement into undefined or private world areas."
        ),
        "world-purpose": (
            "There is no assigned winning condition or scripted life path. You may learn, "
            "cooperate, build shared public things, form and revise your own goals, and ask "
            "humans for information or resources when needed. Humans define the safety "
            "conditions of the world, but your choices within those conditions are yours."
        ),
    }
    count = 0
    for qid, answer in answers.items():
        result = mark_question_answered(
            store, qid, answer, provenance="operator_script",
        )
        if result is not None:
            print(f"Answered: {result['question_id']}")
            print(f"  Question: {result.get('question', '')[:120]}")
            print(f"  Answer:   {result.get('provenance', {}).get('answer', '')[:120]}")
            print(f"  Status:   {result.get('status', '')}")
            count += 1
        else:
            print(f"Skipped: {qid} (not found in store)")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded First Pair runtime demonstration."
    )
    parser.add_argument(
        "--heartbeats",
        type=int,
        default=5,
        help="Number of heartbeat cycles (default: 5; use 0 for answer-only operations)",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Persistence root path (default: world-sim/.runtime/first-pair/)",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Optional path to write evidence JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional deterministic seed",
    )
    parser.add_argument(
        "--questions",
        action="store_true",
        help="Print pending human questions after the run",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="stub",
        choices=["stub", "deterministic_stub", "model"],
        help="Cognition backend: stub (alternating), deterministic_stub, or model (default: stub)",
    )
    parser.add_argument(
        "--answer",
        type=str,
        default=None,
        help="Answer a pending question by question_id",
    )
    parser.add_argument(
        "--answer-text",
        type=str,
        default=None,
        help="Text of the answer to the question specified by --answer (required with --answer)",
    )
    parser.add_argument(
        "--answer-all",
        action="store_true",
        help="Answer all three standing human questions with prescribed operator text",
    )
    parser.add_argument(
        "--grant-capability",
        type=str,
        default=None,
        help="Grant a capability to the pair (e.g. 'movement')",
    )
    parser.add_argument(
        "--grant-scope",
        type=str,
        default="first-pair-shared-habitat",
        help="Scope of the capability grant (default: first-pair-shared-habitat)",
    )
    parser.add_argument(
        "--grant-reason",
        type=str,
        default=None,
        help="Reason for the capability grant",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="",
        help="Optional run identifier for evidence export",
    )

    args = parser.parse_args()

    # --- Validate arguments ---
    if args.answer is not None:
        if not args.answer_text or not args.answer_text.strip():
            sys.exit("error: --answer requires non-empty --answer-text")
    if args.answer_text is not None and args.answer is None:
        sys.exit("error: --answer-text requires --answer")
    if args.grant_capability and not args.grant_reason:
        sys.exit("error: --grant-capability requires --grant-reason")

    root: Path | None = Path(args.root) if args.root else None
    export_path: Path | None = Path(args.export) if args.export else None

    store = FirstPairPersistenceStore(root)

    # --- determine whether we are initialising or resuming ---
    integrity = validate_persistence_integrity(store)
    existing = any(integrity.values())
    state_label = "resumed" if existing else "initialised"

    # --- handle --answer (single question) ---
    if args.answer:
        result = mark_question_answered(
            store, args.answer, args.answer_text.strip(),
            provenance="operator_script",
        )
        if result is None:
            sys.exit(f"error: question {args.answer} not found in store")
        print(f"Answered: {result['question_id']}")
        print(f"  Question: {result.get('question', '')[:120]}")
        print(f"  Answer:   {result.get('provenance', {}).get('answer', '')[:120]}")
        print(f"  Status:   {result.get('status', '')}")

    # --- handle --answer-all (all three questions, zero heartbeats) ---
    if args.answer_all:
        n_answered = _answer_all_questions(store)
        if n_answered == 0:
            print("Warning: no questions found to answer (already answered or not found)")
        else:
            print(f"Answered {n_answered} question(s)")

    # --- handle --grant-capability (zero heartbeats) ---
    if args.grant_capability:
        grant = grant_capability(
            store,
            capability_id=args.grant_capability,
            scope=args.grant_scope,
            reason=args.grant_reason,
            operator_provenance="operator_script",
        )
        print(f"Granted: {grant.capability_id}")
        print(f"  Grant ID: {grant.grant_id}")
        print(f"  Scope:    {grant.scope}")
        print(f"  Reason:   {grant.reason}")
        print(f"  Status:   {grant.status}")
        print(f"  Commitment: {grant.integrity_commitment[:16]}...")

    # --- run the runtime only when heartbeats > 0 ---
    if heartbeats(args) == 0 and not args.answer and not args.answer_all and not args.grant_capability:
        results = {"heartbeats_completed": 0, "errors": []}
        # Still load state so we can report
        runtime = FirstPairRuntime(
            persistence_root=root,
            heartbeat_limit=1,
            backend=args.backend,
        )
        runtime._load_or_initialize()
    elif heartbeats(args) == 0:
        results = {"heartbeats_completed": 0, "errors": []}
        runtime = FirstPairRuntime(
            persistence_root=root,
            heartbeat_limit=1,
            backend=args.backend,
        )
        runtime._load_or_initialize()
    else:
        runtime = FirstPairRuntime(
            persistence_root=root,
            heartbeat_limit=heartbeats(args),
            backend=args.backend,
        )
        results = runtime.run()

    # --- gather state ---
    adam_view = runtime._agent_view("east_adam") if runtime._identity_record else {}
    eve_view = runtime._agent_view("east_eve") if runtime._identity_record else {}

    goals = load_goals(store)
    memory = load_memory(store)
    history = load_heartbeat_history(store)
    unanswered = list_unanswered_questions(store)
    world_obj = dict(runtime._world_state.public_objects) if runtime._world_state else {}

    # --- report ---
    print(f"State:        {state_label}")
    print(f"Backend:      {args.backend}")
    print(f"Adam ID:      {adam_view.get('agent_id', '?')}")
    print(f"Eve ID:       {eve_view.get('agent_id', '?')}")
    print(f"Heartbeats:   {results['heartbeats_completed']} completed"
          f" (total on disk: {len(history)})")
    print(f"Adam memory:  {len(memory.get('east_adam', []))} entries")
    print(f"Eve memory:   {len(memory.get('east_eve', []))} entries")
    print(f"Goals:        {len(goals)}")
    for g in goals:
        print(f"  [{g.status}] {g.goal_id}: {g.description}")
    print(f"Public objects: {len(world_obj)}")
    for oid, o in sorted(world_obj.items()):
        o = o or {}
        print(f"  {oid}: type={o.get('object_type','?')} tile={o.get('tile_id','?')} "
              f"creator={o.get('creator_agent_id','?')[0:20]} hb={o.get('created_heartbeat','?')}")
    if args.questions:
        print(f"Pending questions: {len(unanswered)}")
        for q in unanswered:
            text = q.question[:80] if hasattr(q, 'question') else str(q)[:80]
            print(f"  {q.question_id}: {text}")
    else:
        print(f"Pending questions: {len(unanswered)} (use --questions to list)")

    if export_path:
        runtime.export_evidence(export_path, run_id=args.run_id)
        print(f"Evidence:     {export_path}")

    if results.get("errors"):
        for e in results["errors"]:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def heartbeats(args: argparse.Namespace) -> int:
    """Return effective heartbeat count from args.

    Answer and grant operations always run zero heartbeats regardless of --heartbeats.
    """
    if args.answer or args.answer_all or args.grant_capability:
        return 0
    return args.heartbeats if args.heartbeats is not None else 5


if __name__ == "__main__":
    main()
