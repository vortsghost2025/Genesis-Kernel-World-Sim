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
    load_agent_question_proposals,
    load_operator_messages,
    save_agent_question_proposals,
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


def _resolve_asks(
    store: FirstPairPersistenceStore, addressed_to: str, text: str, msg_id: str
) -> int:
    """Mark unheard questions matching the recipient as answered."""
    records = load_agent_question_proposals(store)
    modified = False
    now_utc = datetime.now(timezone.utc).isoformat()
    resolved = 0
    for rec in records:
        if rec.get("status") != "unheard":
            continue
        agent = rec.get("agent_ref")
        if addressed_to != "all" and agent != addressed_to:
            continue
        rec["status"] = "answered"
        rec["answered_at_utc"] = now_utc
        rec["operator_message_id"] = msg_id
        rec["operator_answer"] = text[:300]
        modified = True
        resolved += 1
    if modified:
        save_agent_question_proposals(store, records)
    return resolved


def say(
    pair: str,
    text: str,
    addressed_to: str = "all",
    author: str = "the operator",
    resolve_asks: bool = True,
) -> dict:
    store_root = PAIRS[pair]
    if not store_root.is_dir():
        raise SystemExit(f"OPERATOR_SAY_ERROR: no such pair store: {store_root}")
    text = (text or "").strip()
    if not text:
        raise SystemExit("OPERATOR_SAY_ERROR: empty --text")
    msg_id = _message_id(author, addressed_to, text)
    message = {
        "message_id": msg_id,
        "author": author,
        "addressed_to": addressed_to,
        "text": text[:MAX_TEXT],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "operator-authored; noncanonical; no authority over agents",
    }
    store = FirstPairPersistenceStore(store_root)
    append_operator_message(store, message)
    resolved = 0
    if resolve_asks:
        resolved = _resolve_asks(store, addressed_to, text, msg_id)
    message["resolved_asks"] = resolved
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
    ap.add_argument(
        "--no-resolve",
        action="store_true",
        help="do not auto-mark matching unheard asks as answered",
    )
    args = ap.parse_args()

    if args.history:
        print(history(None if args.pair == "both" else args.pair))
        return 0

    targets = list(PAIRS) if args.pair == "both" else [args.pair]
    for name in targets:
        message = say(
            name,
            args.text,
            args.to,
            args.author,
            resolve_asks=not args.no_resolve,
        )
        resolved_info = (
            f" resolved={message.get('resolved_asks', 0)}"
            if message.get("resolved_asks")
            else ""
        )
        print(
            f"OPERATOR_SAY=OK pair={name} id={message['message_id']} "
            f"to={args.to} author={args.author}{resolved_info}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
