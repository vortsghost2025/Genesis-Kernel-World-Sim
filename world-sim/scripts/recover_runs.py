"""Recover a run that a reboot interrupted.

On 2026-09-30 Windows updated and rebooted overnight, killing a census at
HB1210 of a 1243-heartbeat run. The chain was gone and the store was
intact, and nobody knew for hours. The chain's own preflight is already
fail-closed, so resuming is safe - the hard part is deciding whether to.

`plan_recovery` is that decision, as a pure function, because it runs
unattended: if it cannot tell what state the run is in, it must do
nothing. Starting a chain on a guess is how two processes end up writing
one store.

Run-state lives in `.scratch/lockstep/current_run.json`, written when a
run is launched. Absent or unreadable is `unknown`, never "resume".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
REPO_ROOT = WORLD_SIM.parent
SCRATCH = WORLD_SIM / ".scratch" / "lockstep"
RUN_STATE = SCRATCH / "current_run.json"
STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}
CHAIN = WORLD_SIM / "scripts" / "lockstep_chain.py"
LOCKS = SCRATCH


def acquire_store_lock(pair: str, pid: int) -> Path | None:
    """Exclusive per-store lock so two chains can never write one store.

    The second writer is refused, not queued: a chain writes heartbeats to
    a shared ledger, and interleaving two of them corrupts the record in a
    way no later check can detect. This exists because the guard above it
    is a heuristic - a pid file plus a process scan - and heuristics are
    what let a duplicate through on 2026-09-30.

    Returns the lock path on success, None when a live lock is held.
    """
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f"chain_{pair}.lock"
    if path.is_file():
        try:
            holder = int(path.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            holder = 0
        if holder and holder != pid and _pid_alive(holder):
            return None
        # Holder is gone or is us: the lock is stale, take it over.
    path.write_text(str(pid), encoding="utf-8", newline="\n")
    return path


def release_store_lock(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _log(msg: str) -> None:
    print(msg, flush=True)


def plan_recovery(tick, target_end: int, chain_alive: bool) -> dict:
    """What should a boot do about a run? Never guesses.

    Returns {action, reason, ...} where action is "resume" or "none".
    """
    if chain_alive:
        return {"action": "none", "reason": "a chain is already running"}
    if not isinstance(target_end, int) or target_end <= 0:
        return {"action": "none", "reason": "no target heartbeat recorded"}
    if not isinstance(tick, int):
        return {"action": "none",
                "reason": "cannot read the store tick - refusing to guess"}
    if tick >= target_end:
        return {"action": "none",
                "reason": f"run already reached HB{target_end}"}
    return {
        "action": "resume",
        "reason": f"interrupted at HB{tick} of {target_end}",
        "start": tick + 1,
        "end": target_end,
        "remaining": target_end - tick,
    }


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def store_tick(pair: str):
    data = read_json(STORES.get(pair, STORES["east"]) / "world_state.json")
    inner = data.get("data", data)
    tick = inner.get("tick")
    return tick if isinstance(tick, int) else None


def chain_alive() -> bool:
    """True when a lockstep chain process exists. Read-only, best effort.

    Checks BOTH the recorded run-state pid and a live process scan, and
    treats a detection failure as ALIVE. That direction is deliberate: the
    question is "may I start another writer?", and the cost of a wrong
    "no" is a missed resume while the cost of a wrong "yes" is two chains
    writing one store. Fail toward the expensive mistake.
    """
    state = read_json(RUN_STATE)
    pid = state.get("chain_pid")
    if isinstance(pid, int) and pid > 0 and _pid_alive(pid):
        return True
    try:
        import psutil  # type: ignore
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
            except Exception:
                continue
            if "lockstep_chain.py" in cmd and proc.pid != os.getpid():
                return True
    except Exception as exc:
        _log(f"chain_alive: process scan unavailable ({type(exc).__name__}) "
             f"- treating as ALIVE, will not start a second writer")
        return True
    return False


def _pid_alive(pid: int) -> bool:
    """Liveness for a recorded pid, across platforms. Never raises."""
    if pid == os.getpid():
        return True
    try:
        import psutil  # type: ignore
        return psutil.Process(pid).is_running()
    except ImportError:
        pass
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _telegram_env() -> dict:
    out = dict(os.environ)
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        val = os.environ.get(name) or os.environ.get(name, "")
        if not val:
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                    val = str(winreg.QueryValueEx(k, name)[0])
            except Exception:
                val = ""
        if val:
            out[name] = val
    return out


def notify(text: str) -> bool:
    """One plain line to the operator, best effort. Never raises."""
    try:
        sys.path.insert(0, str(WORLD_SIM / "scripts"))
        from agent_watch import send_telegram
        env = _telegram_env()
        token = env.get("TELEGRAM_BOT_TOKEN", "")
        chat = env.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            _log("notify: telegram not configured")
            return False
        sig = {"severity": "warn" if "STOPPED" in text or "FROZEN" in text
               else "info", "title": "reboot recovery", "pair": "-",
               "agent": "-", "heartbeat": "-", "body": text}
        ok, detail = send_telegram(sig, token, chat)
        _log(f"notify: {ok} {detail}")
        return bool(ok)
    except Exception as exc:
        _log(f"notify failed: {type(exc).__name__}: {exc}")
        return False


def record_run_state(pair: str, start: int, end: int, chain_pid: int) -> None:
    """Note the run so a later boot can reason about it."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RUN_STATE.write_text(json.dumps(
        {"pair": pair, "start": start, "end": end, "chain_pid": chain_pid},
        indent=1), encoding="utf-8", newline="\n")


