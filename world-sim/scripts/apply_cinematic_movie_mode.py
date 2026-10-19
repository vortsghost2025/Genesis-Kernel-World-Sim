"""Pass 4: Cinematic Director Mode, Worn Desire Paths, Day/Night Atmosphere, and Native Audio Ambience.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# -------------------------------------------------------------------------
# 1. Add Cinema Overlay & Controls to HTML
# -------------------------------------------------------------------------
old_nav_cluster = """      <div class="nav-cluster">
        <div class="nav-pill active" id="btn-east"><span class="civ-dot east"></span>East Valley</div>
        <div class="nav-pill" id="btn-west"><span class="civ-dot west"></span>West Dawn</div>
        <div class="nav-pill" id="btn-fit">⛶ Orbit</div>
      </div>"""

new_nav_cluster = """      <div class="nav-cluster">
        <div class="nav-pill active" id="btn-east"><span class="civ-dot east"></span>East Valley</div>
        <div class="nav-pill" id="btn-west"><span class="civ-dot west"></span>West Dawn</div>
        <div class="nav-pill" id="btn-fit">⛶ Orbit</div>
        <div class="nav-pill" id="btn-cinema" title="Toggle Cinematic Movie Mode">🎬 Movie Mode</div>
        <div class="nav-pill" id="btn-audio" title="Toggle Ambient Wind & Hearth Audio">🔈 Ambience</div>
      </div>"""

assert old_nav_cluster in html, "old_nav_cluster not found"
html = html.replace(old_nav_cluster, new_nav_cluster, 1)

# Add time of day HUD chip to telemetry cluster
old_telemetry = """    <div class="telemetry-cluster">
      <div class="weather-hud" id="weather-hud"></div>
      <div class="status-badge-live">STREAM LIVE</div>
      <div class="hb-counter-masthead" id="hb-masthead">HB 0</div>
    </div>"""

new_telemetry = """    <div class="telemetry-cluster">
      <div class="weather-hud" id="weather-hud"></div>
      <div class="w-chip" id="time-hud" style="color:var(--gold-amber);font-weight:700;">☀️ MIDDAY</div>
      <div class="status-badge-live">STREAM LIVE</div>
      <div class="hb-counter-masthead" id="hb-masthead">HB 0</div>
    </div>"""

assert old_telemetry in html, "old_telemetry not found"
html = html.replace(old_telemetry, new_telemetry, 1)

# Add cinema overlay inside #map-panel
old_map_panel_start = """    <!-- Map Canvas Panel -->
    <div id="map-panel">
      <canvas id="map-canvas"></canvas>"""

new_map_panel_start = """    <!-- Map Canvas Panel -->
    <div id="map-panel">
      <canvas id="map-canvas"></canvas>

      <!-- Cinematic Letterbox & Subtitle Deck -->
      <div id="cinema-overlay" style="display:none;">
        <div class="cinema-bar top">
          <div class="cinema-top-info">
            <span class="cinema-title">GENESIS // CONTINENT ARCHIVES</span>
            <span class="cinema-hb" id="cinema-hb-tag">HB 0</span>
          </div>
        </div>
        <div class="cinema-bar bottom">
          <div id="cinema-subtitle">“We wait for an answer from beyond the silence.”</div>
        </div>
      </div>"""

assert old_map_panel_start in html, "old_map_panel_start not found"
html = html.replace(old_map_panel_start, new_map_panel_start, 1)

# -------------------------------------------------------------------------
# 2. Add CSS for Cinema Mode & Atmosphere
# -------------------------------------------------------------------------
css_target = """/* Action Playback Bar (Clean, Minimal, Docked at Bottom of Map) */"""
cinema_css = """/* Cinematic Director Mode & Letterbox */
#cinema-overlay {
  position: absolute;
  inset: 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  pointer-events: none;
}
.cinema-bar {
  background: #000;
  width: 100%;
  pointer-events: auto;
}
.cinema-bar.top {
  height: 64px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.95);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
}
.cinema-top-info {
  display: flex;
  align-items: center;
  gap: 16px;
}
.cinema-title {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.22em;
  color: #fff;
}
.cinema-hb {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  color: var(--east-cyan);
  background: rgba(0, 210, 211, 0.15);
  padding: 2px 10px;
  border-radius: 12px;
  border: 1px solid rgba(0, 210, 211, 0.4);
}
.cinema-bar.bottom {
  min-height: 86px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px 36px;
  box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.95);
}
#cinema-subtitle {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 500;
  line-height: 1.5;
  letter-spacing: 0.04em;
  color: #fff;
  text-align: center;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.9);
  max-width: 980px;
  transition: opacity 0.3s ease;
}

"""
assert css_target in html, "css_target not found"
html = html.replace(css_target, cinema_css + css_target, 1)

# Write intermediate
with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print("Pass 4 HTML and CSS applied.")
