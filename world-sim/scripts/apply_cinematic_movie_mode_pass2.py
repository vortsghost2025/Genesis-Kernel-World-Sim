"""Pass 4 Part 2: JavaScript logic for Trails, Day/Night Atmosphere, Movie Mode Director, and Web Audio.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# -------------------------------------------------------------------------
# 1. Add Traversal Trail Cache right after populateTiles()
# -------------------------------------------------------------------------
target_after_populate = """populateTiles();"""
trails_code = """populateTiles();

// Foot-Traffic Traversal Trail Cache (Desire Paths etched from 4,000 heartbeats)
const pairTrails = { east: new Map(), west: new Map() };
function computeTrails() {
  for (const [pn, pair] of Object.entries(PAIRS)) {
    const tl = pair.position_timeline || {};
    const trailMap = new Map();
    const hbs = Object.keys(tl).map(Number).sort((a,b) => a - b);
    const prevPos = {};

    for (const hb of hbs) {
      const pos = tl[hb] || {};
      for (const [ref, tid] of Object.entries(pos)) {
        if (prevPos[ref] && prevPos[ref] !== tid) {
          const edgeKey = [prevPos[ref], tid].sort().join("---");
          trailMap.set(edgeKey, (trailMap.get(edgeKey) || 0) + 1);
        }
        prevPos[ref] = tid;
      }
    }
    pairTrails[pn] = trailMap;
  }
}
computeTrails();

// Draw authentic worn dirt paths on terrain
function drawWornTrails(g, pn, origin, s) {
  const trailMap = pairTrails[pn] || new Map();
  if (!trailMap.size) return;

  g.save();
  for (const [edgeKey, count] of trailMap.entries()) {
    if (count < 2) continue; // Only draw paths walked multiple times
    const [t1Id, t2Id] = edgeKey.split("---");
    const t1 = tiles.get(t1Id);
    const t2 = tiles.get(t2Id);
    if (!t1 || !t2 || !t1.coordinates || !t2.coordinates) continue;

    const sx1 = (t1.coordinates.x + 0.5 - origin.x) * s;
    const sy1 = (t1.coordinates.y + 0.5 - origin.y) * s;
    const sx2 = (t2.coordinates.x + 0.5 - origin.x) * s;
    const sy2 = (t2.coordinates.y + 0.5 - origin.y) * s;

    // Trail weight and opacity based on foot traffic
    const traffic = Math.min(1.0, count / 15);
    const trailWidth = Math.max(1.5, (2.2 + traffic * 4.5) * (s / 16));

    // Outer worn earth border
    g.strokeStyle = `rgba(62, 46, 32, ${(0.3 + traffic * 0.45).toFixed(3)})`;
    g.lineWidth = trailWidth;
    g.lineCap = "round";
    g.beginPath();
    g.moveTo(sx1, sy1);
    g.lineTo(sx2, sy2);
    g.stroke();

    // Inner packed soil core
    g.strokeStyle = `rgba(138, 108, 76, ${(0.4 + traffic * 0.5).toFixed(3)})`;
    g.lineWidth = trailWidth * 0.55;
    g.beginPath();
    g.moveTo(sx1, sy1);
    g.lineTo(sx2, sy2);
    g.stroke();
  }
  g.restore();
}

// Day/Night & Atmospheric Shading
function getAtmosphericLighting(hb) {
  // Cycle repeats every 120 heartbeats
  const phase = (hb % 120) / 120;
  let timeName = "Midday";
  let sunColor = "rgba(255, 255, 230, 0)";
  let ambientDarkness = 0;
  let isNight = false;

  if (phase < 0.20) {
    timeName = "Dawn 🌄";
    sunColor = "rgba(255, 180, 120, 0.12)";
    ambientDarkness = 0.15 * (1 - phase / 0.20);
  } else if (phase < 0.65) {
    timeName = "Midday ☀️";
    sunColor = "rgba(255, 255, 240, 0.05)";
    ambientDarkness = 0;
  } else if (phase < 0.85) {
    const pDusk = (phase - 0.65) / 0.20;
    timeName = "Dusk 🌅";
    sunColor = `rgba(255, 120, 60, ${0.18 * Math.sin(pDusk * Math.PI)})`;
    ambientDarkness = pDusk * 0.48;
  } else {
    timeName = "Night 🌙";
    sunColor = "rgba(20, 35, 75, 0.35)";
    ambientDarkness = 0.58;
    isNight = true;
  }
  return { phase, timeName, sunColor, ambientDarkness, isNight };
}

