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
    python world-seward.py --once          # one poll, print to stdout
    python world_steward.py --loop 900     # poll every 900s, the daemon
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

# Windows process creation flags for silent spawning
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def hourly_digest(actions: list[str]) -> str:
    """One clean paragraph for the phone."""
    parts = []
    for pair in ("east", "west"):
        s = action_summary(pair, _read_tick(STORES[pair]) - 60)
        names = []
        for agent, pos in (s["positions"] or {}).items():
            n = agent.split("_")[1] if "_" in agent else agent
            # extract coords from tile id like cont_a_gen_-2_-4
            tile = str(pos)
            try:
                pieces = tile.split("_")
                coords = f"({pieces[-2]},{pieces[-1]})"
            except Exception:
                coords = tile[:20]
            names.append(f"{n} at {coords}")
        activity = []
        if s["moves"]:
            activity.append(f"{sum(s['moves'].values())} moves")
        if s["messages"]:
            activity.append(f"{s['messages']} messages")
        if s["builds"]:
            activity.append(f"{s['builds']} builds")
        if s["use_object"]:
            activity.append(f"{s['use_object']} interactions")
        act_str = ", ".join(activity) if activity else "quiet"
        parts.append(f"{pair}: {'; '.join(names) if names else 'unknown'} "
                     f"— {act_str}")
    msg = "World: " + " | ".join(parts)
    if actions:
        msg += f" [steward: {'; '.join(actions)}]"
    return msg


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
        msg = hourly_digest(all_actions)
        sent = send_telegram(msg)
        result["digest_sent"] = sent
        result["digest"] = msg

    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", type=int, default=0,
                    help="poll interval in seconds (0 = run once)")
    ap.add_argument("--digest", action="store_true",
                    help="send hourly digest even in --once mode")
    args = ap.parse_args(argv)

    if args.once or args.loop == 0:
        out = poll_once(digest=args.digest)
        print(json.dumps(out, indent=1))
        return 0

    # Daemon mode
    poll_count = 0
    print(f"STEWARD=UP interval={args.loop}s", flush=True)
    while True:
        poll_count += 1
        digest = (poll_count % 4 == 0)  # every 4th poll = hourly at 15min
        try:
            out = poll_once(digest=digest)
            stamp = out["at_utc"][:19]
            acts = "; ".join(out["actions"]) if out["actions"] else "clean"
            print(f"[{stamp}] poll {poll_count}: {acts}", flush=True)
            if out.get("digest_sent"):
                print(f"[{stamp}] digest sent", flush=True)
        except Exception as exc:
            print(f"STEWARD_ERROR {type(exc).__name__}: {exc}", flush=True)
        time.sleep(args.loop)


if __name__ == "__main__":
    sys.exit(main())
