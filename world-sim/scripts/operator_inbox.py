"""Operator inbox: what the agents are trying to tell us.

Scans every living pair's canonical store for:
- pending ask_human questions (asked of the operator, not yet answered)
- capability_requests recorded in world_state (counts per capability,
  distinct requesting agents, last request heartbeat, sample reason)
- charters written so far (the recognition layer)
- recently answered questions (proof the loop closes)

READ-ONLY: never writes to canonical stores. Prints a human-readable summary
and (with --json OUT) writes a machine-readable copy.

Usage:
    python world-sim/scripts/operator_inbox.py
    python world-sim/scripts/operator_inbox.py --json .scratch/operator_inbox.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
PAIRS = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def agent_short(agent_id: str, identity: dict) -> str:
    idata = identity.get("data", identity)
    for key, label in (("adam_agent_id", "adam"), ("eve_agent_id", "eve")):
        if idata.get(key) == agent_id:
            return label
    return agent_id[:14]


def scan_pair(pair: str, store: Path) -> dict:
    if not (store / "world_state.json").exists():
        return {"pair": pair, "missing": True}

    world_state = read_json(store / "world_state.json")["data"]
    questions_path = store / "questions.json"
    questions = read_json(questions_path)["data"] if questions_path.exists() else []
    identity = read_json(store / "identity.json") if (store / "identity.json").exists() else {}

    pending = [
        {
            "question_id": q.get("question_id"),
            "agent": agent_short(q.get("asking_agent_id", ""), identity),
            "heartbeat": q.get("heartbeat"),
            "question": q.get("question"),
            "urgency": q.get("urgency"),
        }
        for q in questions
        if q.get("status") == "pending"
    ]
    answered = [
        {
            "question_id": q.get("question_id"),
            "agent": agent_short(q.get("asking_agent_id", ""), identity),
            "question": (q.get("question") or "")[:110],
            "answer": ((q.get("provenance") or {}).get("answer") or "")[:110],
        }
        for q in questions
        if q.get("status") == "answered"
    ]

    # capability requests live in world_state.capability_requests
    cap_reqs = world_state.get("capability_requests", [])
    per_cap: dict[str, dict] = {}
    for r in cap_reqs:
        cap = r.get("capability_id", "?")
        entry = per_cap.setdefault(cap, {
            "count": 0, "agents": set(), "last_heartbeat": 0, "sample_reason": "",
        })
        entry["count"] += 1
        entry["agents"].add(agent_short(r.get("requesting_agent_id", ""), identity))
        entry["last_heartbeat"] = max(entry["last_heartbeat"], r.get("heartbeat", 0))
        if not entry["sample_reason"]:
            entry["sample_reason"] = (r.get("reason") or "")[:200]
    for entry in per_cap.values():
        entry["agents"] = sorted(entry["agents"])

    # charters
    charters = {}
    charter_path = store / "charter.json"
    if charter_path.exists():
        for rec in read_json(charter_path).get("data", []):
            charters[rec.get("agent_ref", "?")] = {
                "text": rec.get("charter_text", ""),
                "heartbeat": rec.get("heartbeat"),
            }

    return {
        "pair": pair,
        "tick": world_state.get("tick"),
        "pending_questions": pending,
        "answered_question_count": len(answered),
        "answered_questions_recent": answered[-3:],
        "capability_requests": per_cap,
        "capability_request_total": len(cap_reqs),
        "charters": charters,
    }


def render(report: list[dict]) -> str:
    lines = []
    for p in report:
        if p.get("missing"):
            continue
        lines.append(f"=== {p['pair']} pair (tick {p.get('tick')}) ===")
        if p["pending_questions"]:
            lines.append(f"  PENDING QUESTIONS ({len(p['pending_questions'])}):")
            for q in p["pending_questions"]:
                lines.append(
                    f"    [{q['urgency'] or '?'}] {q['agent']} @HB{q['heartbeat']}: {q['question']}"
                )
        else:
            lines.append("  pending questions: none")
        if p["capability_requests"]:
            lines.append(f"  CAPABILITY REQUESTS ({p['capability_request_total']} total):")
            for cap, e in p["capability_requests"].items():
                lines.append(
                    f"    {e['count']}x '{cap}' by {','.join(e['agents'])} "
                    f"(last @HB{e['last_heartbeat']}): {e['sample_reason']}"
                )
        else:
            lines.append("  capability requests: none")
        if p["charters"]:
            lines.append(f"  CHARTERS ({len(p['charters'])}):")
            for ref, c in p["charters"].items():
                lines.append(f"    {ref} @HB{c['heartbeat']}: {c['text'][:160]}")
        else:
            lines.append("  charters: none written yet")
        if p["answered_question_count"]:
            lines.append(f"  answered questions to date: {p['answered_question_count']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default="", help="optional path for a machine-readable copy")
    args = ap.parse_args()

    report = [scan_pair(pair, store) for pair, store in PAIRS.items()]
    print(render(report))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
        print(f"INBOX_JSON={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
