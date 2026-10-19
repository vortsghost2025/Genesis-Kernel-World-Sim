import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update sprites definition in index.html to include new environmental assets
sprites_old = """const sprites = {
  adam_standing: new Image(),
  eve_standing: new Image(),
  adam_collapsed: new Image(),
  eve_collapsed: new Image(),
  campfire: new Image(),
  landmark: new Image()
};"""

sprites_new = """const sprites = {
  adam_standing: new Image(),
  eve_standing: new Image(),
  adam_collapsed: new Image(),
  eve_collapsed: new Image(),
  campfire: new Image(),
  landmark: new Image(),
  tree_cluster: new Image(),
  boulder_rock: new Image(),
  berry_bush: new Image()
};"""

assert sprites_old in html, "sprites_old not found in index.html"
html = html.replace(sprites_old, sprites_new, 1)

# 2. Add tracking button styles and zoom tag tracking indicator to CSS
css_target = """/* Action Playback Bar (Clean, Minimal, Docked at Bottom of Map) */"""
css_addition = """/* Camera Tracking & HUD Tags */
.btn-track {
  background: rgba(0, 210, 211, 0.12);
  border: 1px solid rgba(0, 210, 211, 0.35);
  color: #00d2d3;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.btn-track:hover {
  background: rgba(0, 210, 211, 0.25);
  color: #fff;
  border-color: rgba(0, 210, 211, 0.6);
}
.btn-track.active {
  background: rgba(254, 202, 87, 0.25);
  border-color: rgba(254, 202, 87, 0.8);
  color: #feca57;
  box-shadow: 0 0 10px rgba(254, 202, 87, 0.4);
}
#track-indicator {
  display: none;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--gold-amber);
  background: rgba(254, 202, 87, 0.15);
  border: 1px solid rgba(254, 202, 87, 0.4);
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
  letter-spacing: 0.04em;
}

"""
assert css_target in html, "css_target not found"
html = html.replace(css_target, css_addition + css_target, 1)

# 3. Add track indicator span to zoom-tag
zoom_old = """<div id="zoom-tag">ZOOM <span id="zoom-val">15.0×</span> · DRAG · SCROLL</div>"""
zoom_new = """<div id="zoom-tag">ZOOM <span id="zoom-val">15.0×</span> · DRAG · SCROLL <span id="track-indicator">🎥 TRACKING AGENT</span></div>"""
assert zoom_old in html, "zoom_old not found"
html = html.replace(zoom_old, zoom_new, 1)

# Write intermediate check
with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print("Pass 1 applied successfully: Sprites & CSS updated.")
