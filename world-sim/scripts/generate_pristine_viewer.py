"""Construct pristine index.html with cinematic dark-glass UI, organic terrain, and real-time action playback."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "viewer" / "index.html"

HTML_CONTENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Genesis — Civilization Observatory</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg-deep: #030509;
  --bg-panel: rgba(8, 12, 20, 0.78);
  --bg-card: rgba(14, 20, 32, 0.65);
  --bg-glass: rgba(20, 28, 44, 0.55);

  --border-line: rgba(255, 255, 255, 0.08);
  --border-subtle: rgba(255, 255, 255, 0.04);
  --border-glow: rgba(0, 210, 211, 0.35);

  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-tertiary: #64748b;

  --east-cyan: #00d2d3;
  --west-amber: #feca57;
  --crit-red: #ff4757;
  --good-green: #2ed573;
  --warm-orange: #ff9f43;

  --font-display: 'Cinzel', serif;
  --font-body: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-ui: 'Outfit', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; width: 100%; overflow: hidden; background: var(--bg-deep); color: var(--text-primary); font-family: var(--font-body); }

/* Root App Shell */
#app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
}

/* Header Masthead */
header {
  height: 56px;
  background: rgba(6, 9, 16, 0.88);
  border-bottom: 1px solid var(--border-line);
  backdrop-filter: blur(20px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 40;
  flex-shrink: 0;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 16px;
}
.brand-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  letter-spacing: 0.28em;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 0 20px rgba(0, 210, 211, 0.4);
}
.brand-tag {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  color: var(--text-tertiary);
  border-left: 1px solid var(--border-line);
  padding-left: 14px;
  text-transform: uppercase;
}

.nav-cluster {
  display: flex;
  align-items: center;
  gap: 8px;
}
.nav-pill {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  border-radius: 20px;
  padding: 5px 14px;
  font-family: var(--font-ui);
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s ease;
  user-select: none;
}
.nav-pill:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}
.nav-pill.active {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.25);
  color: #fff;
  box-shadow: 0 0 14px rgba(0, 0, 0, 0.5);
}
.civ-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.civ-dot.east { background: var(--east-cyan); box-shadow: 0 0 8px var(--east-cyan); }
.civ-dot.west { background: var(--west-amber); box-shadow: 0 0 8px var(--west-amber); }

.telemetry-cluster {
  display: flex;
  align-items: center;
  gap: 16px;
}
.weather-hud {
  display: flex;
  gap: 12px;
}
.w-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 0.70rem;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.03);
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
}
.status-badge-live {
  background: rgba(46, 213, 115, 0.15);
  border: 1px solid rgba(46, 213, 115, 0.4);
  color: var(--good-green);
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-badge-live::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--good-green);
  box-shadow: 0 0 8px var(--good-green);
}
.hb-counter-masthead {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.04em;
}

/* Main Workspace */
#main {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}

/* Map Viewport */
#map-panel {
  flex: 1;
  position: relative;
  background: #020306;
  overflow: hidden;
}
#map-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: grab;
  display: block;
}
#map-canvas.dragging { cursor: grabbing; }

/* Floating Emergency Banner */
#distress-hud {
  position: absolute;
  top: 14px;
  left: 50%;
  transform: translateX(-50%);
  display: none;
  align-items: center;
  gap: 10px;
  background: linear-gradient(90deg, rgba(38, 10, 18, 0.95), rgba(56, 12, 24, 0.95));
  border: 1px solid rgba(255, 71, 87, 0.75);
  box-shadow: 0 8px 30px rgba(255, 71, 87, 0.4);
  border-radius: 24px;
  padding: 5px 16px;
  backdrop-filter: blur(16px);
  z-index: 50;
  cursor: pointer;
  white-space: nowrap;
}
.distress-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--crit-red);
  box-shadow: 0 0 10px var(--crit-red);
  animation: pulse-red 1.2s infinite;
}
@keyframes pulse-red { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.4); } }
.distress-text {
  font-family: var(--font-ui);
  font-size: 0.74rem;
  font-weight: 600;
  color: #ffb8b8;
}
.distress-cta {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: #fff;
  background: rgba(255, 71, 87, 0.35);
  padding: 2px 8px;
  border-radius: 10px;
}

/* Action Playback Bar (Clean, Minimal, Docked at Bottom of Map) */
#playback-bar {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(8, 12, 20, 0.92);
  border: 1px solid var(--border-line);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.75), 0 0 20px rgba(0, 210, 211, 0.1);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  padding: 8px 18px;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 14px;
  max-width: min(94vw, 840px);
}
.ctrl-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 6px 10px;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  user-select: none;
}
.ctrl-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  transform: translateY(-1px);
}
.ctrl-btn.primary {
  background: linear-gradient(135deg, rgba(0, 210, 211, 0.35), rgba(9, 132, 227, 0.35));
  border-color: rgba(0, 210, 211, 0.6);
  min-width: 68px;
  color: #fff;
}
.ctrl-btn.live-pill {
  background: rgba(255, 71, 87, 0.15);
  border-color: rgba(255, 71, 87, 0.4);
  color: #ff7675;
}
.ctrl-btn.live-pill.active {
  background: rgba(255, 71, 87, 0.35);
  border-color: #ff4757;
  color: #fff;
  box-shadow: 0 0 10px rgba(255, 71, 87, 0.4);
}
.slider-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 180px;
}
#scrubber {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.15);
  outline: none;
  cursor: pointer;
}
#scrubber::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--east-cyan);
  box-shadow: 0 0 8px var(--east-cyan);
  cursor: pointer;
}
.time-readout {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* Speed / Mode Selectors */
.speed-cluster {
  display: flex;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}
.speed-opt {
  padding: 3px 8px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-tertiary);
  cursor: pointer;
}
.speed-opt.active {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

/* Right Sidebar Telemetry Suite */
#sidebar {
  width: 440px;
  background: rgba(8, 12, 20, 0.92);
  border-left: 1px solid var(--border-line);
  backdrop-filter: blur(24px);
  display: flex;
  flex-direction: column;
  z-index: 30;
  flex-shrink: 0;
}
.sidebar-nav {
  display: flex;
  border-bottom: 1px solid var(--border-line);
  background: rgba(4, 7, 12, 0.6);
  flex-shrink: 0;
}
.tab-btn {
  flex: 1;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-tertiary);
  font-family: var(--font-ui);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 14px 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s ease;
}
.tab-btn:hover { color: #fff; }
.tab-btn.active {
  color: #fff;
  border-bottom-color: var(--east-cyan);
  background: rgba(0, 210, 211, 0.05);
}
.tab-badge {
  background: rgba(255, 71, 87, 0.25);
  color: #ff7675;
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 0.65rem;
  font-family: var(--font-mono);
}

.tab-pane-container {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* Biometrics Agent Cards */
.agent-card {
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 16px;
  transition: border-color 0.2s ease;
}
.agent-card.adam { border-left: 3px solid var(--east-cyan); }
.agent-card.eve { border-left: 3px solid var(--west-amber); }
.agent-card.collapsed {
  border-color: rgba(255, 71, 87, 0.55);
  background: linear-gradient(180deg, rgba(30, 8, 14, 0.55), var(--bg-card));
}
.agent-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.agent-profile {
  display: flex;
  align-items: center;
  gap: 12px;
}
.agent-portrait {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.agent-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.agent-name {
  font-family: var(--font-ui);
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.02em;
}
.agent-sub {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
}
.agent-state-badge {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  text-transform: uppercase;
}
.agent-state-badge.collapsed {
  background: rgba(255, 71, 87, 0.2);
  color: var(--crit-red);
  border: 1px solid rgba(255, 71, 87, 0.4);
}
.agent-state-badge.active {
  background: rgba(46, 213, 115, 0.2);
  color: var(--good-green);
  border: 1px solid rgba(46, 213, 115, 0.4);
}

.sector-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 6px;
  padding: 6px 10px;
  margin-bottom: 12px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-secondary);
}
.sector-cta {
  color: var(--east-cyan);
  cursor: pointer;
  font-weight: 600;
}
.sector-cta:hover { text-decoration: underline; }

/* Telemetry Grid */
.telemetry-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin-bottom: 14px;
}
.metric-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.metric-meta {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  color: var(--text-tertiary);
}
.metric-bar-bg {
  height: 5px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}
.metric-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.metric-bar-fill.hunger { background: var(--east-cyan); }
.metric-bar-fill.vital { background: var(--crit-red); }
.metric-bar-fill.warmth { background: var(--warm-orange); }
.metric-bar-fill.wetness { background: #3867d6; }

/* Cognitive Dossier / Inner Voice */
.agent-inner-voice {
  background: rgba(0, 0, 0, 0.45);
  border-left: 2px solid var(--border-glow);
  border-radius: 6px;
  padding: 9px 12px;
  margin-bottom: 12px;
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.72rem;
  line-height: 1.45;
  color: #cbd5e1;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.agent-card.collapsed .agent-inner-voice {
  border-left-color: var(--crit-red);
  background: rgba(30, 8, 12, 0.6);
  color: #fca5a5;
}

/* Pack Inventory */
.inventory-tray {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.inv-pill {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 3px 8px;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  color: var(--text-secondary);
}

/* Chronicle & Comms Cards */
.chronicle-card {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 0.76rem;
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.chronicle-card:last-child { border-bottom: none; }
.chronicle-hb {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.chronicle-who { font-weight: 700; color: #fff; }
.chronicle-text { color: var(--text-secondary); }

.transmission-card {
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.tx-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
}
.tx-sender { color: var(--east-cyan); font-weight: 700; }
.tx-body {
  font-size: 0.76rem;
  line-height: 1.4;
  color: #e2e8f0;
}

/* Zoom Level Hint */
#zoom-tag {
  position: absolute;
  top: 14px;
  left: 14px;
  background: rgba(8, 12, 20, 0.85);
  border: 1px solid var(--border-line);
  padding: 4px 10px;
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-tertiary);
  pointer-events: none;
}
#zoom-tag span { color: var(--east-cyan); font-weight: 700; }

/* Tooltip */
#tooltip {
  position: fixed;
  display: none;
  z-index: 100;
  pointer-events: none;
  background: rgba(8, 12, 20, 0.94);
  border: 1px solid var(--border-line);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 0.74rem;
  line-height: 1.4;
}
</style>
</head>
<body>
<div id="app">
  <!-- Masthead -->
  <header>
    <div class="brand-group">
      <div class="brand-title">GENESIS</div>
      <div class="brand-tag">Observatory // Continent Bifurcation</div>
      <div class="nav-cluster">
        <div class="nav-pill active" id="btn-east"><span class="civ-dot east"></span>East Valley</div>
        <div class="nav-pill" id="btn-west"><span class="civ-dot west"></span>West Dawn</div>
        <div class="nav-pill" id="btn-fit">⛶ Orbit</div>
      </div>
    </div>

    <div class="telemetry-cluster">
      <div class="weather-hud" id="weather-hud"></div>
      <div class="status-badge-live">STREAM LIVE</div>
      <div class="hb-counter-masthead" id="hb-masthead">HB 0</div>
    </div>
  </header>

  <!-- Main View -->
  <div id="main">
    <!-- Map Canvas Panel -->
    <div id="map-panel">
      <canvas id="map-canvas"></canvas>

      <div id="zoom-tag">ZOOM <span id="zoom-val">15.0×</span> · DRAG · SCROLL</div>

      <!-- Distress Banner -->
      <div id="distress-hud">
        <span class="distress-pulse"></span>
        <span class="distress-text" id="distress-msg">CRITICAL TELEMETRY</span>
        <span class="distress-cta">PULSE ↗</span>
      </div>

      <!-- Action Playback Bar -->
      <div id="playback-bar">
        <button class="ctrl-btn" id="pb-start" title="Dawn of Time (HB 1)">⏮</button>
        <button class="ctrl-btn" id="pb-prev" title="Step Back 1 Heartbeat (Left Arrow)">◀</button>
        <button class="ctrl-btn primary" id="pb-play" title="Play / Pause Replay (Spacebar)">▶ PLAY</button>
        <button class="ctrl-btn" id="pb-next" title="Step Forward 1 Heartbeat (Right Arrow)">▶</button>
        <button class="ctrl-btn live-pill active" id="pb-live" title="Return to Live Telemetry">🔴 LIVE</button>

        <div class="slider-wrap">
          <input type="range" id="scrubber" min="1" max="100" value="100" />
          <span class="time-readout" id="pb-counter">0 / 0</span>
        </div>

        <div class="speed-cluster" id="speed-cluster">
          <div class="speed-opt" data-spd="1">1×</div>
          <div class="speed-opt active" data-spd="2">2×</div>
          <div class="speed-opt" data-spd="5">5×</div>
          <div class="speed-opt" data-spd="10">10×</div>
        </div>
      </div>
    </div>

    <!-- Right Telemetry Sidebar -->
    <aside id="sidebar">
      <nav class="sidebar-nav">
        <button class="tab-btn active" data-tab="tab-agents">Biometrics</button>
        <button class="tab-btn" data-tab="tab-chronicle">Chronicle</button>
        <button class="tab-btn" data-tab="tab-comms">Comms <span id="tx-badge" class="tab-badge" style="display:none">0</span></button>
      </nav>

      <div class="tab-pane-container">
        <!-- Biometrics Tab -->
        <div class="tab-pane active" id="tab-agents">
          <div id="agents-container"></div>
        </div>

        <!-- Chronicle Tab -->
        <div class="tab-pane" id="tab-chronicle">
          <div id="chronicle-container"></div>
        </div>

        <!-- Comms Tab -->
        <div class="tab-pane" id="tab-comms">
          <div id="comms-container"></div>
        </div>
      </div>
    </aside>
  </div>
</div>

<div id="tooltip"></div>

<!-- Load Data -->
<script>document.write('<scr' + 'ipt src="viewer_data.js?v=' + Date.now() + '"></scr' + 'ipt>');</script>
<script>
(() => {
"use strict";

let D = window.VIEWER_DATA || {};
let PAIRS = D.pairs || {};
let TM = D.true_map || {};

let selectedPair = "west";
let playbackMode = "live";
let currentHb = 0;
let minHb = 1;
let maxHb = 1;
let isPlaying = false;
let playSpeed = 2;
let lastStepTime = 0;

const tiles = new Map();
const tileByCoord = new Map();
let minX = 0, maxX = 0, minY = 0, maxY = 0, GW = 1, GH = 1, gcx = 0, gcy = 0;

function populateTiles() {
  tiles.clear();
  tileByCoord.clear();
  const allTiles = (TM.tiles || []).concat(Object.values(D.shared_tiles || {}));
  const xs = [], ys = [];
  for (const t of allTiles) {
    if (!t || !t.tile_id) continue;
    tiles.set(t.tile_id, t);
    const c = t.coordinates;
    if (c) {
      tileByCoord.set(c.x + "," + c.y, t);
      xs.push(c.x); ys.push(c.y);
    }
  }
  if (xs.length) {
    minX = Math.min(...xs); maxX = Math.max(...xs);
    minY = Math.min(...ys); maxY = Math.max(...ys);
    GW = maxX - minX + 1; GH = maxY - minY + 1;
    gcx = minX + GW / 2; gcy = minY + GH / 2;
  }
}
populateTiles();

// Biome Colors (Rich Earthy Fantasy Cartography)
const BIOME_COLORS = {
  deep_ravine:      [14, 13, 22],
  deep_lake:        [10, 36, 62],
  warm_coast:       [72, 60, 44],
  temperate_valley: [26, 56, 38],
  temperate_hills:  [42, 62, 40],
  highland:         [70, 78, 92],
  temperate_forest: [22, 48, 32],
  dense_woodland:   [16, 40, 26],
  dark_thicket:     [12, 30, 22],
  coastal_forest:   [24, 52, 38],
  coastal_cliffs:   [82, 90, 104],
  open_sea:         [6, 24, 44],
};
const PAIR_RGB = { east: [0, 210, 211], west: [254, 202, 87] };

function baseColor(t) {
  const e = t.elevation == null ? 0.5 : t.elevation;
  if (t.water) {
    const b = t.water.drinkable ? [16, 68, 108] : [10, 36, 62];
    const k = 0.75 + e * 0.45;
    return [b[0] * k, b[1] * k, b[2] * k];
  }
  let b = BIOME_COLORS[t.biome] || [34, 42, 54];
  const k = 0.75 + e * 0.55;
  let r = b[0] * k, g = b[1] * k, bl = b[2] * k;
  if (e > 0.82) {
    const m = (e - 0.82) / 0.18;
    r = r + (220 - r) * m; g = g + (230 - g) * m; bl = bl + (240 - bl) * m;
  }
  return [r, g, bl];
}

// Sprites & Portraits Preloading
const sprites = {
  adam_standing: new Image(),
  eve_standing: new Image(),
  adam_collapsed: new Image(),
  eve_collapsed: new Image(),
  campfire: new Image(),
  landmark: new Image()
};
for (const [key, img] of Object.entries(sprites)) {
  img._ok = false;
  img.onload = () => { img._ok = true; drawFrame(performance.now()); };
  img.src = `${key}.png`;
}
const portraits = {
  adam: new Image(),
  eve: new Image()
};
for (const [key, img] of Object.entries(portraits)) {
  img._ok = false;
  img.onload = () => { img._ok = true; drawFrame(performance.now()); };
  img.src = `${key}_portrait.jpg`;
}
const baseImg = new Image();
baseImg._ok = false;
baseImg.onload = () => { baseImg._ok = true; drawFrame(performance.now()); };
baseImg.src = "world_base.png";

// Canvas & Viewport
const canvas = document.getElementById("map-canvas");
const ctx = canvas.getContext("2d");
const panel = document.getElementById("map-panel");
const dpr = Math.min(window.devicePixelRatio || 1, 2);

let view = { scale: 15, cx: 0, cy: 0 };
let cssW = 1, cssH = 1;

function resize() {
  cssW = panel.clientWidth || 100;
  cssH = panel.clientHeight || 100;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
}
resize();
window.addEventListener("resize", () => { resize(); drawFrame(performance.now()); });

function screenToWorld(sx, sy) {
  return {
    x: view.cx + (sx - cssW / 2) / view.scale,
    y: view.cy + (sy - cssH / 2) / view.scale,
  };
}
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// Smooth Camera Glide
let animReq = null;
function animateTo(targetCx, targetCy, targetScale, durationMs = 600) {
  if (animReq) cancelAnimationFrame(animReq);
  const startCx = view.cx, startCy = view.cy, startScale = view.scale;
  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const p = Math.min(1, elapsed / durationMs);
    const ease = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
    view.cx = startCx + (targetCx - startCx) * ease;
    view.cy = startCy + (targetCy - startCy) * ease;
    view.scale = startScale + (targetScale - startScale) * ease;
    drawFrame(now);
    if (p < 1) animReq = requestAnimationFrame(step);
    else animReq = null;
  }
  animReq = requestAnimationFrame(step);
}

// Procedural Organic Landscape Layer (Clean, Seamless, Topographical)
const layerCache = new Map();
let layerPx = 0;
function getLayer(px) {
  if (layerCache.has(px)) return layerCache.get(px);
  const W = GW * px, H = GH * px;
  const c2 = document.createElement("canvas");
  c2.width = W; c2.height = H;
  const g = c2.getContext("2d");

  // 1. Base Biomes (Seamless fill)
  tiles.forEach(t => {
    const c = t.coordinates; if (!c) return;
    const x = (c.x - minX) * px, y = (c.y - minY) * px;
    const col = baseColor(t);
    g.fillStyle = `rgb(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])})`;
    g.fillRect(x, y, px, px);
  });

  // 2. Soft Topographical Relief & Natural Shoreline Gradients
  tiles.forEach(t => {
    const c = t.coordinates; if (!c) return;
    const x = (c.x - minX) * px, y = (c.y - minY) * px;
    const e = t.elevation == null ? 0.5 : t.elevation;

    if (t.water) {
      // Check if near land
      const nearLand = [[0,-1],[0,1],[-1,0],[1,0]].some(([dx, dy]) => {
        const n = tileByCoord.get((c.x + dx) + "," + (c.y + dy));
        return n && !n.water;
      });
      if (nearLand) {
        g.fillStyle = "rgba(0, 242, 254, 0.22)";
        g.fillRect(x, y, px, px);
        g.strokeStyle = "rgba(255, 255, 255, 0.35)";
        g.lineWidth = Math.max(1, px * 0.08);
        g.strokeRect(x, y, px, px);
      }
    } else {
      // Sun Hillshading (NW Sun)
      const wTile = tileByCoord.get((c.x - 1) + "," + c.y);
      const nTile = tileByCoord.get(c.x + "," + (c.y - 1));
      const eW = wTile ? (wTile.elevation ?? 0.5) : e;
      const eN = nTile ? (nTile.elevation ?? 0.5) : e;
      const slope = (e - eW) * 0.65 + (e - eN) * 0.65;
      if (Math.abs(slope) > 0.015) {
        if (slope > 0) {
          g.fillStyle = `rgba(255, 255, 235, ${Math.min(0.24, slope * 0.5).toFixed(3)})`;
        } else {
          g.fillStyle = `rgba(0, 4, 14, ${Math.min(0.35, -slope * 0.7).toFixed(3)})`;
        }
        g.fillRect(x, y, px, px);
      }
    }

    // Basalt Ridge Barrier
    if (t.blocks_travel) {
      g.fillStyle = "rgba(18, 12, 16, 0.9)";
      g.fillRect(x, y, px, px);
      g.fillStyle = "rgba(255, 71, 87, 0.2)";
      g.fillRect(x, y, px, Math.max(1, px * 0.15));
    }
  });

  layerCache.set(px, c2);
  return c2;
}
function ensureLayer() {
  const want = clamp(Math.round(view.scale), 4, 28);
  if (!layerPx || Math.abs(want / layerPx - 1) > 0.45) {
    layerPx = want;
    getLayer(layerPx);
  }
  return layerCache.get(layerPx) || getLayer(layerPx);
}

// Scene State & Objects
let objectsAll = [];
let objectsByTile = new Map();
let agentsAll = [];
const hbIndex = { east: new Map(), west: new Map() };
const timelineHbs = { east: [], west: [] };

function buildIndex() {
  for (const [pn, pair] of Object.entries(PAIRS)) {
    hbIndex[pn] = new Map();
    (pair.heartbeats || []).forEach(hb => {
      if (hb && hb.heartbeat != null) hbIndex[pn].set(hb.heartbeat, hb);
    });
    timelineHbs[pn] = Object.keys(pair.position_timeline || {}).map(Number).sort((a,b) => a - b);
  }
  const hbs = timelineHbs[selectedPair] || [];
  if (hbs.length) {
    minHb = hbs[0];
    maxHb = hbs[hbs.length - 1];
    if (!currentHb || playbackMode === "live") currentHb = maxHb;
  }
}
buildIndex();

function recomputeScene() {
  objectsAll = [];
  objectsByTile = new Map();
  for (const [pn, pair] of Object.entries(PAIRS)) {
    for (const [oid, o] of Object.entries(pair.public_objects || {})) {
      const rec = { ...o, _pair: pn, _oid: oid };
      objectsAll.push(rec);
      if (!objectsByTile.has(o.tile_id)) objectsByTile.set(o.tile_id, []);
      objectsByTile.get(o.tile_id).push(rec);
    }
  }

  // Active agents based on current playback heartbeat
  agentsAll = [];
  for (const [pn, pair] of Object.entries(PAIRS)) {
    const tl = pair.position_timeline || {};
    const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];
    for (const [ref, tid] of Object.entries(pos)) {
      agentsAll.push({ ref, pair: pn, tileId: tid });
    }
  }

  updateUI();
}

function objCategory(type) {
  const s = String(type || "").toLowerCase();
  if (s.includes("road")) return "road";
  if (s.includes("tower") || s.includes("landmark") || s.includes("monument")) return "landmark";
  if (s.includes("fire") || s.includes("hearth")) return "fire";
  return "craft";
}

// Floating Combat/Loot Text FX
const floatingTexts = [];
function spawnFloatingText(text, sx, sy, col = "#2ed573") {
  floatingTexts.push({ text, sx, sy, col, startTs: performance.now(), dur: 1800 });
  if (floatingTexts.length > 20) floatingTexts.shift();
}

// Activity & Speech Text Extractor
function getAgentActivity(pairName, agentRef) {
  const pair = PAIRS[pairName] || {};
  const chronicle = pair.chronicle || [];
  const raw = agentRef.toLowerCase();
  const shortName = raw.split("_")[1] || raw;

  // Check recent unheard asks
  for (const ask of (pair.agent_asks || [])) {
    const askWho = String(ask.agent || "").toLowerCase();
    if ((askWho.includes(shortName) || raw.includes(askWho)) && ask.status === "unheard") {
      let q = String(ask.question || "");
      if (q.length > 55) q = q.slice(0, 52) + "...";
      return { kind: "ask", text: `Asked: "${q}"`, short: q };
    }
  }

  // Check recent chronicle events
  for (let i = chronicle.length - 1; i >= 0; i--) {
    const e = chronicle[i];
    const who = String(e.who || "").toLowerCase();
    if (who === raw || who.includes(shortName) || raw.includes(who)) {
      let txt = String(e.text || "Active");
      if (txt.length > 55) txt = txt.slice(0, 52) + "...";
      return { kind: e.kind || "act", text: txt, short: txt };
    }
  }

  return { kind: "idle", text: "Exploring sector", short: "Exploring" };
}

// Character Figure Renderer (High-Res Painted Sprites + Actions)
function drawCharacter(g, a, sx, sy, s, ts, idx = 0) {
  const isAdam = a.ref.toLowerCase().includes("adam");
  const rawName = a.ref.split("_")[1] || a.ref;
  const name = rawName.toUpperCase();
  const pairData = PAIRS[a.pair] || {};
  const vitals = (pairData.vitals || {})[a.ref] || { hunger: 0, warmth: 80, vitality: 100, downed: false };
  const isDowned = Boolean(vitals.downed);
  const act = getAgentActivity(a.pair, a.ref);
  const accentHex = isAdam ? "#00d2d3" : "#feca57";

  g.save();
  const figScale = clamp(s / 16, 0.85, 1.4);
  let figureTopY = sy - 40;

  if (isDowned) {
    // Prone / Collapsed on Ground
    const breath = Math.sin(ts / 750);
    g.fillStyle = "rgba(0, 0, 0, 0.5)";
    g.beginPath();
    g.ellipse(sx, sy + 6 * figScale, 34 * figScale, 13 * figScale, 0, 0, Math.PI * 2);
    g.fill();

    const proneSprite = isAdam ? sprites.adam_collapsed : sprites.eve_collapsed;
    if (proneSprite && proneSprite._ok) {
      const spriteW = Math.max(90, s * 2.2) * (1 + breath * 0.02);
      const spriteH = spriteW * (proneSprite.height / proneSprite.width);
      const drawX = sx - spriteW / 2;
      const drawY = sy - spriteH * 0.55;
      g.drawImage(proneSprite, drawX, drawY, spriteW, spriteH);
      figureTopY = drawY;
    }
  } else {
    // Upright Active / Walking
    const breath = Math.sin(ts / 650);
    const isEating = act.kind === "eat";

    // Ground Shadow
    g.fillStyle = "rgba(0, 0, 0, 0.45)";
    g.beginPath();
    g.ellipse(sx, sy + 18 * figScale, 18 * figScale, 6 * figScale, 0, 0, Math.PI * 2);
    g.fill();

    // Standing Sprite
    const activeSprite = isAdam ? sprites.adam_standing : sprites.eve_standing;
    if (activeSprite && activeSprite._ok) {
      const sway = Math.sin(ts / 600) * 1.2;
      const figH = Math.max(85, s * 2.1) + Math.sin(ts / 750);
      const figW = figH * (activeSprite.width / activeSprite.height);
      const drawX = sx - figW / 2 + sway;
      const drawY = (sy + 18 * figScale) - figH;
      g.drawImage(activeSprite, drawX, drawY, figW, figH);
      figureTopY = drawY;

      // Eating animation particle
      if (isEating) {
        g.font = "14px sans-serif";
        g.fillText("🫐", sx + figW * 0.28, drawY + figH * 0.35 + Math.sin(ts / 180) * 2);
      }
    }
  }

  // Portrait Cameo Medallion on Map
  const portraitImg = isAdam ? portraits.adam : portraits.eve;
  const medR = 14 * figScale;
  const medY = figureTopY - medR - 8;

  if (portraitImg && portraitImg._ok) {
    g.save();
    g.beginPath();
    g.arc(sx, medY, medR, 0, Math.PI * 2);
    g.clip();
    g.drawImage(portraitImg, sx - medR, medY - medR, medR * 2, medR * 2);
    g.restore();

    g.strokeStyle = isDowned ? "#ff4757" : accentHex;
    g.lineWidth = 2.4;
    g.beginPath();
    g.arc(sx, medY, medR, 0, Math.PI * 2);
    g.stroke();
  }

  // Comic Action / Speech Bubble
  let bannerText = "";
  let iconPrefix = "";
  if (isDowned) {
    iconPrefix = "💤";
    bannerText = `${name}: COLLAPSED PRONE ON SOIL (${vitals.vitality.toFixed(1)}/12 HP)`;
  } else if (act.kind === "eat") {
    iconPrefix = "🫐";
    bannerText = `${name}: CONSUMING WILD BERRIES (+15 FOOD)`;
  } else if (act.kind === "ask") {
    iconPrefix = "💬";
    bannerText = `${name}: "${act.short}"`;
  } else {
    iconPrefix = "🌿";
    bannerText = `${name}: EXPLORING TERRAIN & GATHERING`;
  }

  let fullLabel = `${iconPrefix} ${bannerText}`;
  if (fullLabel.length > 50) fullLabel = fullLabel.slice(0, 47) + "...";

  g.font = "700 11px 'Plus Jakarta Sans', sans-serif";
  const tw = g.measureText(fullLabel).width;
  const bubbleW = Math.min(tw + 20, cssW - 24);
  const bubbleH = 22;
  const bubbleX = clamp(sx - bubbleW / 2, 12, cssW - bubbleW - 12);
  const bubbleY = medY - medR - bubbleH - 6 - (idx * (bubbleH + 6));

  // Pointer Tail
  const tailX = clamp(sx, bubbleX + 12, bubbleX + bubbleW - 12);
  g.fillStyle = isDowned ? "rgba(40, 10, 18, 0.95)" : "rgba(8, 14, 24, 0.95)";
  g.beginPath();
  g.moveTo(tailX - 5, bubbleY + bubbleH);
  g.lineTo(tailX, bubbleY + bubbleH + 5);
  g.lineTo(tailX + 5, bubbleY + bubbleH);
  g.closePath();
  g.fill();

  // Glass Box
  g.fillRect(bubbleX, bubbleY, bubbleW, bubbleH);
  g.strokeStyle = isDowned ? "rgba(255, 71, 87, 0.9)" : (isAdam ? "rgba(0, 210, 211, 0.85)" : "rgba(254, 202, 87, 0.85)");
  g.lineWidth = 1.4;
  g.strokeRect(bubbleX, bubbleY, bubbleW, bubbleH);

  g.fillStyle = isDowned ? "#ffc2c7" : "#ffffff";
  g.fillText(fullLabel, bubbleX + 10, bubbleY + 15);

  g.restore();
}

// Master Canvas Drawing Loop
function drawFrame(ts) {
  if (panel.clientWidth !== cssW || panel.clientHeight !== cssH) resize();
  const g = ctx;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Deep Space Void
  g.fillStyle = "#020306";
  g.fillRect(0, 0, cssW, cssH);

  const terrain = ensureLayer();
  const s = view.scale;
  const origin = screenToWorld(0, 0);
  const dx = (origin.x - minX) * s, dy = (origin.y - minY) * s;
  const dw = GW * s, dh = GH * s;

  // Unexplored Ghost Backdrop
  if (baseImg._ok) {
    g.save();
    g.globalAlpha = 0.28;
    g.drawImage(baseImg, -dx, -dy, dw, dh);
    g.restore();
  }

  // Crisp Terrain Layer (Smooth Bilinear Filter enabled to eliminate chunky pixels!)
  g.imageSmoothingEnabled = true;
  g.drawImage(terrain, -dx, -dy, dw, dh);

  const tl = screenToWorld(0, 0), br = screenToWorld(cssW, cssH);
  const vx0 = Math.floor(tl.x), vx1 = Math.ceil(br.x);
  const vy0 = Math.floor(tl.y), vy1 = Math.ceil(br.y);

  // Rare Sustenance Flora: Emerald Gems
  if (s >= 11) {
    tiles.forEach(t => {
      const c = t.coordinates; if (!c) return;
      if (c.x < vx0 || c.x > vx1 || c.y < vy0 || c.y > vy1) return;
      if (!t.resources || !t.resources.length || t.water) return;
      if (t.resources.some(r => /berry|root|mushroom/.test(r))) {
        const sx = (c.x + 0.5 - origin.x) * s, sy = (c.y + 0.5 - origin.y) * s;
        g.fillStyle = "rgba(46, 213, 115, 0.9)";
        g.beginPath(); g.arc(sx, sy, Math.max(2.5, s * 0.15), 0, Math.PI * 2); g.fill();
        g.strokeStyle = "rgba(255, 255, 255, 0.8)";
        g.lineWidth = 1;
        g.stroke();
      }
    });
  }

  // Structures & Campfires
  for (const o of objectsAll) {
    const t = tiles.get(o.tile_id);
    if (!t || !t.coordinates) continue;
    const c = t.coordinates;
    if (c.x < vx0 || c.x > vx1 || c.y < vy0 || c.y > vy1) continue;
    const cat = objCategory(o.object_type);
    const sx = (c.x + 0.5 - origin.x) * s, sy = (c.y + 0.5 - origin.y) * s;

    if (cat === "fire") {
      // Warm Campfire Light Halo
      const fireGlow = g.createRadialGradient(sx, sy, 0, sx, sy, s * 1.6);
      fireGlow.addColorStop(0, "rgba(255, 140, 20, 0.48)");
      fireGlow.addColorStop(0.5, "rgba(255, 90, 10, 0.22)");
      fireGlow.addColorStop(1, "rgba(255, 60, 0, 0)");
      g.fillStyle = fireGlow;
      g.beginPath(); g.arc(sx, sy, s * 1.6, 0, Math.PI * 2); g.fill();

      if (sprites.campfire && sprites.campfire._ok) {
        const flamePulse = 1 + Math.sin(ts / 150) * 0.04;
        const fireW = Math.max(28, s * 0.95) * flamePulse;
        const fireH = fireW * (sprites.campfire.height / sprites.campfire.width);
        g.drawImage(sprites.campfire, sx - fireW / 2, sy - fireH * 0.65, fireW, fireH);
      }
    } else if (cat === "landmark") {
      if (sprites.landmark && sprites.landmark._ok) {
        const lmH = Math.max(36, s * 1.25);
        const lmW = lmH * (sprites.landmark.width / sprites.landmark.height);
        g.drawImage(sprites.landmark, sx - lmW / 2, sy - lmH * 0.72, lmW, lmH);
      }
    }
  }

  // Living Characters
  const tileAgentCounts = new Map();
  const tileAgentIndices = new Map();
  for (const a of agentsAll) {
    tileAgentCounts.set(a.tileId, (tileAgentCounts.get(a.tileId) || 0) + 1);
  }

  for (let i = 0; i < agentsAll.length; i++) {
    const a = agentsAll[i];
    const t = tiles.get(a.tileId);
    if (!t || !t.coordinates) continue;
    const c = t.coordinates;
    const baseSx = (c.x + 0.5 - origin.x) * s, baseSy = (c.y + 0.5 - origin.y) * s;

    const count = tileAgentCounts.get(a.tileId) || 1;
    const idx = tileAgentIndices.get(a.tileId) || 0;
    tileAgentIndices.set(a.tileId, idx + 1);

    const sep = count > 1 ? (idx - (count - 1) / 2) * Math.max(48, s * 0.9) : 0;
    drawCharacter(g, a, baseSx + sep, baseSy, s, ts, idx);
  }

  // Floating Action / Loot Texts
  for (let i = floatingTexts.length - 1; i >= 0; i--) {
    const ft = floatingTexts[i];
    const age = ts - ft.startTs;
    if (age > ft.dur) {
      floatingTexts.splice(i, 1);
      continue;
    }
    const p = age / ft.dur;
    const yOff = p * 35;
    g.save();
    g.font = "700 12px 'Plus Jakarta Sans', sans-serif";
    g.textAlign = "center";
    g.fillStyle = ft.col;
    g.globalAlpha = Math.sin(p * Math.PI);
    g.fillText(ft.text, ft.sx, ft.sy - yOff);
    g.restore();
  }

  document.getElementById("zoom-val").textContent = `${view.scale.toFixed(1)}×`;
}

function loop(ts) {
  if (isPlaying) {
    if (!lastStepTime) lastStepTime = ts;
    const interval = 1000 / playSpeed;
    if (ts - lastStepTime >= interval) {
      lastStepTime = ts;
      if (currentHb < maxHb) {
        currentHb++;
        playbackMode = "replay";
        recomputeScene();
        triggerActionFX();
      } else {
        isPlaying = false;
        updateUI();
      }
    }
  }
  drawFrame(ts);
  requestAnimationFrame(loop);
}

// Action FX Trigger on Heartbeat Step
function triggerActionFX() {
  const hbRec = (hbIndex[selectedPair] || new Map()).get(currentHb);
  if (!hbRec || !hbRec.actions) return;

  const pair = PAIRS[selectedPair] || {};
  const tl = pair.position_timeline || {};
  const pos = tl[currentHb] || pair.current_positions || {};

  for (const [ref, tid] of Object.entries(pos)) {
    const t = tiles.get(tid);
    if (!t || !t.coordinates) continue;
    const act = hbRec.actions[ref] || hbRec.actions[ref.replace(`${selectedPair}_`, "")];
    if (!act) continue;

    const c = t.coordinates;
    const origin = screenToWorld(0, 0);
    const sx = (c.x + 0.5 - origin.x) * view.scale;
    const sy = (c.y + 0.5 - origin.y) * view.scale - 30;

    const type = String(act.type || "").toLowerCase();
    if (type === "gather") {
      const res = act.resource ? act.resource.replace(/_/g, " ") : "wild flora";
      const icon = /berry/.test(res) ? "🫐" : (/wood/.test(res) ? "🪵" : "🪨");
      spawnFloatingText(`+${icon} ${res}`, sx, sy, "#2ed573");
    } else if (type === "eat") {
      spawnFloatingText(`🍖 Ate Rations (+HP)`, sx, sy, "#00d2d3");
    } else if (type === "build") {
      spawnFloatingText(`🔨 Built Campfire 🔥`, sx, sy, "#feca57");
    }
  }
}

// Cognitive Dossier Helper
function getAgentInnerVoice(pn, ref, v, act, inv) {
  const isAdam = ref.toLowerCase().includes("adam");
  const partner = isAdam ? "Eve" : "Adam";
  const pair = PAIRS[pn] || {};

  for (const ask of (pair.agent_asks || [])) {
    const askWho = String(ask.agent || "").toLowerCase();
    if (askWho.includes((isAdam ? "adam" : "eve")) && ask.status === "unheard") {
      return `"${ask.question}" — We wait for an answer from beyond the silence.`;
    }
  }
  if (v.downed) {
    return `Exhaustion overcame me... the ground is cold, but my breath is steadying. Gathering strength to stand beside ${partner}.`;
  }
  if (v.hunger >= 85) {
    return `Hunger is gnawing at my senses. I must search every shrub for wild berries before darkness settles.`;
  }
  if (act.kind === "eat") {
    return `Wild berries are reviving my blood. I must forage extra so ${partner} has rations as well.`;
  }
  return `Watching the horizon with ${partner}. Every path we walk together carves our home into this earth.`;
}

// Sidebar UI Renderers
function updateUI() {
  const hbs = timelineHbs[selectedPair] || [];
  if (hbs.length) {
    minHb = hbs[0];
    maxHb = hbs[hbs.length - 1];
  }

  // Masthead & Scrubber
  document.getElementById("hb-masthead").textContent = `HB ${currentHb || maxHb}`;
  const slider = document.getElementById("scrubber");
  if (slider) {
    slider.min = minHb;
    slider.max = maxHb;
    slider.value = currentHb || maxHb;
  }
  document.getElementById("pb-counter").textContent = `${currentHb || maxHb} / ${maxHb} HB`;

  const btnLive = document.getElementById("pb-live");
  if (playbackMode === "live") btnLive.classList.add("active");
  else btnLive.classList.remove("active");

  const btnPlay = document.getElementById("pb-play");
  btnPlay.textContent = isPlaying ? "⏸ PAUSE" : "▶ PLAY";

  renderBiometrics();
  renderChronicle();
  renderComms();
}

function renderBiometrics() {
  const el = document.getElementById("agents-container");
  const pair = PAIRS[selectedPair] || {};
  const inventories = pair.inventories || {};
  const vitalsAll = pair.vitals || {};
  const tl = pair.position_timeline || {};
  const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];

  let html = "";
  for (const [ref, tileId] of Object.entries(pos)) {
    const isAdam = ref.toLowerCase().includes("adam");
    const name = isAdam ? "ADAM" : "EVE";
    const v = vitalsAll[ref] || { hunger: 0, warmth: 80, vitality: 100, downed: false };
    const inv = inventories[ref] || {};
    const act = getAgentActivity(selectedPair, ref);
    const portraitSrc = isAdam ? "adam_portrait.jpg" : "eve_portrait.jpg";
    const st = v.downed ? "COLLAPSED" : "ACTIVE";

    const pills = Object.entries(inv).filter(([, c]) => c > 0).map(([k, c]) => `<span class="inv-pill">${k.replace(/_/g," ")} ×${c}</span>`);

    html += `<div class="agent-card ${isAdam ? 'adam' : 'eve'} ${v.downed ? 'collapsed' : ''}">
      <div class="agent-head">
        <div class="agent-profile">
          <img class="agent-portrait" src="${portraitSrc}" alt="${name}">
          <div class="agent-titles">
            <span class="agent-name">${name}</span>
            <span class="agent-sub">${selectedPair === "east" ? "East Valley" : "West Dawn"}</span>
          </div>
        </div>
        <span class="agent-state-badge ${v.downed ? 'collapsed' : 'active'}">${st}</span>
      </div>

      <div class="sector-row">
        <span>SECTOR: ${esc(tileId)}</span>
        <span class="sector-cta" onclick="focusTile('${esc(tileId)}')">PULSE ON MAP ↗</span>
      </div>

      <div class="telemetry-grid">
        <div class="metric-row">
          <div class="metric-meta"><span>HUNGER</span><span>${v.hunger.toFixed(0)}%</span></div>
          <div class="metric-bar-bg"><div class="metric-bar-fill hunger" style="width:${clamp(v.hunger, 0, 100)}%"></div></div>
        </div>
        <div class="metric-row">
          <div class="metric-meta"><span>VITAL</span><span>${v.vitality.toFixed(1)} HP</span></div>
          <div class="metric-bar-bg"><div class="metric-bar-fill vital" style="width:${clamp(v.vitality / 12 * 100, 0, 100)}%"></div></div>
        </div>
        <div class="metric-row">
          <div class="metric-meta"><span>WARMTH</span><span>${v.warmth.toFixed(0)}°C</span></div>
          <div class="metric-bar-bg"><div class="metric-bar-fill warmth" style="width:${clamp(v.warmth, 0, 100)}%"></div></div>
        </div>
        <div class="metric-row">
          <div class="metric-meta"><span>WETNESS</span><span>${(v.wetness || 0).toFixed(0)}%</span></div>
          <div class="metric-bar-bg"><div class="metric-bar-fill wetness" style="width:${clamp(v.wetness || 0, 0, 100)}%"></div></div>
        </div>
      </div>

      <div class="agent-inner-voice">
        <span style="font-style:normal;">🧠</span>
        <span>“${esc(getAgentInnerVoice(selectedPair, ref, v, act, inv))}”</span>
      </div>

      <div class="inventory-tray">
        ${pills.join("") || '<span style="font-size:0.68rem;color:var(--text-tertiary);">Pack is empty</span>'}
      </div>
    </div>`;
  }
  el.innerHTML = html;
}

function renderChronicle() {
  const el = document.getElementById("chronicle-container");
  const pair = PAIRS[selectedPair] || {};
  const events = (pair.chronicle || []).slice(-30).reverse();
  el.innerHTML = events.map(e => `
    <div class="chronicle-card">
      <span class="chronicle-hb">HB${e.hb}</span>
      <span class="chronicle-text"><strong class="chronicle-who">${(e.who||"").toUpperCase()}</strong> ${esc(e.text)}</span>
    </div>
  `).join("") || '<div style="color:var(--text-tertiary);text-align:center;padding:20px;">Chronicle is silent.</div>';
}

function renderComms() {
  const el = document.getElementById("comms-container");
  const pair = PAIRS[selectedPair] || {};
  const asks = (pair.agent_asks || []).slice(-20).reverse();
  el.innerHTML = asks.map(a => `
    <div class="transmission-card">
      <div class="tx-head">
        <span class="tx-sender">${(a.agent||"?").toUpperCase()}</span>
        <span style="color:var(--text-tertiary)">HB${a.heartbeat}</span>
      </div>
      <div class="tx-body">"${esc(a.question)}"</div>
      ${a.answer ? `<div style="margin-top:6px;color:#feca57;font-size:0.7rem;"><strong>DIRECTIVE:</strong> ${esc(a.answer)}</div>` : ''}
    </div>
  `).join("") || '<div style="color:var(--text-tertiary);text-align:center;padding:20px;">No comms recorded.</div>';
}

function esc(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function focusTile(tid) {
  const t = tiles.get(tid);
  if (t && t.coordinates) animateTo(t.coordinates.x + 0.5, t.coordinates.y + 0.5, 18);
}
window.focusTile = focusTile;

// Playback Transport Controls
function togglePlay() {
  isPlaying = !isPlaying;
  if (isPlaying && currentHb >= maxHb) currentHb = minHb;
  updateUI();
}
function step(delta) {
  isPlaying = false;
  playbackMode = "replay";
  currentHb = clamp(currentHb + delta, minHb, maxHb);
  recomputeScene();
  triggerActionFX();
  drawFrame(performance.now());
}
function seek(hb) {
  isPlaying = false;
  playbackMode = "replay";
  currentHb = clamp(hb, minHb, maxHb);
  recomputeScene();
  triggerActionFX();
  drawFrame(performance.now());
}
function goLive() {
  isPlaying = false;
  playbackMode = "live";
  currentHb = maxHb;
  recomputeScene();
  drawFrame(performance.now());
}

document.getElementById("pb-play").onclick = togglePlay;
document.getElementById("pb-start").onclick = () => seek(minHb);
document.getElementById("pb-prev").onclick = () => step(-1);
document.getElementById("pb-next").onclick = () => step(1);
document.getElementById("pb-live").onclick = goLive;
document.getElementById("scrubber").oninput = (e) => seek(Number(e.target.value));

document.querySelectorAll("#speed-cluster .speed-opt").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll("#speed-cluster .speed-opt").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    playSpeed = Number(btn.dataset.spd || 2);
  };
});

// Keyboard Shortcuts
window.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.code === "Space") { e.preventDefault(); togglePlay(); }
  else if (e.code === "ArrowLeft") { e.preventDefault(); step(-1); }
  else if (e.code === "ArrowRight") { e.preventDefault(); step(1); }
});

// Navigation Bar
document.getElementById("btn-east").onclick = () => {
  selectedPair = "east";
  document.getElementById("btn-east").classList.add("active");
  document.getElementById("btn-west").classList.remove("active");
  focusPair("east");
};
document.getElementById("btn-west").onclick = () => {
  selectedPair = "west";
  document.getElementById("btn-west").classList.add("active");
  document.getElementById("btn-east").classList.remove("active");
  focusPair("west");
};
document.getElementById("btn-fit").onclick = () => {
  animateTo(gcx, gcy, clamp(Math.min(cssW / (GW * 1.15), cssH / (GH * 1.15)), 1.2, 24));
};

function focusPair(pn) {
  const pair = PAIRS[pn];
  if (!pair) return;
  const hbs = timelineHbs[pn] || [];
  if (hbs.length) {
    minHb = hbs[0]; maxHb = hbs[hbs.length - 1];
    if (playbackMode === "live") currentHb = maxHb;
    else currentHb = clamp(currentHb, minHb, maxHb);
  }
  const pos = pair.current_positions || {};
  let ax = 0, ay = 0, n = 0;
  for (const tid of Object.values(pos)) {
    const t = tiles.get(tid);
    if (t && t.coordinates) { ax += t.coordinates.x; ay += t.coordinates.y; n++; }
  }
  if (n) animateTo(ax / n, ay / n, 16);
  recomputeScene();
}

// Tabs
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    const target = document.getElementById(btn.dataset.tab);
    if (target) target.classList.add("active");
  };
});

// Canvas Drag & Zoom
let dragging = false, lastMouse = { x: 0, y: 0 };
canvas.addEventListener("mousedown", e => {
  if (e.button !== 0) return;
  dragging = true;
  lastMouse = { x: e.clientX, y: e.clientY };
  canvas.classList.add("dragging");
});
window.addEventListener("mousemove", e => {
  if (!dragging) return;
  const dx = e.clientX - lastMouse.x, dy = e.clientY - lastMouse.y;
  lastMouse = { x: e.clientX, y: e.clientY };
  view.cx -= dx / view.scale;
  view.cy -= dy / view.scale;
  drawFrame(performance.now());
});
window.addEventListener("mouseup", () => {
  dragging = false;
  canvas.classList.remove("dragging");
});
canvas.addEventListener("wheel", e => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  const sx = e.clientX - r.left, sy = e.clientY - r.top;
  const worldBefore = screenToWorld(sx, sy);
  const factor = Math.exp(-e.deltaY * 0.0018);
  view.scale = clamp(view.scale * factor, 1.2, 38);
  const worldAfter = screenToWorld(sx, sy);
  view.cx += worldBefore.x - worldAfter.x;
  view.cy += worldBefore.y - worldAfter.y;
  drawFrame(performance.now());
}, { passive: false });

// Start App
focusPair("west");
ensureLayer();
recomputeScene();
drawFrame(0);
requestAnimationFrame(loop);

})();
</script>
</body>
</html>
"""

HTML_FILE.write_text(HTML_CONTENT, encoding="utf-8", newline="\n")
print("SUCCESS: Pristine index.html written with LF line endings.")
