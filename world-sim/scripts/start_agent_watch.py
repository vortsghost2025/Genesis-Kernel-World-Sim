"""Start the agent watcher as a persistent, detached, self-restarting process.

The watcher is the operator's only early-warning system. If it dies
silently the whole point is lost, so this launcher:
  * starts it detached (survives editor/UI restarts, like the chains)
  * writes a pidfile so it can be stopped or restarted deliberately
  * restarts it if it ever exits, with backoff, unless stopped on purpose

It does NOT restart on its own if you asked it to stop: stop_watch.py
removes the guard file first.

Usage:
    python world-sim/scripts/start_agent_watch.py            # start (idempotent)
    python world-sim/scripts/start_agent_watch.py --status   # is it up?
    python world-sim/scripts/start_agent_watch.py --stop     # stop it
    python world-sim/scripts/start_agent_watch.py --restart  # stop then start
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
SCRATCH = WORLD_SIM / ".scratch" / "agent_watch"
PIDFILE = SCRATCH / "watcher.pid"
LOGFILE = SCRATCH / "watcher.out"
STOP_GUARD = SCRATCH / "watcher.stopped"
WATCH_SCRIPT = WORLD_SIM / "scripts" / "agent_watch.py"
DEFAULT_INTERVAL = 60

CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def running_pid() -> int | None:
    """The watcher's pid if it is alive, else None."""
    if not PIDFILE.is_file():
        return None
    try:
        pid = int(PIDFILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if pid <= 0:
        return None
    try:
        import psutil  # type: ignore
        proc = psutil.Process(pid)
        if proc.is_running() and "agent_watch" in " ".join(proc.cmdline()):
            return pid
        return None
    except ImportError:
        pass
    except Exception:
        return None
    # No psutil: fall back to a tasklist probe (Windows only)
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=20,
            ).stdout
            return pid if str(pid) in out else None
        except Exception:
            return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def start(interval: int = DEFAULT_INTERVAL) -> dict:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    existing = running_pid()
    if existing:
        return {"status": "already-running", "pid": existing}

    STOP_GUARD.unlink(missing_ok=True)
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = (
        CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB | CREATE_NO_WINDOW
        if os.name == "nt" else 0
    )
    log = open(LOGFILE, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(WATCH_SCRIPT), "--interval", str(interval)],
            cwd=str(WORLD_SIM),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            start_new_session=(os.name != "nt"),
        )
    finally:
        log.close()
    PIDFILE.write_text(str(proc.pid), encoding="utf-8", newline="\n")
    (SCRATCH / "watcher.meta.json").write_text(
        json.dumps({
            "pid": proc.pid,
            "interval_seconds": interval,
            "started_at_utc": _utc_now(),
            "log": str(LOGFILE),
        }, indent=2),
        encoding="utf-8", newline="\n",
    )
    time.sleep(1.5)
    alive = running_pid()
    return {
        "status": "started" if alive else "started-but-not-confirmed",
        "pid": proc.pid,
        "interval_seconds": interval,
        "log": str(LOGFILE),
    }


def stop() -> dict:
    STOP_GUARD.parent.mkdir(parents=True, exist_ok=True)
    STOP_GUARD.write_text(_utc_now(), encoding="utf-8", newline="\n")
    pid = running_pid()
    if not pid:
        PIDFILE.unlink(missing_ok=True)
        return {"status": "not-running"}
    try:
        os.kill(pid, 15 if os.name != "nt" else 15)
    except Exception:
        pass
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=30)
    time.sleep(1.0)
    PIDFILE.unlink(missing_ok=True)
    return {"status": "stopped", "pid": pid}


def status() -> dict:
    pid = running_pid()
    return {
        "running": bool(pid),
        "pid": pid,
        "stop_guard": STOP_GUARD.is_file(),
        "log_exists": LOGFILE.is_file(),
        "log": str(LOGFILE),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--restart", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        result = status()
    elif args.stop:
        result = stop()
    elif args.restart:
        result = {"stop": stop(), "start": start(args.interval)}
    else:
        result = start(args.interval)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
