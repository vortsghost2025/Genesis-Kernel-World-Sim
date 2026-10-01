"""Lockstep chain: advances BOTH pairs on the same heartbeat clock.

Each tick n launches the east pair's HB(n) and the west pair's HB(n) as
independent detached runners (separate stores, no shared state), waits for
both, and verifies both stores at n. This is the merged-clock operating tool
of the two-civilization era.

Resilience model (mirrors the west catch-up chain):
- Transient failures (empty_response, launch hiccups) retried per pair up to
  MAX_RETRIES with a delay.
- Store mismatches and invariant failures hard-stop immediately (fail-closed).
- Every SNAPSHOT_EVERY ticks the slim viewer snapshot is exported and pushed
  to the public show; a push failure is logged and never fatal.

Usage:
    python world-sim/scripts/lockstep_chain.py 453 500
    python world-sim/scripts/lockstep_chain.py 944 1043 east

The optional third argument restricts the run to a pair subset, so a
single-pair census can run on its own clock without the merged-clock hard
stop that a lagging comparison store would otherwise cause.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# CREATE_NO_WINDOW: the chain spawns a detached runner every heartbeat on
# Windows. Without it each spawn flashes a console on the operator's screen,
# every few tens of seconds, for the whole run. A background process whose
# existence reaches the foreground is not background.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

WORLD_SIM = Path(__file__).resolve().parent.parent
REPO_ROOT = WORLD_SIM.parent
RUNNER = WORLD_SIM / "scripts" / "launch_canonical_heartbeat_detached.py"
EXPORTER = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"
EVIDENCE_DIR = WORLD_SIM / ".scratch" / "lockstep"
SNAPSHOT_OUT = EVIDENCE_DIR / "viewer_data.js"
# Sim-owned credential vault (decoupled from kernel-lane 2026-09-26).
# The runner's built-in default still points at S:\kernel-lane\.env; the
# chain passes this explicitly so every heartbeat uses sim-owned keys.
VAULT = WORLD_SIM / ".env"

PAIRS_ALL = ("east", "west")
# Overridable so a single-pair arc can run on its own clock. The east pair is
# frequently ahead of west (west is a deliberately dormant comparison store),
# and a merged clock hard-stops on that mismatch - which is correct for a
# lockstep run and useless for a census that only measures one pair.
PAIRS = PAIRS_ALL
STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}

MAX_RETRIES = 3
RETRY_DELAY_S = 45
# Per-heartbeat budget for the detached runner. Generous - a free-tier model
# can be slow - but finite, so a dead runner cannot spin the chain forever.
STATUS_TIMEOUT_S = 600
SNAPSHOT_EVERY = 10
# The snapshot push is an EXTERNAL network write: it exports the slim world
# state and scp/ssh's it onto a public viewer. It is not a local read or a
# sim write - it publishes. It is non-fatal by design and unrelated to any
# census row, so a single-pair measurement arc should run with it off rather
# than quietly pushing state to a public URL 10 times.
SNAPSHOTS_ENABLED = True
# IP not hostname: the hostname is not yet in known_hosts and subprocess ssh
# cannot answer the interactive host-key prompt. Equivalent target.
PUBLIC_VPS = os.environ.get("GENESIS_PUBLIC_VPS", "root@187.77.3.56")


def store_state(pair: str) -> tuple[int, int, dict]:
    hb = json.loads((STORES[pair] / "heartbeat.json").read_text(encoding="utf-8"))
    data = hb.get("data", hb)
    ws = json.loads((STORES[pair] / "world_state.json").read_text(encoding="utf-8"))
    wdata = ws.get("data", ws)
    return len(data), wdata.get("tick", 0), wdata.get("tile_occupancy", {})


def status_path(pair: str, hb: int) -> Path:
    return EVIDENCE_DIR / f"lockstep_{pair}_hb{hb}_status.json"


def attempt_heartbeat(pair: str, hb: int) -> bool:
    """Launch one detached runner. True when the launch itself succeeded."""
    evidence = EVIDENCE_DIR / f"lockstep_{pair}_hb{hb}_evidence.json"
    log = EVIDENCE_DIR / f"lockstep_{pair}_hb{hb}_run.log"
    status = status_path(pair, hb)
    if status.exists():
        status.unlink()

    proc = subprocess.run(
        [
            sys.executable, str(RUNNER),
            "--expect-heartbeat", str(hb),
            "--pair-id", pair,
            "--vault", str(VAULT),
            "--evidence", str(evidence),
            "--log", str(log),
            "--status", str(status),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=CREATE_NO_WINDOW,
    )
    if proc.returncode != 0:
        print(f"HB{hb} {pair}: LAUNCH FAIL — {proc.stderr[:200]}", flush=True)
        return False
    return True


def wait_for_status(pair: str, hb: int, timeout_s: int = STATUS_TIMEOUT_S,
                    poll_s: int = 5) -> bool:
    """Block until the detached runner reports exported or failed.

    Fails closed on timeout. The original version polled forever, so a runner
    that died before writing a terminal status left the chain spinning
    indefinitely - it could not tell "still working" from "dead". That is the
    worst possible behaviour for an unattended run: it looks alive, reports
    nothing, and never stops. A timeout turns that into a retryable failure
    and, eventually, a hard stop.
    """
    status = status_path(pair, hb)
    deadline = time.monotonic() + timeout_s
    while True:
        if status.is_file():
            try:
                s = json.loads(status.read_text(encoding="utf-8"))
                st = s.get("status", "")
                if st == "evidence-exported":
                    return True
                if st == "failed":
                    print(f"HB{hb} {pair}: runner FAILED — {s.get('detail', '?')}",
                          flush=True)
                    return False
            except Exception:
                pass
        if time.monotonic() > deadline:
            seen = None
            if status.is_file():
                try:
                    seen = json.loads(status.read_text(encoding="utf-8")).get("status")
                except Exception:
                    seen = "<unreadable>"
            print(f"HB{hb} {pair}: TIMEOUT after {timeout_s}s — last status "
                  f"{seen!r} (runner dead, or slower than the budget)", flush=True)
            return False
        time.sleep(poll_s)


def push_snapshot() -> None:
    """Export the slim snapshot and push it to the public show. Non-fatal."""
    try:
        r = subprocess.run(
            [sys.executable, str(EXPORTER), "--slim", "--out", str(SNAPSHOT_OUT)],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300,
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode != 0:
            print(f"SNAPSHOT: export failed — {r.stderr[:150]}", flush=True)
            return
        scp = subprocess.run(
            ["scp", str(SNAPSHOT_OUT), f"{PUBLIC_VPS}:/tmp/viewer_data.js"],
            capture_output=True, text=True, timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
        if scp.returncode != 0:
            print(f"SNAPSHOT: scp failed — {scp.stderr[:150]}", flush=True)
            return
        ssh = subprocess.run(
            ["ssh", PUBLIC_VPS,
             "docker cp /tmp/viewer_data.js genesis-viewer:/app/web/viewer_data.js"],
            capture_output=True, text=True, timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
        if ssh.returncode == 0:
            print("SNAPSHOT: pushed to public show", flush=True)
        else:
            print(f"SNAPSHOT: docker cp failed — {ssh.stderr[:150]}", flush=True)
    except Exception as exc:
        print(f"SNAPSHOT: push error — {type(exc).__name__}: {exc}", flush=True)
    print_inbox()


def print_inbox() -> None:
    """Operator inbox: surface what the agents are asking us. Non-fatal."""
    try:
        r = subprocess.run(
            [sys.executable, str(WORLD_SIM / "scripts" / "operator_inbox.py")],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            print("--- OPERATOR INBOX " + "-" * 40, flush=True)
            print(r.stdout.rstrip(), flush=True)
            print("-" * 58, flush=True)
        else:
            print(f"INBOX: scan failed — {r.stderr[:150]}", flush=True)
    except Exception as exc:
        print(f"INBOX: scan error — {type(exc).__name__}: {exc}", flush=True)


def run_tick(hb: int) -> bool:
    """Advance both pairs to heartbeat hb. True when both stores are at hb."""
    need = []
    for pair in PAIRS:
        count, tick, _ = store_state(pair)
        if count >= hb:
            print(f"HB{hb} {pair}: already done", flush=True)
        elif count != hb - 1 or tick != hb - 1:
            print(f"HB{hb} {pair}: MISMATCH count={count} tick={tick} expected {hb-1}", flush=True)
            print("HARD STOP", flush=True)
            return False
        else:
            need.append(pair)
    if not need:
        return True

    done = {p: False for p in need}
    for attempt in range(1, MAX_RETRIES + 1):
        # launch phase: (re)launch every pair not yet at hb
        launched: dict[str, bool] = {}
        for pair in need:
            if done[pair]:
                continue
            count, tick, _ = store_state(pair)
            if count == hb and tick == hb:
                done[pair] = True
                continue
            if count != hb - 1 or tick != hb - 1:
                print(f"HB{hb} {pair}: INVARIANT FAIL — count={count} tick={tick}", flush=True)
                print("HARD STOP", flush=True)
                return False
            launched[pair] = attempt_heartbeat(pair, hb)
        if all(done.values()):
            break

        # wait phase: runners execute concurrently; harvest in order
        for pair, launch_ok in launched.items():
            if launch_ok:
                wait_for_status(pair, hb)

        # check phase
        progressed = False
        for pair in need:
            if done[pair]:
                continue
            count, tick, _ = store_state(pair)
            if count == hb and tick == hb:
                done[pair] = True
                progressed = True
            elif count != hb - 1 or tick != hb - 1:
                print(f"HB{hb} {pair}: INVARIANT FAIL — count={count} tick={tick}", flush=True)
                print("HARD STOP", flush=True)
                return False
        if all(done.values()):
            break
        if attempt < MAX_RETRIES:
            pending = [p for p in need if not done[p]]
            print(f"HB{hb} {pending}: attempt {attempt} failed; retrying in {RETRY_DELAY_S}s", flush=True)
            time.sleep(RETRY_DELAY_S)
        else:
            pending = [p for p in need if not done[p]]
            print(f"HB{hb} {pending}: FAILED after {MAX_RETRIES} attempts — HARD STOP", flush=True)
            return False

    for pair in need:
        _, _, occ = store_state(pair)
        print(f"HB{hb} {pair}: OK at {time.strftime('%H:%M:%S')} — {json.dumps(occ)}", flush=True)
    return True


def select_pairs(spec: str | None) -> tuple[str, ...]:
    """Parse an optional pair filter. None/empty means the full both-pairs set.

    An unknown pair name is a hard error rather than a silent no-op: a typo
    that selected nothing would report success while advancing zero heartbeats.
    """
    global PAIRS
    if not spec:
        PAIRS = PAIRS_ALL
        return PAIRS
    names = tuple(n.strip() for n in spec.split(",") if n.strip())
    if not names:
        PAIRS = PAIRS_ALL
        return PAIRS
    unknown = [n for n in names if n not in STORES]
    if unknown:
        raise SystemExit(
            f"unknown pair(s) {unknown}; known: {sorted(STORES)}"
        )
    PAIRS = names
    return PAIRS


def parse_args(argv: list[str]) -> tuple[int, int, tuple[str, ...], bool]:
    """<start> <end> [pairs] [--no-snapshot]

    An unknown flag is a hard error. A silently-ignored `--no-snapshot` would
    push to a public URL the caller believed they had disabled.
    """
    global PAIRS, SNAPSHOTS_ENABLED
    positional: list[str] = []
    snapshots = True
    for arg in argv:
        if arg == "--no-snapshot":
            snapshots = False
        elif arg.startswith("-"):
            raise SystemExit(f"unknown flag {arg!r}; known flags: --no-snapshot")
        else:
            positional.append(arg)
    if len(positional) < 2:
        raise SystemExit(
            "usage: lockstep_chain.py <start> <end> [pairs] [--no-snapshot]"
        )
    pairs = select_pairs(positional[2] if len(positional) > 2 else None)
    PAIRS, SNAPSHOTS_ENABLED = pairs, snapshots
    return int(positional[0]), int(positional[1]), pairs, snapshots


def main() -> int:
    start, end, pairs, snapshots = parse_args(sys.argv[1:])
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    label = "both pairs, merged clock" if pairs == PAIRS_ALL else (
        f"single clock, pairs={','.join(pairs)}"
    )
    snap = "on" if snapshots else "OFF (public viewer will not update)"
    print(f"LOCKSTEP CHAIN: HB{start}-{end} ({label}; snapshots {snap})",
          flush=True)
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    for pair in pairs:
        count, tick, _ = store_state(pair)
        print(f"PREFLIGHT {pair}: count={count} tick={tick} "
              f"(needs {start - 1} to start at {start})", flush=True)
        # Record the run so a boot has something to reason about. The
        # machine rebooted mid-census on 2026-09-30 and nobody found out
        # for hours; recover_runs.py can only resume a run it knows about.
        try:
            from recover_runs import record_run_state
            record_run_state(pair, start, end, os.getpid())
        except Exception as exc:
            print(f"  run-state not recorded: {type(exc).__name__}",
                  flush=True)

    # Store lock: refuse to run beside another writer on the same store.
    # Interleaving two chains into one heartbeat ledger produces a record
    # that looks plausible and is wrong, and no later check can detect it.
    lock_paths = []
    for pair in pairs:
        try:
            sys.path.insert(0, str(WORLD_SIM / "scripts"))
            from recover_runs import acquire_store_lock
            got = acquire_store_lock(pair, os.getpid())
        except Exception as exc:
            print(f"LOCK {pair}: unavailable ({type(exc).__name__}: {exc}) "
                  f"- refusing to run beside a possible second writer",
                  flush=True)
            return 1
        if got is None:
            print(f"LOCK {pair}: held by a live chain - refusing to start. "
                  f"Two writers on one store would corrupt the heartbeat "
                  f"ledger. If no chain is actually running, delete "
                  f"{WORLD_SIM / '.scratch' / 'lockstep' / f'chain_{pair}.lock'}",
                  flush=True)
            for p in lock_paths:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
            return 1
        lock_paths.append(got)
        print(f"LOCK {pair}: acquired (pid {os.getpid()})", flush=True)

    try:
        for hb in range(start, end + 1):
            if not run_tick(hb):
                return 1
            if snapshots and hb % SNAPSHOT_EVERY == 0:
                push_snapshot()
    finally:
        for p in lock_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    for pair in PAIRS:
        count, tick, occ = store_state(pair)
        print(f"\nLOCKSTEP FINAL {pair}: count={count}, tick={tick}", flush=True)
        print(f"Positions: {json.dumps(occ)}", flush=True)
    print(f"End: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
