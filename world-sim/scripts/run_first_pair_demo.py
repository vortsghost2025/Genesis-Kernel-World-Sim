"""Operator script: run the First Pair bounded runtime demonstration.

Usage:
    python scripts/run_first_pair_demo.py --heartbeats 2 \\
        --root .runtime/first-pair-manual-proof \\
        --export .runtime/first-pair-manual-proof/evidence.json \\
        --seed 42 --questions --backend stub

    python scripts/run_first_pair_demo.py --heartbeats 1 --backend model

    python scripts/run_first_pair_demo.py --answer adam-question-1 \\
        --answer-text "The world is made of digital tiles."
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
    load_goals,
    load_heartbeat_history,
    load_memory,
    list_unanswered_questions,
    mark_question_answered,
    validate_persistence_integrity,
)
from backend.world.first_pair_runtime import FirstPairRuntime


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the bounded First Pair runtime demonstration."
    )
    parser.add_argument(
        "--heartbeats",
        type=int,
        default=5,
        help="Number of heartbeat cycles (default: 5; use 0 with --answer)",
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

    args = parser.parse_args()

    # --answer requires --answer-text
    if args.answer is not None:
        if not args.answer_text or not args.answer_text.strip():
            sys.exit("error: --answer requires non-empty --answer-text")
    if args.answer_text is not None and args.answer is None:
        sys.exit("error: --answer-text requires --answer")

    heartbeats = args.heartbeats
    if heartbeats < 0:
        sys.exit("error: --heartbeats must be a non-negative integer")

    root: Path | None = Path(args.root) if args.root else None
    export_path: Path | None = Path(args.export) if args.export else None

    store = FirstPairPersistenceStore(root)

    # --- determine whether we are initialising or resuming ---
    # (before --answer so state is stable)
    integrity = validate_persistence_integrity(store)
    existing = any(integrity.values())
    state_label = "resumed" if existing else "initialised"

    # --- handle --answer using the governed persistence operation ---
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

    # --- run the runtime only when heartbeats > 0 ---
    if heartbeats == 0:
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
            heartbeat_limit=heartbeats,
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
              f"creator={o.get('creator_agent_id','?')} hb={o.get('created_heartbeat','?')}")
    if args.questions:
        print(f"Pending questions: {len(unanswered)}")
        for q in unanswered:
            print(f"  {q.question_id}: {q.question[:80]}")
    else:
        print(f"Pending questions: {len(unanswered)} (use --questions to list)")

    if export_path:
        runtime.export_evidence(export_path)
        print(f"Evidence:     {export_path}")

    if results["errors"]:
        print(f"Errors:       {results['errors']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
