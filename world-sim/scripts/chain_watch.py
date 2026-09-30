"""Chain run monitor: distinct terminal messages, never silence.

The watcher reports store idleness (`dead`) identically for finished-OK and
died-badly, says nothing about why, and is itself silent if it dies. This
script watches ONE run: Telegrams on start (with target), then exactly one
terminal message — complete, hard-stop with the log's reason, or stalled
(tick unmoved beyond budget with the chain gone quiet).

Dedupe: one terminal state sends once, ever, per ledger. Restarting the
monitor cannot replay a terminal message.

Usage:
    python world-sim/scripts/chain_watch.py --pair east --start 1044 --end 1143 --chain-pid 1234
    python world-sim/scripts/chain_watch.py --status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
WATCH_SCRATCH = WORLD_SIM / ".scratch" / "chain_watch"
LEDGER = WATCH_SCRATCH / "runs.json"

# A heartbeat lands every ~2-3 min; 30 min without movement while the chain
# is supposed to be running means dead-or-wedged, not slow.
STALL_BUDGET_S = 1800
POLL_S = 120

# Inert-heartbeat budget. The tick measures the CLOCK, not the world: a
# chain whose model route is dead keeps ticking and keeps logging "OK"
# while both agents take no action at all. Proven on 2026-09-30 - the
# nvidia/* routes began returning 502/403 upstream, and HB1198-1243 ran 46
# consecutive heartbeats with zero actions while the chain reported success
# and this watcher reported "complete". Five consecutive fully-inert
# heartbeats (~10-15 min at the live cadence) is past any transient: a
# single 429 or one dead key is a dead heartbeat, not a dead world.
INERT_TAIL_THRESHOLD = 5


def run_health(heartbeats: list[dict]) -> dict:
    """Is the sim actually living, or just the clock?

    A heartbeat is INERT when no agent acted — `action_taken` absent, or
    present with every agent entry null. Anything either agent did counts
    as life, so a run where one agent is silent but the other works is
    alive, not frozen.

    Returns {verdict, inert_tail, last_active_heartbeat, heartbeats_seen}.
    `verdict` is "frozen" once the inert tail reaches
    INERT_TAIL_THRESHOLD, "healthy" while short of it, and "unknown" when
    there is no history at all: absence of evidence is not evidence of a
    dead world, and this monitor has already learned that a monitor which
    invents death from its own read failure is worse than silent.
    """
    rows = [r for r in heartbeats if isinstance(r, dict)]
    if not rows:
        return {"verdict": "unknown", "inert_tail": 0,
                "last_active_heartbeat": None, "heartbeats_seen": 0}

    def acted(row: dict) -> bool:
        acts = row.get("action_taken") or {}
        if not isinstance(acts, dict):
            return False
        return any(isinstance(a, dict) and a.get("action_type") not in
                   (None, "", "no_action") for a in acts.values())

    inert_tail = 0
    last_active = None
    for row in rows:
        n = row.get("heartbeat_number")
        if acted(row):
            inert_tail = 0
            last_active = n
        else:
            inert_tail += 1
    verdict = "frozen" if inert_tail >= INERT_TAIL_THRESHOLD else "healthy"
    return {"verdict": verdict, "inert_tail": inert_tail,
            "last_active_heartbeat": last_active,
            "heartbeats_seen": len(rows)}


def load_heartbeats(pair: str, limit: int = 60) -> list[dict]:
    """Most recent heartbeat records for a pair, oldest-first.

    Reads the store's own heartbeat ledger. Returns [] when unreadable —
    never a fabricated history.
    """
    data = _read_json(STORES.get(pair, STORES["east"]) / "heartbeat.json")
    rows = data.get("data", data)
    if not isinstance(rows, list):
        return []
    rows = [r for r in rows if isinstance(r, dict)]
    return rows[-limit:] if limit else rows


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8",
                    newline="\n")


def store_tick(pair: str) -> int | None:
    ws = STORES[pair] / "world_state.json"
    data = _read_json(ws)
    inner = data.get("data", data)
    tick = inner.get("tick")
    return tick if isinstance(tick, int) else None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import psutil  # type: ignore
        return psutil.Process(pid).is_running()
    except Exception:
        pass
    try:
        import os
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def classify(tick: int | None, target_end: int, chain_alive: bool,
             seconds_since_move: float) -> str:
    """One of: complete, stopped, stalled, running, unknown.

    Pure function — the unit under test. `tick is None` (unreadable store)
    is unknown, never a terminal state: a monitor must not declare death
    from its own read failure.
    """
    if tick is None:
        return "unknown"
    if tick >= target_end:
        return "complete"
    if not chain_alive:
        return "stopped"
    if seconds_since_move > STALL_BUDGET_S:
        return "stalled"
    return "running"


def terminal_message(state: str, pair: str, tick: int | None, target_end: int,
                     reason: str = "", inert_tail: int | None = None) -> str:
    if state == "frozen":
        span = f" for the last {inert_tail} heartbeats" if inert_tail else ""
        return (f"Genesis: the agents have stopped acting{span}. {pair} is at "
                f"HB{tick} of a run targeting {target_end}, and NEITHER agent "
                f"has taken an action. The clock is still advancing; the "
                f"world is not. This is a model/provider failure, not a "
                f"result about the agents - these heartbeats are not "
                f"evidence. Needs a human look.")
    if state == "complete":
        return (f"Genesis: census run complete. {pair} reached HB{target_end} "
                f"(100 heartbeats, no action needed).")
    if state == "stopped":
        return (f"Genesis: chain STOPPED at HB{tick} (target {target_end}). "
                f"{reason} I am idle; nothing will advance until a human "
                f"looks. No data lost: the store is intact at HB{tick}.")
    if state == "stalled":
        return (f"Genesis: chain STALLED at HB{tick} (target {target_end}, "
                f"no movement in 30+ min). {reason} Needs a human look.")
    return ""


def _load_ledger() -> dict:
    return _read_json(LEDGER)


def already_sent(run_key: str, state: str) -> bool:
    return _load_ledger().get(run_key, {}).get(state, False)


def mark_sent(run_key: str, state: str) -> None:
    ledger = _load_ledger()
    entry = ledger.get(run_key, {})
    entry[state] = {"at_utc": _utc_now()}
    ledger[run_key] = entry
    _write_json(LEDGER, ledger)


def send_telegram_text(text: str) -> tuple[bool, str]:
    """Best-effort Telegram; failures are returned, never raised.

    Shapes the message as a watcher signal so the shared render path is
    reused exactly — one format on the channel, no drift.
    """
    sys.path.insert(0, str(WORLD_SIM / "scripts"))
    try:
        from agent_watch import send_telegram
    except Exception as exc:
        return False, f"import: {type(exc).__name__}"
    import os
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        # Fall back to User-level env (where the operator keeps them).
        return False, "telegram not configured in process env"
    sig = {
        "severity": "info",
        "title": "run monitor",
        "pair": "-",
        "agent": "-",
        "heartbeat": "-",
        "body": text,
    }
    try:
        return send_telegram(sig, token, chat)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"


def chain_log_tail(n: int = 6) -> list[str]:
    logs = sorted((WORLD_SIM / ".scratch" / "lockstep").glob("chain_*.log"))
    if not logs:
        return []
    try:
        return logs[-1].read_text(
            encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def last_stop_reason() -> str:
    tail = chain_log_tail(8)
    for line in reversed(tail):
        if "HARD STOP" in line or "FAILED after" in line or "TIMEOUT" in line:
            return line.strip()[:160]
    return "no reason in chain log tail."


def monitor_once(pair: str, start: int, end: int,
                 chain_pid: int | None) -> dict:
    run_key = f"{pair}:{start}-{end}"
    tick = store_tick(pair)
    alive = pid_alive(chain_pid)
    # Movement clock: newest evidence/status mtime in the lockstep dir.
    move_age = _seconds_since_last_evidence()
    state = classify(tick, end, alive, move_age)
    health = run_health(load_heartbeats(pair))
    # A run that produced no actions is not succeeding, whether or not it
    # has reached its target. Reaching the end is a property of the clock;
    # the agents acting is a property of the world. Proven on 2026-09-30,
    # when 46 dead heartbeats were reported to the operator as a completed
    # census and nobody knew the sim had been frozen since HB1198.
    if health["verdict"] == "frozen":
        state = "frozen"
    result: dict = {"state": state, "tick": tick, "chain_alive": alive,
                    "run": run_key, "health": health}
    if state in ("complete", "stopped", "stalled", "frozen") and \
            not already_sent(run_key, state):
        reason = "" if state in ("complete", "frozen") else last_stop_reason()
        msg = terminal_message(state, pair, tick, end, reason,
                               inert_tail=health["inert_tail"])
        ok, detail = send_telegram_text(msg)
        result["notified"] = ok
        result["notify_detail"] = detail
        if ok:
            mark_sent(run_key, state)
    else:
        result["notified"] = False
    return result


def _seconds_since_last_evidence() -> float:
    d = WORLD_SIM / ".scratch" / "lockstep"
    try:
        mtimes = [p.stat().st_mtime for p in d.glob("lockstep_*")
                  if p.is_file()]
    except OSError:
        return float("inf")
    if not mtimes:
        return float("inf")
    return time.time() - max(mtimes)


def announce_start(pair: str, start: int, end: int) -> dict:
    run_key = f"{pair}:{start}-{end}"
    if already_sent(run_key, "started"):
        return {"announced": False, "reason": "already announced"}
    msg = (f"Genesis: census run started. {pair} HB{start}-{end} "
           f"({end - start + 1} heartbeats, ~4h). I will message on "
           f"complete, stop, or stall — silence from me means running.")
    ok, detail = send_telegram_text(msg)
    if ok:
        mark_sent(run_key, "started")
    return {"announced": ok, "detail": detail}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", default="east")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=0)
    p.add_argument("--chain-pid", type=int, default=None)
    p.add_argument("--once", action="store_true")
    p.add_argument("--announce", action="store_true")
    p.add_argument("--status", action="store_true")
    args = p.parse_args(argv)
    if args.status:
        print(json.dumps(_load_ledger(), indent=2))
        return 0
    if args.announce:
        print(json.dumps(announce_start(args.pair, args.start, args.end),
                         indent=2))
        return 0
    if args.once:
        print(json.dumps(monitor_once(args.pair, args.start, args.end,
                                      args.chain_pid), indent=2))
        return 0
    print(f"CHAIN_WATCH=UP run={args.pair}:{args.start}-{args.end}",
          flush=True)
    while True:
        try:
            out = monitor_once(args.pair, args.start, args.end, args.chain_pid)
            if out.get("state") in ("complete", "stopped", "stalled") \
                    and out.get("notified"):
                print(f"[{_utc_now()}] terminal {out['state']} notified",
                      flush=True)
        except Exception as exc:
            print(f"CHAIN_WATCH_ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
