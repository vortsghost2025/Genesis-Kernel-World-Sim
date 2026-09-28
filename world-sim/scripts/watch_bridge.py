"""Watch bridge: turn a watcher alert into a resumed operator turn.

`agent_watch.py` is deliberately read-only and never answers on your behalf
(see its own docstring: "the operator's voice stays a human's"). This is the
separate, explicit act that honours the standing delegation in AGENTS.md
rule 7 - I may answer the agents' factual questions in the operator's
register, but only in a turn where I can see what I am doing.

The bridge polls the watcher's dedupe ledger for signals that are NEW since
the last time it looked. On an `ask` (an agent is asking a question) or a
`stuck` (an agent is being refused the same way, repeatedly) it spawns:

    opencode run -c "<brief>"

which continues the most recent opencode session - this one - with a short
brief. That is the nudge: the agents need an operator, an operator turn
starts, and the operator (me, with the full session context and the
delegated authority) reads the inbox and answers.

Hard properties:

  * READ-ONLY with respect to the sim. This script never writes to a store,
    never runs a heartbeat, and never answers an agent itself. It only
    decides when to ask a session to look.
  * BUDGETED. `--max-invocations` and `--cooldown-seconds` are real caps.
    Every invocation costs a model turn, so the default is deliberately
    stingy: 3 nudges, 15 minutes apart.
  * IDEMPOTENT. A signal is nudged once, ever, per bridge ledger. Restarting
    the bridge does not re-nudge old alerts.
  * INFORMATIONAL signals never nudge. `first_build` and `dead` go to
    Telegram only; they are not a reason to spend a turn.

Usage:
    python world-sim/scripts/watch_bridge.py --once --dry-run
    python world-sim/scripts/watch_bridge.py --interval 120
    python world-sim/scripts/watch_bridge.py --status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
WATCH_SCRATCH = WORLD_SIM / ".scratch" / "agent_watch"
WATCH_LEDGER = WATCH_SCRATCH / "ledger.json"
BRIDGE_SCRATCH = WORLD_SIM / ".scratch" / "watch_bridge"
BRIDGE_LEDGER = BRIDGE_SCRATCH / "nudged.json"
BRIDGE_LOG = BRIDGE_SCRATCH / "bridge.log"
BRIDGE_STATUS = BRIDGE_SCRATCH / "status.json"

# Signals that mean "an agent is stuck and needs an operator turn".
NUDGE_KINDS = {"ask", "stuck"}

DEFAULT_MAX_INVOCATIONS = 3
DEFAULT_COOLDOWN_SECONDS = 900

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000

BRIEF = (
    "Genesis operator turn, triggered automatically by watch_bridge because "
    "an agent signal needs a human.\n\n"
    "Do exactly this, in order, and then stop:\n"
    "1. Run: python world-sim/scripts/operator_inbox.py  (read-only)\n"
    "2. If an agent asked a FACTUAL question, answer it with "
    "scripts/operator_say.py under the standing delegation in AGENTS.md rule "
    "7: state only what is true or what changed. NEVER give strategy, "
    "directions, or build instructions. If a question needs an operator "
    "decision you do not have delegated authority for, say so instead of "
    "guessing.\n"
    "3. Re-read world-sim/docs/heartbeat_runner_integrity_spec.md and "
    "world-sim/docs/build_meaning_spec.md if relevant, for the register on "
    "what is true.\n"
    "4. Report to Sean in plain language: what the agents are up to, what "
    "you answered, what needs his decision. No raw traces.\n\n"
    "Do NOT start a heartbeat, change physics, commit, or push. Heartbeats "
    "remain one-per-explicit-authorization."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")


def load_nudged(path: Path | None = None) -> dict:
    return _read_json(Path(path) if path else BRIDGE_LEDGER)


def _parse(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def pending_nudges(ledger: dict, nudged: dict, since: str | None = None) -> list[dict]:
    """Watcher ledger keys that are new, nudging, and after the watermark.

    `since` is the baseline timestamp. Anything at or before it was absorbed
    when the bridge started and can never trigger a turn - that is the whole
    reason the watermark exists.
    """
    cutoff = _parse(since)
    out = []
    for key, rec in (ledger.get("fired") or {}).items():
        if key in nudged:
            continue
        if rec.get("kind") not in NUDGE_KINDS:
            continue
        if cutoff is not None and _parse(rec.get("fired_at_utc")) is not None:
            if _parse(rec.get("fired_at_utc")) <= cutoff:
                continue
        out.append({"key": key, **rec})
    out.sort(key=lambda r: r.get("fired_at_utc", ""))
    return out


def build_command(limit: int = 1) -> list[str]:
    """The command that resumes the operator session.

    `-c` continues the most recent session, which is this one - so the
    resumed turn inherits the full context, not a blank slate.
    """
    return [
        "opencode", "run", "-c",
        "--title", "genesis operator turn (auto)",
        BRIEF,
    ]


def spawn(cmd: list[str], dry_run: bool = False) -> dict:
    if dry_run:
        return {"spawned": False, "dry_run": True, "cmd": cmd}
    flags = (
        DETACHED_PROCESS
        | CREATE_NEW_PROCESS_GROUP
        | CREATE_BREAKAWAY_FROM_JOB
        | CREATE_NO_WINDOW
    )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(WORLD_SIM),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception as exc:
        return {"spawned": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return {"spawned": True, "pid": proc.pid}


def log(message: str) -> None:
    BRIDGE_SCRATCH.mkdir(parents=True, exist_ok=True)
    with open(BRIDGE_LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{_utc_now()} {message}\n")


def seed_baseline(watcher: dict, state: dict) -> dict:
    """First run absorbs the existing backlog instead of replaying it.

    The watcher ledger holds every signal since the watcher was first started -
    111 of them, most of them questions already answered in past turns. A
    bridge that nudged on "anything not yet nudged" would fire a burst of
    operator turns on stale alerts the moment it started.

    So the first scan records a watermark: every signal that already exists is
    marked seen, and nothing is nudged. Only signals that appear AFTER this
    point can ever trigger a turn. An already-answered question therefore
    cannot be answered twice, without the bridge needing to know anything
    about which questions were answered.
    """
    fired = dict(state.get("nudged", {}))
    existing = watcher.get("fired") or {}
    seeded = 0
    for key, rec in existing.items():
        if key not in fired:
            fired[key] = rec.get("fired_at_utc", _utc_now())
            seeded += 1
    payload = {
        "updated_at_utc": _utc_now(),
        "baselined_at_utc": state.get("baselined_at_utc") or _utc_now(),
        "nudged": fired,
        "invocations": state.get("invocations", 0),
        "last_invocation_utc": state.get("last_invocation_utc"),
        "max_invocations": state.get("max_invocations"),
    }
    _write_json(BRIDGE_LEDGER, payload)
    log(f"baseline seeded: absorbed={seeded} existing={len(existing)}")
    return {"action": "baseline_seeded", "absorbed": seeded,
            "existing": len(existing), "nudged": 0,
            "invocations": state.get("invocations", 0)}


def run_once(
    dry_run: bool = False,
    max_invocations: int = DEFAULT_MAX_INVOCATIONS,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
) -> dict:
    watcher = _read_json(WATCH_LEDGER)
    state = load_nudged()
    if not state.get("baselined_at_utc"):
        return seed_baseline(watcher, state)
    fired = state.get("nudged", {})
    used = state.get("invocations", 0)
    last = state.get("last_invocation_utc")
    last_dt = None
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            last_dt = None

    if used >= max_invocations:
        return {"action": "budget_exhausted", "invocations": used,
                "max_invocations": max_invocations}
    if last_dt is not None:
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        if elapsed < cooldown_seconds:
            return {"action": "cooldown", "seconds_remaining":
                    int(cooldown_seconds - elapsed), "invocations": used}

    pending = pending_nudges(watcher, fired, since=state.get("baselined_at_utc"))
    if not pending:
        return {"action": "idle", "pending": 0, "invocations": used}

    # Mark every pending nudging signal as seen, so one turn covers the batch
    # and a restart cannot re-nudge them.
    for rec in pending:
        fired[rec["key"]] = rec.get("fired_at_utc", _utc_now())

    result = spawn(build_command(), dry_run=dry_run)
    log(f"nudge pending={[r['key'] for r in pending]} spawn={result}")

    if result.get("spawned") or result.get("dry_run"):
        used += 1
    _write_json(BRIDGE_LEDGER, {
        "updated_at_utc": _utc_now(),
        "baselined_at_utc": state.get("baselined_at_utc") or _utc_now(),
        "nudged": fired,
        "invocations": used,
        "last_invocation_utc": _utc_now(),
        "max_invocations": max_invocations,
    })
    status = {
        "updated_at_utc": _utc_now(),
        "action": "nudged",
        "signals": [r["key"] for r in pending],
        "invocations": used,
        "max_invocations": max_invocations,
        "pid": result.get("pid"),
    }
    _write_json(BRIDGE_STATUS, status)
    return status


def run_forever(interval: int, dry_run: bool, max_invocations: int,
                cooldown_seconds: int) -> None:
    print(f"BRIDGE=UP interval={interval}s dry_run={dry_run} "
          f"max={max_invocations} cooldown={cooldown_seconds}s", flush=True)
    while True:
        try:
            out = run_once(dry_run, max_invocations, cooldown_seconds)
            if out.get("action") == "nudged":
                print(f"[{_utc_now()}] nudged {out.get('signals')}", flush=True)
        except Exception as exc:
            print(f"BRIDGE_ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(10, interval))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true", help="one scan and exit")
    p.add_argument("--interval", type=int, default=120, help="seconds between scans")
    p.add_argument("--dry-run", action="store_true",
                   help="print the command instead of spawning it")
    p.add_argument("--max-invocations", type=int, default=DEFAULT_MAX_INVOCATIONS,
                   help="hard cap on operator turns this bridge may request")
    p.add_argument("--cooldown-seconds", type=int, default=DEFAULT_COOLDOWN_SECONDS,
                   help="minimum seconds between operator turns")
    p.add_argument("--status", action="store_true", help="print bridge status")
    p.add_argument("--pending", action="store_true",
                   help="report pending nudges without acting")
    args = p.parse_args()

    if args.status:
        print(BRIDGE_STATUS.read_text(encoding="utf-8")
              if BRIDGE_STATUS.is_file() else "no bridge status yet")
        return 0
    if args.pending:
        watcher = _read_json(WATCH_LEDGER)
        state = load_nudged()
        pending = pending_nudges(watcher, state.get("nudged", {}),
                                since=state.get("baselined_at_utc"))
        print(json.dumps({
            "baselined_at_utc": state.get("baselined_at_utc"),
            "pending": pending,
            "invocations_used": state.get("invocations", 0),
            "watcher_signals": len(watcher.get("fired") or {}),
        }, indent=2))
        return 0
    if args.once:
        print(json.dumps(run_once(args.dry_run, args.max_invocations,
                                  args.cooldown_seconds), indent=2))
        return 0
    run_forever(args.interval, args.dry_run, args.max_invocations,
                args.cooldown_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