// Procedural Living Audio Ambience (Web Audio API)
let audioCtx = null;
let isAudioActive = false;
let windGain = null, droneGain = null;

function initAudio() {
  if (audioCtx) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();

    // 1. Procedural Wind
    const bufSize = audioCtx.sampleRate * 2;
    const noiseBuf = audioCtx.createBuffer(1, bufSize, audioCtx.sampleRate);
    const out = noiseBuf.getChannelData(0);
    let lastOut = 0.0;
    for (let i = 0; i < bufSize; i++) {
      const white = Math.random() * 2 - 1;
      out[i] = (lastOut + (0.02 * white)) / 1.02;
      lastOut = out[i];
      out[i] *= 3.5;
    }
    const noiseNode = audioCtx.createBufferSource();
    noiseNode.buffer = noiseBuf;
    noiseNode.loop = true;

    const windFilter = audioCtx.createBiquadFilter();
    windFilter.type = "lowpass";
    windFilter.frequency.value = 340;

    windGain = audioCtx.createGain();
    windGain.gain.value = 0.06;

    noiseNode.connect(windFilter);
    windFilter.connect(windGain);
    windGain.connect(audioCtx.destination);
    noiseNode.start();

    // 2. Procedural Ethereal Contemplative Drone
    const freqs = [130.81, 155.56, 196.00];
    droneGain = audioCtx.createGain();
    droneGain.gain.value = 0.035;

    freqs.forEach(f => {
      const osc = audioCtx.createOscillator();
      osc.type = "sine";
      osc.frequency.value = f;
      osc.connect(droneGain);
      osc.start();
    });
    droneGain.connect(audioCtx.destination);
  } catch(e) {
    console.warn("Web Audio not supported:", e);
  }
}

function toggleAudio() {
  if (!audioCtx) initAudio();
  if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
  isAudioActive = !isAudioActive;
  if (windGain && audioCtx) windGain.gain.setTargetAtTime(isAudioActive ? 0.06 : 0, audioCtx.currentTime, 0.3);
  if (droneGain && audioCtx) droneGain.gain.setTargetAtTime(isAudioActive ? 0.035 : 0, audioCtx.currentTime, 0.3);
  const btn = document.getElementById("btn-audio");
  if (btn) {
    if (isAudioActive) {
      btn.classList.add("active");
      btn.textContent = "🔊 Ambience ON";
    } else {
      btn.classList.remove("active");
      btn.textContent = "🔈 Ambience OFF";
    }
  }
}
window.toggleAudio = toggleAudio;

