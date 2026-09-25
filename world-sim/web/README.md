# Genesis Civilization Viewer — public web app

A tiny Flask app that serves the two-civilization viewer: Adam and Eve,
live on their planet, west pair on the Dawn Bluff, east pair in Origin
Valley. Like a nature documentary where the animals are LLM agents.

## What it serves

- `GET /` — the full viewer (pair switcher, fog-of-war map, heartbeat
  scrubber, event/feed timeline)
- `GET /viewer_data.js` — the current snapshot payload (slim, ~0.6 MB)
- `GET /health` — uptime probe with per-pair tick counts
- `POST /refresh` — force a snapshot refresh (rate-limited: 2/minute/IP)

## Modes

### Demo mode (default) — zero coupling to the home world

Ships a packaged snapshot (`viewer_data.js`) and serves it. Nothing to
connect, no secrets, works on any box.

```bash
python world-sim/scripts/export_viewer_snapshot.py --slim \
  --out world-sim/web/viewer_data.js   # regenerate the packaged snapshot
# commit or copy viewer_data.js with the deploy
pip install -r world-sim/web/requirements.txt
python world-sim/web/app.py            # listens on 0.0.0.0:8000
```

### Live mode — reads the canonical stores on the source machine

```bash
export GENESIS_MODE=live
export GENESIS_STORE_EAST="S:\\Genesis Kernel World Sim\\world-sim\\.runtime\\first-pair"
export GENESIS_STORE_WEST="S:\\Genesis Kernel World Sim\\world-sim\\.runtime\\first-pair-west"
export GENESIS_REFRESH_SECONDS=60
python world-sim/web/app.py
```

Every 60 s the app re-runs `scripts/export_viewer_snapshot.py --slim`
against those stores and atomically swaps the served payload. The running
world is never touched (read-only).

Later, when we want a public VPS to show *live* data, the sync path is:
package a fresh snapshot on the source machine, push it to the VPS
(scp/rsync/git), and the demo-mode app picks it up because it re-reads
the file from disk per request. No live connection required.

## Deploy: Docker

```bash
docker build -t genesis-viewer world-sim/web/
docker run -p 8000:8000 genesis-viewer
# or
docker compose -f world-sim/web/docker-compose.yml up -d
```

## Deploy: systemd on Ubuntu VPS (Hostinger)

```bash
# as root or with sudo
mkdir -p /opt/genesis-viewer
cp -r world-sim /opt/genesis-viewer/
cd /opt/genesis-viewer/world-sim/web
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp genesis-viewer.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now genesis-viewer
systemctl status genesis-viewer
```

## Security posture

- Read-only: the app never writes to the canonical stores; the exporter it
  invokes only reads them.
- No API keys in this package; mode/paths come from env vars only.
- `/refresh` is rate-limited (fixed window, per IP); everything else is a
  static read.
- The mystery layer is never in the payload: `viewer_data.js` carries only
  what agents have already discovered; the world's secrets stay secret.