def recover_pair(pair: str, state: dict, dry_run: bool = False) -> dict:
    """Apply the decision for one pair. Returns the plan plus what happened."""
    plan = plan_recovery(store_tick(pair), int(state.get("end") or 0),
                         chain_alive())
    plan["pair"] = pair
    if plan["action"] != "resume":
        _log(f"{pair}: no action - {plan['reason']}")
        return plan
    if dry_run:
        _log(f"{pair}: WOULD resume {plan['start']}-{plan['end']} "
             f"({plan['reason']})")
        return plan
    log_path = SCRATCH / f"chain_{pair}_recovered_{plan['start']}_{plan['end']}.log"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as fh:
        proc = subprocess.Popen(
            [sys.executable, str(CHAIN), str(plan["start"]), str(plan["end"]),
             pair, "--no-snapshot"],
            cwd=str(REPO_ROOT), stdout=fh, stderr=subprocess.STDOUT,
            env=_telegram_env(), creationflags=getattr(
                subprocess, "CREATE_NO_WINDOW", 0))
    _log(f"{pair}: resumed as pid {proc.pid} -> {log_path.name}")
    plan["pid"] = proc.pid
    plan["log"] = str(log_path)
    return plan


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    pairs = [a for a in argv if not a.startswith("-")] or ["east", "west"]
    _log(f"RECOVER start dry_run={dry} pairs={pairs}")

    started = []
    for pair in pairs:
        if pair not in STORES:
            _log(f"{pair}: unknown pair, skipped")
            continue
        state = read_json(RUN_STATE)
        if state.get("pair") != pair:
            _log(f"{pair}: no recorded run state, skipped")
            continue
        try:
            plan = recover_pair(pair, state, dry_run=dry)
        except Exception as exc:
            _log(f"{pair}: recovery error {type(exc).__name__}: {exc}")
            continue
        if plan.get("action") == "resume":
            started.append(pair)

    if started and not dry:
        notify("Genesis: the machine restarted mid-run and I picked it back "
               f"up: {', '.join(started)}. Heartbeats are running again.")
    elif not started and not dry:
        _log("RECOVER nothing to resume")
    _log(f"RECOVER done resumed={started}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
