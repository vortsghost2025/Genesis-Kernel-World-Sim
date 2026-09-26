"""Operator channel: the human writes to the agents.

Appends an operator-authored message to a pair's operator_messages.json —
append-only, operator-owned. The runtime only READS that file: nothing
here touches agent state, capability grants, canonical questions, or
world physics. The operator is a character who can speak, not an
authority over what any agent does.

Messages land in the agent's prompt under "MESSAGES FROM THE OPERATOR"
and in the public show payload. Addressing: "all" (both agents) or a
specific agent_ref (east_adam, west_eve, ...).

Usage:
    python world-sim/scripts/operator_say.py --text "The stone is yours."
    python world-sim/scripts/operator_say.py --pair west --to west_eve --text "..."
    python world-sim/scripts/operator_say.py --history
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"

if str(WORLD_SIM) not in sys.path:
    sys.path.insert(0, str(WORLD_SIM))

from backend.world.first_pair_persistence import (  # noqa: E402
    FirstPairPersistenceStore,
    append_operator_message,
    load_operator_messages,
)

PAIRS = {
    "east": RUNTIME_ROOT / "first-pair",
    "west": RUNTIME_ROOT / "first-pair-west",
}
MAX_TEXT = 2000


def _message_id(author: str, addressed_to: str, text: str) -> str:
    stamp = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(
        f"{author}{addressed_to}{text}{stamp}".encode("utf-8")
    ).hexdigest()[:12]
    return f"op-{digest}"


def say(pair: str, text: str, addressed_to: str = "all", author: str = "the operator") -> dict:
    store_root = PAIRS[pair]
    if not store_root.is_dir():
        raise SystemExit(f"OPERATOR_SAY_ERROR: no such pair store: {store_root}")
    text = (text or "").strip()
    if not text:
        raise SystemExit("OPERATOR_SAY_ERROR: empty --text")
    message = {
        "message_id": _message_id(author, addressed_to, text),
        "author": author,
        "addressed_to": addressed_to,
        "text": text[:MAX_TEXT],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "operator-authored; noncanonical; no authority over agents",
    }
    append_operator_message(FirstPairPersistenceStore(store_root), message)
    return message


def history(pair: str | None = None) -> str:
    pairs = [pair] if pair else list(PAIRS)
    lines = []
    for name in pairs:
        store_root = PAIRS[name]
        if not store_root.is_dir():
            continue
        messages = load_operator_messages(FirstPairPersistenceStore(store_root))
        lines.append(f"=== {name} pair: {len(messages)} operator message(s) ===")
        for m in messages[-5:]:
            lines.append(
                f"  [{m.get('author')}] -> {m.get('addressed_to')} "
                f"@ {m.get('created_at_utc')}: {m.get('text', '')[:200]}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", default="both", choices=["east", "west", "both"])
    ap.add_argument("--text", default="", help="the message to the agent(s)")
    ap.add_argument("--to", default="all", help="'all' or an agent_ref")
    ap.add_argument("--author", default="the operator")
    ap.add_argument("--history", action="store_true", help="print recent messages and exit")
    args = ap.parse_args()

    if args.history:
        print(history(None if args.pair == "both" else args.pair))
        return 0

    targets = list(PAIRS) if args.pair == "both" else [args.pair]
    for name in targets:
        message = say(name, args.text, args.to, args.author)
        print(
            f"OPERATOR_SAY=OK pair={name} id={message['message_id']} "
            f"to={args.to} author={args.author}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
