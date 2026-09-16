"""First-pair living loop — bounded, operator-launched, real-model heartbeats.

Grants the movement capability through the existing governed
``grant_capability`` seam (zero heartbeats, sealed, provenance-recorded), then
runs a bounded ``FirstPairRuntime`` sequence with the real model cognition
backend resolved from the environment (NVIDIA GLM 5.3 Flash or local Ollama).

Each heartbeat: Adam and Eve each run a full cognitive cycle
(observe -> model -> proposed action -> reflect), the runtime executes the
proposed action against the movement-grant topology, and state persists to the
selected store.

Usage (from world-sim/):
    $env:NVIDIA_API_KEY = "<key>"
    $env:GENESIS_FIRST_PAIR_MODEL = "z-ai/glm-5.3-flash"
    python scripts/run_first_pair_living_loop.py --heartbeats 2

Scratch dry run (isolated temp store, never canonical):
    python scripts/run_first_pair_living_loop.py --heartbeats 1 --scratch
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from backend.world.first_pair_persistence import (
    FirstPairPersistenceStore,
    grant_capability,
    load_capability_grant,
)
from backend.world.first_pair_runtime import FirstPairRuntime
from backend.world.first_pair_cognition_model import (
    resolve_provider,
    sanitize_provider_error,
)


def _safe(text: object, maximum: int = 160) -> str:
    raw = "" if text is None else str(text)
    cleaned = "".join(ch if 32 <= ord(ch) < 127 or ch in "\n\t" else "?" for ch in raw)
    return cleaned.replace("\n", " ")[:maximum]


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded first-pair living loop")
    parser.add_argument("--heartbeats", type=int, default=2,
                        help="Bounded heartbeat count (default 2)")
    parser.add_argument("--scratch", action="store_true",
                        help="Run against an isolated temp store, never canonical")
    parser.add_argument("--evidence", type=str, default="",
                        help="Optional evidence export path (JSON)")
    args = parser.parse_args()

    if args.heartbeats < 1 or args.heartbeats > 16:
        print("LIVING_LOOP=FAIL heartbeats must be 1..16")
        return 1

    try:
        config = resolve_provider()
    except Exception as exc:
        print(f"LIVING_LOOP=FAIL resolve_provider: {sanitize_provider_error(exc)}")
        return 1
    print(f"PROVIDER={config.provider_type} MODEL={config.model}")

    if args.scratch:
        root = Path(tempfile.mkdtemp(prefix="genesis-living-loop-scratch-"))
        print(f"STORE=SCRATCH {root}")
    else:
        root = None
        print("STORE=CANONICAL")

    store = FirstPairPersistenceStore(root)

    existing_grant = load_capability_grant(store)
    if existing_grant is not None and existing_grant.status == "granted" \
            and existing_grant.capability_id == "movement":
        print(f"MOVEMENT_GRANT=EXISTING {existing_grant.grant_id}")
    else:
        grant = grant_capability(
            store,
            capability_id="movement",
            scope="canonical 3-tile habitat topology, one edge per heartbeat",
            reason=(
                "Operator-authorized first-pair activation: Adam and Eve may "
                "explore the shared starting habitat they already understand "
                "(q1-habitat-structure answered)."
            ),
            operator_provenance="sean-operator-auto-activation-2026-09-14",
        )
        print(f"MOVEMENT_GRANT=GRANTED {grant.grant_id}")

    runtime = FirstPairRuntime(
        persistence_root=root,
        heartbeat_limit=args.heartbeats,
        backend="model",
    )
    try:
        results = runtime.run()
    except Exception as exc:
        print(f"LIVING_LOOP=FAIL runtime: {sanitize_provider_error(exc)}")
        return 1

    print(f"HEARTBEATS_COMPLETED={results.get('heartbeats_completed', 0)}")
    for err in results.get("errors", []):
        print(f"RUNTIME_ERROR={_safe(err)}")

    evidence_path = None
    if args.evidence:
        evidence_path = Path(args.evidence)
    elif args.scratch:
        evidence_path = Path(tempfile.gettempdir()) / "genesis-living-loop-scratch-evidence.json"
    if evidence_path is not None:
        try:
            exported = runtime.export_evidence(
                evidence_path, run_id=f"living-loop-{config.provider_type}"
            )
            print(f"EVIDENCE={evidence_path}")
        except Exception as exc:
            print(f"EVIDENCE_EXPORT_SKIPPED={_safe(exc)}")
    else:
        print("EVIDENCE=NONE (no path requested; use export_first_pair_state_evidence.py)")

    print(f"ADAM_COGNITION={_safe(runtime._current_run_cognition['east_adam']['decision_summary'])}")
    print(f"EVE_COGNITION={_safe(runtime._current_run_cognition['east_eve']['decision_summary'])}")

    ok = results.get("heartbeats_completed", 0) > 0 and not results.get("errors")
    print("LIVING_LOOP=OK" if ok else "LIVING_LOOP=PARTIAL")
    return 0 if results.get("heartbeats_completed", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
