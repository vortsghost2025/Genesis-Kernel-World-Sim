"""Sync local viewer snapshot data to Hostinger VPS.

Transfers viewer_data.js (and optionally full assets) to /var/www/html/genesis/
on the Hostinger VPS (187.77.3.56) so deliberatefederation.cloud/genesis/ stays
in sync with living world progress.

Usage:
    python world-sim/scripts/sync_viewer_to_vps.py
    python world-sim/scripts/sync_viewer_to_vps.py --all
    python world-sim/scripts/sync_viewer_to_vps.py --watch
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parent.parent
VIEWER_DIR = WORLD_SIM / "viewer"
DATA_JS = VIEWER_DIR / "viewer_data.js"
VPS_HOST = "187.77.3.56"
VPS_DIR = "/var/www/html/genesis"


def sync_file(src: Path, dest_dir: str = VPS_DIR) -> bool:
    if not src.is_file():
        print(f"[SYNC_ERROR] {src} not found")
        return False
    cmd = ["scp", str(src), f"{VPS_HOST}:{dest_dir}/"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[SYNC_OK] {src.name} -> {VPS_HOST}:{dest_dir}/ ({src.stat().st_size:,} bytes)")
        return True
    print(f"[SYNC_FAIL] {src.name}: {res.stderr.strip()}")
    return False


def sync_all() -> bool:
    files = list(VIEWER_DIR.glob("*.html")) + \
            list(VIEWER_DIR.glob("*.js")) + \
            list(VIEWER_DIR.glob("*.json")) + \
            list(VIEWER_DIR.glob("*.png")) + \
            list(VIEWER_DIR.glob("*.jpg"))
    ok = True
    for f in sorted(files):
        if not sync_file(f):
            ok = False
    return ok


def watch_loop(poll_interval: float = 30.0):
    last_mtime = DATA_JS.stat().st_mtime if DATA_JS.is_file() else 0
    print(f"[SYNC_WATCH] Monitoring {DATA_JS.name} every {poll_interval}s...")
    while True:
        try:
            if DATA_JS.is_file():
                mtime = DATA_JS.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    sync_file(DATA_JS)
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[SYNC_WATCH_ERROR] {e}")
            time.sleep(poll_interval)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Sync all assets including HTML and images")
    ap.add_argument("--watch", action="store_true", help="Continuously sync viewer_data.js when modified")
    args = ap.parse_args()

    if args.all:
        return 0 if sync_all() else 1
    if args.watch:
        watch_loop()
        return 0
    return 0 if sync_file(DATA_JS) else 1


if __name__ == "__main__":
    sys.exit(main())