// Cinematic Director Mode
let isCinematic = false;
function toggleCinematic() {
  isCinematic = !isCinematic;
  const overlay = document.getElementById("cinema-overlay");
  const sidebar = document.getElementById("sidebar");
  const pbBar = document.getElementById("playback-bar");
  const btn = document.getElementById("btn-cinema");

  if (isCinematic) {
    overlay.style.display = "flex";
    sidebar.style.display = "none";
    pbBar.style.bottom = "92px";
    if (btn) btn.classList.add("active");
    if (!isPlaying) togglePlay();
  } else {
    overlay.style.display = "none";
    sidebar.style.display = "flex";
    pbBar.style.bottom = "16px";
    if (btn) btn.classList.remove("active");
  }
  resize();
}
window.toggleCinematic = toggleCinematic;"""

assert target_after_populate in html, "target_after_populate not found"
html = html.replace(target_after_populate, trails_code, 1)

# -------------------------------------------------------------------------
# 2. Hook trails & lighting into drawFrame(ts)
# -------------------------------------------------------------------------
old_terrain_draw = """  // Continuous Organic Terrain Layer
  g.imageSmoothingEnabled = true;
  g.drawImage(terrain, -dx, -dy, dw, dh);"""

new_terrain_draw = """  // Continuous Organic Terrain Layer
  g.imageSmoothingEnabled = true;
  g.drawImage(terrain, -dx, -dy, dw, dh);

  // Worn Footstep Trails (Desire paths etched from 4,000 heartbeats)
  drawWornTrails(g, selectedPair, origin, s);"""

assert old_terrain_draw in html, "old_terrain_draw not found"
html = html.replace(old_terrain_draw, new_terrain_draw, 1)

# Add Day/Night Lighting pass before character drawing
old_char_loop_start = """  // Living Characters with Movement Interpolation"""
lighting_code = """  // Atmospheric Sun & Day/Night Wash
  const atmo = getAtmosphericLighting(currentHb);
  const timeHud = document.getElementById("time-hud");
  if (timeHud) timeHud.textContent = atmo.timeName;

  if (atmo.ambientDarkness > 0) {
    g.save();
    g.fillStyle = `rgba(4, 10, 24, ${atmo.ambientDarkness.toFixed(3)})`;
    g.fillRect(0, 0, cssW, cssH);

    // Campfire & Landmark Light Holes through Darkness
    g.globalCompositeOperation = "destination-out";
    for (const o of objectsAll) {
      const t = tiles.get(o.tile_id);
      if (!t || !t.coordinates) continue;
      const c = t.coordinates;
      const sx = (c.x + 0.5 - origin.x) * s, sy = (c.y + 0.5 - origin.y) * s;
      const cat = objCategory(o.object_type);
      if (cat === "fire" || cat === "landmark") {
        const fireRad = g.createRadialGradient(sx, sy, 0, sx, sy, s * 2.8);
        fireRad.addColorStop(0, "rgba(0, 0, 0, 1)");
        fireRad.addColorStop(0.6, "rgba(0, 0, 0, 0.7)");
        fireRad.addColorStop(1, "rgba(0, 0, 0, 0)");
        g.fillStyle = fireRad;
        g.beginPath();
        g.arc(sx, sy, s * 2.8, 0, Math.PI * 2);
        g.fill();
      }
    }
    g.restore();
  }

  // Cinematic Director Camera Glide & Subtitle Feed
  if (isCinematic) {
    let avgX = 0, avgY = 0, charCount = 0;
    let mainQuote = "";
    for (const a of agentsAll) {
      const anim = getAgentWorldPos(a.pair, a.ref, currentHb, 1);
      avgX += anim.x + 0.5; avgY += anim.y + 0.5; charCount++;
      const act = getAgentRealAction(a.pair, a.ref, currentHb);
      if (!mainQuote && (act.fullReason || act.label)) {
        const who = a.ref.toUpperCase().replace(/.*_/, "");
        mainQuote = `${who}: "${act.fullReason || act.label}"`;
      }
    }
    if (charCount > 0) {
      view.cx += (avgX / charCount - view.cx) * 0.04;
      view.cy += (avgY / charCount - view.cy) * 0.04;
      view.scale += (19.0 - view.scale) * 0.02;
    }
    const subEl = document.getElementById("cinema-subtitle");
    if (subEl && mainQuote) subEl.textContent = mainQuote;
    const hbTag = document.getElementById("cinema-hb-tag");
    if (hbTag) hbTag.textContent = `HB ${currentHb} // ${atmo.timeName}`;
  }

  // Living Characters with Movement Interpolation"""

assert old_char_loop_start in html, "old_char_loop_start not found"
html = html.replace(old_char_loop_start, lighting_code, 1)

# -------------------------------------------------------------------------
# 3. Add event listeners for btn-cinema and btn-audio
# -------------------------------------------------------------------------
old_nav_listeners = """document.getElementById("btn-fit").onclick = () => {
  animateTo(gcx, gcy, clamp(Math.min(cssW / (GW * 1.15), cssH / (GH * 1.15)), 1.2, 24));
};"""

new_nav_listeners = """document.getElementById("btn-fit").onclick = () => {
  animateTo(gcx, gcy, clamp(Math.min(cssW / (GW * 1.15), cssH / (GH * 1.15)), 1.2, 24));
};
document.getElementById("btn-cinema").onclick = toggleCinematic;
document.getElementById("btn-audio").onclick = toggleAudio;"""

assert old_nav_listeners in html, "old_nav_listeners not found"
html = html.replace(old_nav_listeners, new_nav_listeners, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print("Pass 4 Part 2 applied successfully: Trails, Atmosphere, Cinema Mode & Web Audio installed.")
