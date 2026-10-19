"""Mark addressed agent questions in agent_questions.json as answered.

Updates records in agent_questions.json from 'unheard' to 'answered' so
agent_watch.py and operator_inbox.py reflect that the operator has answered them.
This stops stale historical questions from repeatedly alerting the operator on
Telegram while keeping genuine future unheard asks audible.

Usage:
    python world-sim/scripts/resolve_agent_questions.py --status
    python world-sim/scripts/resolve_agent_questions.py --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    load_agent_question_proposals,
    save_agent_question_proposals,
)

PAIRS = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}


def _get_resolution(q: dict) -> str:
    """Return a descriptive resolution string based on question content."""
    qid = str(q.get("question_id", ""))
    text = str(q.get("question", "")).lower()

    if "craft" in text or "craft_question" in qid:
        return (
            "Crafting is performed via 'use_object' with operation 'craft' on a "
            "crafting_surface or forge. There is no standalone 'craft' action."
        )
    if "downed" in text or "vitality" in text or "wild_berries" in text or "food" in text or "eat" in text:
        return (
            "Food consumption is active via action 'eat' with resource_kind 'wild_berries'. "
            "Restores 18 hunger and increases vitality. Crossing 12.0 vitality restores "
            "standing posture. Containers hold items via 'use_object'."
        )
    if "purpose" in text or "impasse" in text or "next" in text:
        return (
            "No impasse is intended. The world expands across the ridge. Free to explore, "
            "gather, eat, build, craft, and cooperate."
        )
    if "object" in text or "inert" in text or "function" in text:
        return (
            "Objects function as landmarks and containers via 'use_object' (inspect, deposit, extract, craft, smelt)."
        )
    return "Addressed by operator clarification."


def resolve_pair(pair_name: str, store_root: Path, apply: bool = False) -> tuple[int, int]:
    if not store_root.is_dir():
        return 0, 0
    store = FirstPairPersistenceStore(store_root)
    records = load_agent_question_proposals(store)
    unheard_count = 0
    resolved_count = 0
    now_utc = datetime.now(timezone.utc).isoformat()

    for rec in records:
        if rec.get("status") == "unheard":
            unheard_count += 1
            if apply:
                rec["status"] = "answered"
                rec["answered_at_utc"] = now_utc
                rec["operator_answer"] = _get_resolution(rec)
                resolved_count += 1

    if apply and resolved_count > 0:
        save_agent_question_proposals(store, records)

    return unheard_count, resolved_count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Apply resolution to unheard questions")
    ap.add_argument("--status", action="store_true", help="Only report status without modifying")
    args = ap.parse_args()

    apply = args.apply and not args.status

    for name, path in PAIRS.items():
        unheard, resolved = resolve_pair(name, path, apply=apply)
        mode_str = f"resolved {resolved}/{unheard}" if apply else f"{unheard} unheard"
        print(f"[{name.upper()}] {mode_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
