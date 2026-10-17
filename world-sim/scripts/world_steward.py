"""World steward: keeps the sim running so Sean can watch.

Runs on a Windows Scheduled Task every 15 minutes. Each poll:

  1. Checks both stores for split-brain (count != tick) and
     forward-repairs if needed (the safe direction from the
     ledger-before-tick fix).
  2. Checks whether a chain process is running. If not, restarts from
     the next heartbeat after the store's last clean record.
  3. Every 4th poll (once an hour), sends ONE Telegram digest:
     both pairs' positions, what they did, any repairs.

The steward never makes design decisions, never answers agent questions,
never changes physics. It does exactly what Sean has been saying "yes"
to every time he checks in: repair, restart, resume, report.

Usage:
    python world_steward.py --once          # one poll, print to stdout
    python world_steward.py --loop 900 --max-polls 4   # bounded daemon

Every invocation takes a single-instance lock: a second steward that
finds a fresh lock held by a live pid exits immediately. Daemon mode
must be bounded with --max-polls — the Oct 19 incident (80 immortal
stewards from an unbounded --loop under a 15-min schedule) is why this
file grew a lock. The hourly digest cadence lives in a fire counter,
so --once under a 15-min schedule still digests every 4th fire.
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
REPO_ROOT = WORLD_SIM.parent
STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
CHAIN = WORLD_SIM / "scripts" / "lockstep_chain.py"
LOCK_DIR = WORLD_SIM / ".scratch" / "lockstep"
WINDOW_SIZE = 100
STEWARD_LOCK = LOCK_DIR / "steward.lock"
FIRE_COUNTER = LOCK_DIR / "steward_fires.json"

# Windows process creation flags for silent spawning
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# single-instance lock
# --------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_steward_lock() -> dict | None:
    data = _read_json(STEWARD_LOCK)
    if not isinstance(data, dict) or not isinstance(data.get("pid"), int):
        return None
    return data


def acquire_steward_lock(max_age_s: float) -> bool:
    """Take the steward lock. False = a live steward already holds it."""
    now = time.time()
    existing = _read_steward_lock()
    if existing:
        age = now - float(existing.get("ts", 0))
        if _pid_alive(existing["pid"]) and age <= max_age_s:
            return False
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    STEWARD_LOCK.write_text(
        json.dumps({"pid": os.getpid(), "ts": now}),
        encoding="utf-8", newline="\n")
    return True


def refresh_steward_lock() -> None:
    """Heartbeat the lock so a hung steward's lock still expires."""
    if STEWARD_LOCK.exists():
        STEWARD_LOCK.write_text(
            json.dumps({"pid": os.getpid(), "ts": time.time()}),
            encoding="utf-8", newline="\n")


def release_steward_lock() -> None:
    try:
        data = _read_steward_lock()
        if data and data.get("pid") == os.getpid():
            STEWARD_LOCK.unlink(missing_ok=True)
    except OSError:
        pass


def _bump_fire_counter() -> int:
    """How many times has the steward fired? Drives the hourly digest
    cadence when running --once under the scheduled task."""
    data = _read_json(FIRE_COUNTER) or {}
    n = int(data.get("count", 0)) + 1
    FIRE_COUNTER.parent.mkdir(parents=True, exist_ok=True)
    FIRE_COUNTER.write_text(json.dumps({"count": n}),
                            encoding="utf-8", newline="\n")
    return n


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count_heartbeat_records(path: Path) -> int:
    """Stream-count 'heartbeat_number' occurrences. Same technique as the
    chain's fix — never load the full file."""
    count = 0
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                count += chunk.count(b'"heartbeat_number"')
    except OSError:
        return 0
    return count


def _read_tick(store: Path) -> int:
    ws = _read_json(store / "world_state.json")
    data = ws.get("data", ws)
    tick = data.get("tick", 0)
    return tick if isinstance(tick, int) else 0


def _occupancy(store: Path) -> dict:
    ws = _read_json(store / "world_state.json")
    return ws.get("data", ws).get("tile_occupancy", {})


def forward_repair(pair: str) -> str | None:
    """Roll the tick forward to match the ledger if it's behind."""
    store = STORES[pair]
    count = _count_heartbeat_records(store / "heartbeat.json")
    tick = _read_tick(store)
    if count > tick:
        ws = _read_json(store / "world_state.json")
        data = ws.get("data", ws)
        data["tick"] = count
        if "tick" in ws:
            ws["tick"] = count
        tmp = store / "world_state.json.tmp"
        tmp.write_text(json.dumps(ws, indent=1), encoding="utf-8", newline="\n")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(store / "world_state.json")
        return f"{pair}: forward repair {tick} -> {count}"
    return None


