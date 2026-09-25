"""Genesis Civilization Viewer - public web app.

Serves the two-civilization viewer (world-sim/viewer/index.html) with a
refreshed slim data payload. Public-watchable: reads canonical stores
(optionally) and republishes a safe, trimmed snapshot. Never writes to
canonical state.

Modes:
    demo  - serves the packaged viewer_data.js snapshot (default; works
            standalone on a VPS with zero connection to the home source)
    live  - additionally re-runs scripts/export_viewer_snapshot.py --slim
            on a timer, refreshing viewer_data.js from the live stores

Endpoints:
    GET /                     the viewer (static)
    GET /viewer_data.js       the current snapshot payload
    GET /health               uptime probe: {status, tick_east, tick_west}
    POST /refresh             force a snapshot refresh (rate-limited)

Security posture: read-only against the repo; no secrets; refresh endpoint
is rate-limited; everything else is a static read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, request, send_file
except ImportError:
    raise SystemExit("Flask required: pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent
WORLD_SIM = HERE.parent
REPO_ROOT = WORLD_SIM.parent

MODE = os.environ.get("GENESIS_MODE", "demo").strip().lower()  # demo | live
PORT = int(os.environ.get("GENESIS_PORT", "8000"))
REFRESH_SECONDS = int(os.environ.get("GENESIS_REFRESH_SECONDS", "60"))
STORE_EAST = os.environ.get(
    "GENESIS_STORE_EAST", str(WORLD_SIM / ".runtime" / "first-pair"))
STORE_WEST = os.environ.get(
    "GENESIS_STORE_WEST", str(WORLD_SIM / ".runtime" / "first-pair-west"))
RATE_LIMIT_RPM = int(os.environ.get("GENESIS_REFRESH_RPM", "2"))

DATA_FILE = HERE / "viewer_data.js"
INDEX_FILE = WORLD_SIM / "viewer" / "index.html"

app = Flask(__name__)

# --- rate limiting (fixed window, in-memory, single process) -------------
_lock = threading.Lock()
_refresh_windows: dict[str, tuple[int, int]] = {}  # ip -> (window_start_min, count)
_state = {"last_refresh": 0.0, "last_error": None, "ticks": {}}


def _rate_ok(ip: str) -> bool:
    now_min = int(time.time() // 60)
    with _lock:
        start, count = _refresh_windows.get(ip, (now_min, 0))
        if start != now_min:
            start, count = now_min, 0
        if count >= RATE_LIMIT_RPM:
            return False
        _refresh_windows[ip] = (start, count + 1)
        return True


def _run_export() -> None:
    """Regenerate viewer_data.js from the canonical stores (live mode). Never writes to them."""
    if MODE != "live":
        return
    try:
        subprocess.run(
            [sys.executable, str(WORLD_SIM / "scripts" / "export_viewer_snapshot.py"),
             "--slim", "--out", str(DATA_FILE)],
            cwd=str(REPO_ROOT), check=True, capture_output=True, text=True,
            timeout=180,
            env={**os.environ,
                 "GENESIS_STORE_EAST": STORE_EAST,
                 "GENESIS_STORE_WEST": STORE_WEST},
        )
        _state["last_refresh"] = time.time()
        _state["last_error"] = None
    except Exception as exc:  # keep serving last-known-good snapshot
        _state["last_error"] = f"{type(exc).__name__}: {exc}"


def _refresh_loop() -> None:
    while True:
        time.sleep(REFRESH_SECONDS)
        _run_export()


# --- CORS (viewer only reads these) --------------------------------------
@app.after_request
def _cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "no-cache" if request.path == "/viewer_data.js" else resp.headers.get("Cache-Control", "")
    return resp


@app.get("/")
def index():
    return send_file(INDEX_FILE)


@app.get("/viewer_data.js")
def viewer_data():
    return send_file(DATA_FILE, mimetype="application/javascript")


@app.get("/health")
def health():
    ticks = {}
    try:
        text = DATA_FILE.read_text(encoding="utf-8", errors="replace")
        for pair in ("east", "west"):
            marker = f'"{pair}":'
            if marker in text:
                # cheap: find exported_tick after the pair marker
                i = text.find(marker)
                j = text.find('"exported_tick":', i)
                if j > 0:
                    k = text.find(",", j)
                    ticks[pair] = int(text[j + 16:k].strip())
    except Exception:
        pass
    return jsonify({
        "status": "ok", "mode": MODE, "ticks": ticks,
        "last_refresh_age_s": round(time.time() - _state["last_refresh"], 1) if _state["last_refresh"] else None,
        "last_error": _state["last_error"],
    })


@app.post("/refresh")
def refresh():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    if not _rate_ok(ip):
        return jsonify({"status": "rate_limited", "try_again_in_s": 60}), 429
    if MODE != "live":
        return jsonify({"status": "demo_mode", "note": "serving packaged snapshot; no live source connected"}), 200
    _run_export()
    return jsonify({"status": "refreshed" if not _state["last_error"] else "error",
                    "last_error": _state["last_error"]})


if __name__ == "__main__":
    if not DATA_FILE.exists():
        print("Packaging demo snapshot...")
        subprocess.run([sys.executable,
                        str(WORLD_SIM / "scripts" / "export_viewer_snapshot.py"),
                        "--slim", "--out", str(DATA_FILE)],
                       cwd=str(REPO_ROOT), check=True)
    if MODE == "live":
        threading.Thread(target=_refresh_loop, daemon=True).start()
    print(f"Genesis viewer on 0.0.0.0:{PORT} (mode={MODE})")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
