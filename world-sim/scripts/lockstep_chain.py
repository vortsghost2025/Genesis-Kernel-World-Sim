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
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
REPO_ROOT = WORLD_SIM.parent
RUNNER = WORLD_SIM / "scripts" / "launch_canonical_heartbeat_detached.py"
EXPORTER = WORLD_SIM / "scripts" / "export_viewer_snapshot.py"
EVIDENCE_DIR = WORLD_SIM / ".scratch" / "lockstep"
SNAPSHOT_OUT = EVIDENCE_DIR / "viewer_data.js"

PAIRS = ("east", "west")
STORES = {
    "east": WORLD_SIM / ".runtime" / "first-pair",
    "west": WORLD_SIM / ".runtime" / "first-pair-west",
}

MAX_RETRIES = 3
RETRY_DELAY_S = 45
SNAPSHOT_EVERY = 10
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
            "--evidence", str(evidence),
            "--log", str(log),
            "--status", str(status),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        print(f"HB{hb} {pair}: LAUNCH FAIL — {proc.stderr[:200]}", flush=True)
        return False
    return True


def wait_for_status(pair: str, hb: int) -> bool:
    """Block until the detached runner reports exported or failed."""
    status = status_path(pair, hb)
    while True:
        if status.is_file():
            try:
                s = json.loads(status.read_text(encoding="utf-8"))
                st = s.get("status", "")
                if st == "evidence-exported":
                    return True
                if st == "failed":
                    print(f"HB{hb} {pair}: runner FAILED — {s.get('detail', '?')}", flush=True)
                    return False
            except Exception:
                pass
        time.sleep(5)


def push_snapshot() -> None:
    """Export the slim snapshot and push it to the public show. Non-fatal."""
    try:
        r = subprocess.run(
            [sys.executable, str(EXPORTER), "--slim", "--out", str(SNAPSHOT_OUT)],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            print(f"SNAPSHOT: export failed — {r.stderr[:150]}", flush=True)
            return
        scp = subprocess.run(
            ["scp", str(SNAPSHOT_OUT), f"{PUBLIC_VPS}:/tmp/viewer_data.js"],
            capture_output=True, text=True, timeout=120,
        )
        if scp.returncode != 0:
            print(f"SNAPSHOT: scp failed — {scp.stderr[:150]}", flush=True)
            return
        ssh = subprocess.run(
            ["ssh", PUBLIC_VPS,
             "docker cp /tmp/viewer_data.js genesis-viewer:/app/web/viewer_data.js"],
            capture_output=True, text=True, timeout=120,
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


def main() -> int:
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"LOCKSTEP CHAIN: HB{start}-{end} (both pairs, merged clock)", flush=True)
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    for hb in range(start, end + 1):
        if not run_tick(hb):
            return 1
        if hb % SNAPSHOT_EVERY == 0:
            push_snapshot()

    for pair in PAIRS:
        count, tick, occ = store_state(pair)
        print(f"\nLOCKSTEP FINAL {pair}: count={count}, tick={tick}", flush=True)
        print(f"Positions: {json.dumps(occ)}", flush=True)
    print(f"End: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