def chain_alive() -> dict[str, bool]:
    """Check for lockstep_chain.py processes."""
    alive = {"east": False, "west": False}
    try:
        import psutil
        for proc in psutil.process_iter(["cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
            except Exception:
                continue
            if "lockstep_chain.py" not in cmd:
                continue
            for pair in alive:
                if f" {pair}" in cmd or f'"{pair}"' in cmd:
                    alive[pair] = True
    except ImportError:
        # psutil unavailable; check lock files and pids
        for pair in alive:
            lock = LOCK_DIR / f"chain_{pair}.lock"
            if lock.is_file():
                try:
                    pid = int(lock.read_text(encoding="utf-8").strip())
                    os.kill(pid, 0)
                    alive[pair] = True
                except (OSError, ValueError):
                    pass
    return alive


def start_chain(pair: str, start: int, end: int) -> int | None:
    """Start a chain window. Returns the pid or None."""
    log = LOCK_DIR / f"chain_{pair}_{start}_{end}.log"
    err = LOCK_DIR / f"chain_{pair}_{start}_{end}.err"
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        proc = subprocess.Popen(
            [sys.executable, str(CHAIN), str(start), str(end), pair,
             "--no-snapshot"],
            cwd=str(REPO_ROOT),
            stdout=open(log, "w", encoding="utf-8", newline="\n"),
            stderr=open(err, "w", encoding="utf-8", newline="\n"),
            creationflags=flags,
        )
        return proc.pid
    except Exception:
        return None


def clear_lock(pair: str) -> None:
    lock = LOCK_DIR / f"chain_{pair}.lock"
    lock.unlink(missing_ok=True)


def ensure_running(pair: str) -> list[str]:
    """Repair, restart, or start a chain. Returns actions taken."""
    actions = []
    alive = chain_alive()
    if alive.get(pair):
        return actions  # running, nothing to do

    # .scratch can vanish (cleanup tools love gitignored dirs); without
    # it start_chain cannot open logs and every restart silently fails
    LOCK_DIR.mkdir(parents=True, exist_ok=True)

    # Not running: repair the store if needed
    repair = forward_repair(pair)
    if repair:
        actions.append(repair)
    clear_lock(pair)

    # Start from the next heartbeat
    store = STORES[pair]
    count = _count_heartbeat_records(store / "heartbeat.json")
    tick = _read_tick(store)
    current = max(count, tick)
    start = current + 1
    end = start + WINDOW_SIZE - 1
    pid = start_chain(pair, start, end)
    if pid:
        actions.append(f"{pair}: restarted HB{start}-{end} (pid {pid})")
    else:
        actions.append(f"{pair}: FAILED to restart")
    return actions


def action_summary(pair: str, since_hb: int) -> dict:
    """What did both agents do since the last check?"""
    store = STORES[pair]
    rows = _read_json(store / "heartbeat.json").get("data", [])
    # Use the streaming count for the total; only read recent rows
    # from the raw JSON for the summary (bounded to last 100)
    try:
        raw = (store / "heartbeat.json").read_text(encoding="utf-8")
        all_rows = json.loads(raw).get("data", [])
        recent = [r for r in all_rows if isinstance(r, dict)
                  and (r.get("heartbeat_number") or 0) >= since_hb]
    except Exception:
        recent = []

    moves = {}
    msgs = 0
    builds = 0
    uses = 0
    for r in recent:
        for who, a in (r.get("action_taken") or {}).items():
            if not isinstance(a, dict):
                continue
            at = a.get("action_type", "")
            name = who.split("_")[1] if "_" in who else who
            if at == "move":
                moves[name] = moves.get(name, 0) + 1
            elif at == "leave_public_message":
                msgs += 1
            elif at in ("build", "create_public_object"):
                builds += 1
            elif at == "use_object":
                uses += 1

    occ = _occupancy(store)
    return {
        "positions": occ,
        "moves": moves,
        "messages": msgs,
        "builds": builds,
        "use_object": uses,
        "tick": _read_tick(store),
    }


def build_narrative_summary(pair: str, since_hb: int) -> dict:
    """What happened, in words a person hears on TTS.

    No coordinates, no heartbeat numbers, no move counts. Just: who
    did what, what they said, and whether they have a question.
    """
    store = STORES[pair]
    try:
        raw = (store / "heartbeat.json").read_text(encoding="utf-8")
        all_rows = json.loads(raw).get("data", [])
        recent = [r for r in all_rows if isinstance(r, dict)
                  and (r.get("heartbeat_number") or 0) >= since_hb]
    except Exception:
        recent = []

    # What did each agent DO (named actions, not counts)
    did: dict[str, list[str]] = {}
    quotes: list[str] = []
    question = None
    for r in recent:
        for who, a in (r.get("action_taken") or {}).items():
            if not isinstance(a, dict):
                continue
            name = who.split("_")[1] if "_" in who else who
            at = a.get("action_type", "")
            if at == "move":
                did.setdefault(name, []).append("explored")
            elif at == "gather":
                kind = a.get("resource_kind", "resources")
                did.setdefault(name, []).append(f"gathered {kind}")
            elif at == "build":
                ot = a.get("object_type", "something")
                did.setdefault(name, []).append(f"built a {ot}")
            elif at == "leave_public_message":
                text = str(a.get("message", ""))[:140]
                if text:
                    quotes.append(f"{name} said: {text}")
                did.setdefault(name, []).append("sent a message")
            elif at == "ask_human":
                q = str(a.get("question", ""))[:160]
                if q:
                    question = f"{name} is asking: {q}"
            elif at == "use_object":
                op = a.get("operation", "")
                target = a.get("target_object_id", "")
                did.setdefault(name, []).append(f"used an object ({op})")
            elif at == "revise_charter":
                did.setdefault(name, []).append("revised their charter")

    # Build the summary sentence
    parts = []
    for name, actions in did.items():
        # Deduplicate and limit
        unique = list(dict.fromkeys(actions))[:3]
        parts.append(f"{name} {' and '.join(unique)}")
    summary = "; ".join(parts) if parts else "quiet"

    return {
        "summary": summary,
        "quote": quotes[-1] if quotes else None,
        "question": question,
    }


def build_digest(east: dict, west: dict) -> str:
    """One paragraph, TTS-friendly: what they did, what they said,
    what they need. No coordinates, no numbers, no telemetry."""
    parts = []
    for pair_name, data in (("East", east), ("West", west)):
        s = data.get("summary", "quiet")
        if s and s != "quiet":
            sentence = f"{pair_name}: {s}"
            q = data.get("quote")
            if q:
                sentence += f". {q}"
            parts.append(sentence)
        else:
            parts.append(f"{pair_name}: quiet")
        ask = data.get("question")
        if ask:
            parts.append(f"QUESTION: {ask}")
    return ". ".join(parts) + "."


def send_telegram(text: str) -> bool:
    """Best-effort Telegram via the existing agent_watch path."""
    sys.path.insert(0, str(WORLD_SIM / "scripts"))
    try:
        from agent_watch import send_telegram
        import winreg
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                    token = str(winreg.QueryValueEx(k, "TELEGRAM_BOT_TOKEN")[0])
                    chat = str(winreg.QueryValueEx(k, "TELEGRAM_CHAT_ID")[0])
            except Exception:
                return False
        if not token or not chat:
            return False
        sig = {"severity": "info", "title": "", "pair": "-", "agent": "-",
               "heartbeat": "-", "body": text}
        ok, _ = send_telegram(sig, token, chat)
        return bool(ok)
    except Exception:
        return False


def poll_once(digest: bool = False) -> dict:
    """One steward poll: repair, restart, optionally digest."""
    all_actions = []
    for pair in ("east", "west"):
        all_actions.extend(ensure_running(pair))

    result = {"at_utc": _utc_now(), "actions": all_actions}

    if digest:
        east_data = build_narrative_summary("east", _read_tick(STORES["east"]) - 60)
        west_data = build_narrative_summary("west", _read_tick(STORES["west"]) - 60)
        msg = build_digest(east_data, west_data)
        if all_actions:
            msg += f" Steward note: {'; '.join(all_actions)}."
        sent = send_telegram(msg)
        result["digest_sent"] = sent
        result["digest"] = msg

    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", type=int, default=0,
                    help="poll interval in seconds (0 = run once)")
    ap.add_argument("--max-polls", type=int, default=0,
                    help="daemon mode: exit after N polls (0 = unlimited; "
                         "unbounded daemons caused the Oct 19 pileup)")
    ap.add_argument("--digest", action="store_true",
                    help="force the digest even if the fire counter "
                         "isn't at the hourly mark")
    args = ap.parse_args(argv)

    lock_age = max(args.loop * 2, 120) if args.loop else 300
    if not acquire_steward_lock(lock_age):
        print("STEWARD=ALREADY-RUNNING", flush=True)
        return 0

    try:
        if args.once or args.loop == 0:
            fire = _bump_fire_counter()
            digest = args.digest or (fire % 4 == 0)
            out = poll_once(digest=digest)
            print(json.dumps(out, indent=1))
            return 0

        # Daemon mode — bounded by --max-polls, heartbeat every poll
        poll_count = 0
        print(f"STEWARD=UP interval={args.loop}s "
              f"max_polls={args.max_polls or 'unlimited'}", flush=True)
        while True:
            poll_count += 1
            refresh_steward_lock()
            digest = (poll_count % 4 == 0)
            try:
                out = poll_once(digest=digest)
                stamp = out["at_utc"][:19]
                acts = "; ".join(out["actions"]) if out["actions"] else "clean"
                print(f"[{stamp}] poll {poll_count}: {acts}", flush=True)
                if out.get("digest_sent"):
                    print(f"[{stamp}] digest sent", flush=True)
            except Exception as exc:
                print(f"STEWARD_ERROR {type(exc).__name__}: {exc}", flush=True)
            if args.max_polls > 0 and poll_count >= args.max_polls:
                break
            time.sleep(args.loop)
        return 0
    finally:
        release_steward_lock()


if __name__ == "__main__":
    sys.exit(main())
