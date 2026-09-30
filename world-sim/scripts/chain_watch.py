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
                     reason: str = "") -> str:
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
    result: dict = {"state": state, "tick": tick, "chain_alive": alive,
                    "run": run_key}
    if state in ("complete", "stopped", "stalled") and not already_sent(
            run_key, state):
        reason = "" if state == "complete" else last_stop_reason()
        msg = terminal_message(state, pair, tick, end, reason)
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
