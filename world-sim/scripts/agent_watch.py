"""Agent watch: the operator's early-warning system.

The world asks questions. Right now the answers go to a file nobody
opens: an agent can be refused construction twenty times, starve, or
diagnose a real bug in plain language, and the operator inbox only
prints it when a human happens to run a script. That is how a chain
hard-stop went unnoticed and how an agent's ten unanswered questions sat
for thirty-two heartbeats.

This watcher is the missing sense. It polls the canonical stores
READ-ONLY and raises an alert when the world needs a human:

  ask          an agent asked a question (unheard)
  stuck        an agent is being refused the same way repeatedly
  starving     an agent is out of food for a sustained stretch
  dead         a heartbeat has not advanced for longer than the deadline
  first_build  an agent built something for the first time (the show)

Hard properties:
  * READ-ONLY. It never writes to a store, never touches agent state,
    never answers on your behalf. Answering is a separate, explicit act
    (scripts/operator_say.py) so the operator's voice stays a human's.
  * DEDUPED. Every signal has a stable key; a signal fires once until
    its key changes. You are not spammed 60 times a minute.
  * DEGRADED-SAFE. No credentials -> alerts still land in the durable
    log. Telegram is additive, never required.

Usage:
    python world-sim/scripts/agent_watch.py --once --dry-run
    python world-sim/scripts/agent_watch.py --interval 60
    python world-sim/scripts/agent_watch.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORLD_SIM / ".runtime"
SCRATCH = WORLD_SIM / ".scratch" / "agent_watch"

PAIRS = {
    "east": RUNTIME_ROOT / "first-pair",
    "west": RUNTIME_ROOT / "first-pair-west",
}

# (The `starving` signal is retired with the pressure model: nothing
# starves now that the world consumes no food. It fired 0 times in 70
# heartbeats before removal, on a board where two agents were in fact
# locked at zero food by a deadlock nobody had measured - which is what
# scripts/audit_tile_resources.py now guards against.)

# Thresholds are operator-tunable, not agent-visible physics.
STUCK_MIN_HITS = 5          # same refusal, this many times
STUCK_WINDOW = 40           # ...within this many heartbeats
DEAD_HEARTBEATS = 8         # no tick advance for this many minutes

STATE_PATH = SCRATCH / "ledger.json"
ALERT_LOG = SCRATCH / "alerts.log"
STATUS_PATH = SCRATCH / "status.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# (split_ledgers retired with the pressure model - it existed only to
# serve the starving signal.)


# ---------------------------------------------------------------------------
# Scanning (pure; never writes)
# ---------------------------------------------------------------------------


def scan_asks(pair: str, store: Path) -> list[dict]:
    """Unheard agent questions."""
    path = store / "agent_questions.json"
    if not path.is_file():
        return []
    out = []
    for rec in read_json(path).get("data", []):
        if not isinstance(rec, dict) or rec.get("status") != "unheard":
            continue
        out.append({
            "kind": "ask",
            "key": f"{pair}:ask:{rec.get('question_id')}",
            "severity": rec.get("urgency") or "low",
            "pair": pair,
            "agent": rec.get("agent_ref", "?"),
            "heartbeat": rec.get("heartbeat"),
            "title": f"{rec.get('agent_ref', '?')} asks (unanswered)",
            "body": rec.get("question", ""),
            "reply_hint": "python world-sim/scripts/operator_say.py --text \"...\"",
        })
    return out


def scan_stuck(pair: str, store: Path) -> list[dict]:
    """An agent refused the same way, over and over, lately."""
    path = store / "heartbeat.json"
    if not path.is_file():
        return []
    heartbeats = read_json(path).get("data", [])
    if not heartbeats:
        return []
    last_hb = heartbeats[-1].get("heartbeat_number", 0)
    window = [
        h for h in heartbeats
        if last_hb - h.get("heartbeat_number", 0) < STUCK_WINDOW
    ]
    counts: dict[tuple, list] = {}
    for hb in window:
        outcomes = hb.get("action_outcomes") or {}
        actions = hb.get("action_taken") or {}
        for ref, out in outcomes.items():
            if out.get("status") != "rejected":
                continue
            action = actions.get(ref) or {}
            atype = action.get("action_type", "?")
            reason = str(out.get("reason", ""))[:60]
            counts.setdefault((ref, atype, reason), []).append(hb.get("heartbeat_number"))
    out = []
    for (ref, atype, reason), hbs in counts.items():
        if len(hbs) < STUCK_MIN_HITS:
            continue
        out.append({
            "kind": "stuck",
            "key": f"{pair}:stuck:{ref}:{atype}:{reason}",
            "severity": "high" if len(hbs) >= STUCK_MIN_HITS * 2 else "medium",
            "pair": pair,
            "agent": ref,
            "heartbeat": hbs[-1],
            "title": f"{ref} refused {len(hbs)}x: {atype}",
            "body": reason,
            "reply_hint": "inspect before answering; refusals are usually real",
        })
    return out


def scan_first_build(pair: str, store: Path) -> list[dict]:
    """An agent built something. The show moment."""
    path = store / "world_state.json"
    if not path.is_file():
        return []
    data = read_json(path).get("data", {})
    out = []
    for obj_id, obj in (data.get("public_objects") or {}).items():
        if not isinstance(obj, dict):
            continue
        if not obj.get("materials"):
            continue  # pre-build-layer objects carry no materials
        out.append({
            "kind": "first_build",
            "key": f"{pair}:build:{obj_id}",
            "severity": "high",
            "pair": pair,
            "agent": "unknown",
            "heartbeat": obj.get("created_heartbeat"),
            "title": f"{pair} pair built: {obj.get('object_type')}",
            "body": (obj.get("public_description") or "")[:220],
            "reply_hint": f"object_id={obj_id} materials={obj.get('materials')}",
        })
    return out


def scan_dead(pair: str, store: Path, idle_minutes: float = DEAD_HEARTBEATS) -> list[dict]:
    """A store whose clock stopped moving."""
    path = store / "world_state.json"
    if not path.is_file():
        return []
    data = read_json(path).get("data", {})
    stamp = data.get("updated_at_utc")
    tick = data.get("tick")
    if not stamp or tick is None:
        return []
    try:
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(stamp)).total_seconds() / 60.0
    except ValueError:
        return []
    if age < idle_minutes:
        return []
    return [{
        "kind": "dead",
        "key": f"{pair}:dead:{tick}",
        "severity": "high",
        "pair": pair,
        "agent": "-",
        "heartbeat": tick,
        "title": f"{pair} pair clock stopped at tick {tick}",
        "body": f"no heartbeat for {age:.0f} min",
        "reply_hint": "check the chain log; relaunch, do not hand-edit stores",
    }]


def scan_all(pairs: dict | None = None, idle_minutes: float = DEAD_HEARTBEATS) -> list[dict]:
    pairs = pairs or PAIRS
    signals: list[dict] = []
    for pair, store in pairs.items():
        if not Path(store).is_dir():
            continue
        for fn in (scan_asks, scan_stuck, scan_first_build):
            try:
                signals.extend(fn(pair, Path(store)))
            except Exception as exc:
                signals.append({
                    "kind": "watcher_error", "key": f"{pair}:err:{fn.__name__}:{type(exc).__name__}",
                    "severity": "high", "pair": pair, "agent": "-", "heartbeat": None,
                    "title": f"watcher could not scan {fn.__name__}",
                    "body": f"{type(exc).__name__}: {exc}"[:200],
                    "reply_hint": "the watcher is read-only; this is its own bug",
                })
        try:
            signals.extend(scan_dead(pair, Path(store), idle_minutes))
        except Exception:
            pass
    return signals


# ---------------------------------------------------------------------------
# Dedup ledger
# ---------------------------------------------------------------------------


def load_ledger(path: Path | None = None) -> dict:
    # Resolved at call time, not import time: a caller (or a test) that
    # repoints STATE_PATH must actually change where we read.
    path = Path(path) if path is not None else STATE_PATH
    if path.is_file():
        try:
            return read_json(path).get("fired", {})
        except Exception:
            return {}
    return {}


def dedupe(signals: list[dict], fired: dict) -> tuple[list[dict], dict]:
    """Return (new_signals, updated_fired). A key fires once."""
    fresh = []
    updated = dict(fired)
    for sig in signals:
        key = sig["key"]
        if updated.get(key):
            continue
        updated[key] = {
            "fired_at_utc": _utc_now(),
            "kind": sig["kind"],
            "pair": sig["pair"],
        }
        fresh.append(sig)
    return fresh, updated


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def render(sig: dict) -> str:
    lines = [
        f"[{sig['severity'].upper()}] {sig['title']}",
        f"pair={sig['pair']} agent={sig['agent']} hb={sig['heartbeat']}",
    ]
    if sig.get("body"):
        lines.append(sig["body"])
    if sig.get("reply_hint"):
        lines.append(f"-> {sig['reply_hint']}")
    return "\n".join(lines)


def telegram_config(env: dict | None = None) -> tuple[str, str]:
    env = env or os.environ
    return (
        env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        env.get("TELEGRAM_CHAT_ID", "").strip(),
    )


def send_telegram(sig: dict, token: str, chat_id: str, timeout: float = 15.0) -> tuple[bool, str]:
    if not token or not chat_id:
        return False, "telegram not configured"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": f"GENESIS WATCH\n{render(sig)}",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return bool(body.get("ok")), "ok" if body.get("ok") else str(body)[:200]
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"[:200]


def log_alert(sig: dict, path: Path | None = None) -> None:
    path = Path(path) if path is not None else Path(ALERT_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"--- {_utc_now()}\n{render(sig)}\n")


def deliver(signals: list[dict], dry_run: bool = False, env: dict | None = None) -> dict:
    """Fan out alerts: durable log always, Telegram when configured."""
    token, chat_id = telegram_config(env)
    sent, failed, logged = 0, [], 0
    for sig in signals:
        if dry_run:
            print(f"[DRY-RUN] would alert:\n{render(sig)}\n")
            continue
        log_alert(sig, ALERT_LOG)
        logged += 1
        ok, detail = send_telegram(sig, token, chat_id)
        if ok:
            sent += 1
        elif "not configured" not in detail:
            failed.append({"key": sig["key"], "detail": detail})
    status = {
        "updated_at_utc": _utc_now(),
        "alerts_logged": logged,
        "telegram_sent": sent,
        "telegram_failures": failed,
        "telegram_configured": bool(token and chat_id),
    }
    if not dry_run:
        status_path = Path(STATUS_PATH)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8", newline="\n")
    return status


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def run_once(dry_run: bool = False, idle_minutes: float = DEAD_HEARTBEATS) -> dict:
    signals = scan_all(idle_minutes=idle_minutes)
    fresh, fired = dedupe(signals, load_ledger())
    if fresh and not dry_run:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps({"updated_at_utc": _utc_now(), "fired": fired}, indent=2),
            encoding="utf-8", newline="\n")
    return deliver(fresh, dry_run=dry_run)


def run_forever(interval: int, dry_run: bool = False) -> None:
    print(f"AGENT_WATCH=UP interval={interval}s dry_run={dry_run}", flush=True)
    while True:
        try:
            status = run_once(dry_run=dry_run)
            if status["alerts_logged"]:
                print(
                    f"[{status['updated_at_utc']}] alerts={status['alerts_logged']} "
                    f"telegram={status['telegram_sent']}/{status['alerts_logged']}",
                    flush=True)
        except Exception as exc:
            # The watcher must never be the thing that dies silently.
            print(f"AGENT_WATCH_ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(5, interval))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one scan and exit")
    ap.add_argument("--interval", type=int, default=60, help="seconds between scans")
    ap.add_argument("--dry-run", action="store_true",
                    help="print alerts, never write ledger or send")
    ap.add_argument("--idle-minutes", type=float, default=DEAD_HEARTBEATS,
                    help="minutes without a heartbeat before 'dead' fires")
    ap.add_argument("--status", action="store_true", help="print last delivery status")
    ap.add_argument("--reset", action="store_true",
                    help="clear the dedupe ledger (re-alert everything)")
    args = ap.parse_args()

    if args.status:
        print(STATUS_PATH.read_text(encoding="utf-8") if STATUS_PATH.is_file()
              else "no status yet")
        return 0
    if args.reset:
        if STATE_PATH.is_file():
            STATE_PATH.unlink()
            print(f"AGENT_WATCH_RESET {STATE_PATH}")
        return 0
    if args.once:
        status = run_once(dry_run=args.dry_run, idle_minutes=args.idle_minutes)
        print(json.dumps(status, indent=2))
        return 0
    run_forever(args.interval, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
