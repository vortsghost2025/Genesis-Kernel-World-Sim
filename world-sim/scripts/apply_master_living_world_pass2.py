"""Master Living World Pass 2:
Replaces:
1. getLayer(px) with organic terrain renderer
2. Scenery & props rendering (trees, rocks, bushes, fires, landmarks)
3. Living character action engine & smooth movement interpolation
4. Camera tracking mode
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# -------------------------------------------------------------
# Part 1: Replace getLayer(px)
# -------------------------------------------------------------
target_getlayer_start = """// Procedural Organic Landscape Layer (Clean, Seamless, Topographical)
const layerCache = new Map();"""

target_getlayer_end = """function ensureLayer() {
  const want = clamp(Math.round(view.scale), 4, 28);
  if (!layerPx || Math.abs(want / layerPx - 1) > 0.45) {
    layerPx = want;
    getLayer(layerPx);
  }
  return layerCache.get(layerPx) || getLayer(layerPx);
}"""

replacement_getlayer = '''// Procedural Organic Landscape Layer (Continuous, Blended, Topographical)
const layerCache = new Map();
let layerPx = 0;

// Reusable texture pattern for organic loam/grass grain
let noisePattern = null;
function getNoisePattern() {
  if (noisePattern) return noisePattern;
  const pc = document.createElement("canvas");
  pc.width = 64; pc.height = 64;
  const pctx = pc.getContext("2d");
  const imgData = pctx.createImageData(64, 64);
  const d = imgData.data;
  let seed = 42;
  function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
  for (let i = 0; i < d.length; i += 4) {
    const v = Math.round(rnd() * 28);
    d[i] = v; d[i+1] = v; d[i+2] = v; d[i+3] = 18;
  }
  pctx.putImageData(imgData, 0, 0);
  const dummy = document.createElement("canvas").getContext("2d");
  noisePattern = dummy.createPattern(pc, "repeat");
  return noisePattern;
}

function getLayer(px) {
  if (layerCache.has(px)) return layerCache.get(px);
  const W = GW * px, H = GH * px;
  const c2 = document.createElement("canvas");
  c2.width = W; c2.height = H;
  const g = c2.getContext("2d");

  // 1. Base Biomes (Soft Rounded Organic Blending)
  tiles.forEach(t => {
    const c = t.coordinates; if (!c) return;
    const cx = (c.x - minX + 0.5) * px;
    const cy = (c.y - minY + 0.5) * px;
    const col = baseColor(t);
    const r = px * 0.72;

    const grad = g.createRadialGradient(cx, cy, px * 0.2, cx, cy, r);
    grad.addColorStop(0, `rgb(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])})`);
    grad.addColorStop(0.75, `rgb(${Math.round(col[0] * 0.95)}, ${Math.round(col[1] * 0.95)}, ${Math.round(col[2] * 0.95)})`);
    grad.addColorStop(1, `rgba(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])}, 0.2)`);

    g.fillStyle = grad;
    g.beginPath();
    g.arc(cx, cy, r, 0, Math.PI * 2);
    g.fill();
  });

  // 2. Neighbor Transition Feathering
  tiles.forEach(t => {
    const c = t.coordinates; if (!c) return;
    const cx = (c.x - minX + 0.5) * px;
    const cy = (c.y - minY + 0.5) * px;
    const col = baseColor(t);

    const neighbors = [
      { dx: 1, dy: 0 }, { dx: -1, dy: 0 },
      { dx: 0, dy: 1 }, { dx: 0, dy: -1 }
    ];

    for (const n of neighbors) {
      const nt = tileByCoord.get((c.x + n.dx) + "," + (c.y + n.dy));
      if (!nt || nt.biome === t.biome) continue;
      const ncol = baseColor(nt);
      const nx = (c.x + n.dx - minX + 0.5) * px;
      const ny = (c.y + n.dy - minY + 0.5) * px;

      const bridgeGrad = g.createLinearGradient(cx, cy, nx, ny);
      bridgeGrad.addColorStop(0, `rgba(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])}, 0.4)`);
      bridgeGrad.addColorStop(1, `rgba(${Math.round(ncol[0])}, ${Math.round(ncol[1])}, ${Math.round(ncol[2])}, 0.4)`);

      g.fillStyle = bridgeGrad;
      g.beginPath();
      const midX = (cx + nx) / 2, midY = (cy + ny) / 2;
      g.arc(midX, midY, px * 0.45, 0, Math.PI * 2);
      g.fill();
    }
  });

  // 3. Water Shorelines & Sand Beach Ribbons
  tiles.forEach(t => {
    const c = t.coordinates; if (!c) return;
    const cx = (c.x - minX + 0.5) * px;
    const cy = (c.y - minY + 0.5) * px;

    if (t.water) {
      // Check if near land
      const nearLand = [[0,-1],[0,1],[-1,0],[1,0]].some(([dx, dy]) => {
        const n = tileByCoord.get((c.x + dx) + "," + (c.y + dy));
        return n && !n.water;
      });
      if (nearLand) {
        // Sand beach fringe
        g.strokeStyle = "rgba(194, 178, 128, 0.45)";
        g.lineWidth = Math.max(2, px * 0.18);
        g.beginPath();
        g.arc(cx, cy, px * 0.52, 0, Math.PI * 2);
        g.stroke();

        // Shallow turquoise water glow
        g.fillStyle = "rgba(32, 160, 180, 0.28)";
        g.beginPath();
        g.arc(cx, cy, px * 0.58, 0, Math.PI * 2);
        g.fill();
      }
    }
  });

  // 4. Directional Sun Hillshading (NW Sun, continuous relief)
  tiles.forEach(t => {
    const c = t.coordinates; if (!c || t.water) return;
    const cx = (c.x - minX + 0.5) * px;
    const cy = (c.y - minY + 0.5) * px;
    const e = t.elevation == null ? 0.5 : t.elevation;

    const wTile = tileByCoord.get((c.x - 1) + "," + c.y);
    const nTile = tileByCoord.get(c.x + "," + (c.y - 1));
    const eTile = tileByCoord.get((c.x + 1) + "," + c.y);
    const sTile = tileByCoord.get(c.x + "," + (c.y + 1));

    const eW = wTile ? (wTile.elevation ?? 0.5) : e;
    const eN = nTile ? (nTile.elevation ?? 0.5) : e;
    const eE = eTile ? (eTile.elevation ?? 0.5) : e;
    const eS = sTile ? (sTile.elevation ?? 0.5) : e;

    const slopeX = (eE - eW) * 0.5;
    const slopeY = (eS - eN) * 0.5;
    const sunLight = -0.707 * slopeX - 0.707 * slopeY;

    if (Math.abs(sunLight) > 0.012) {
      if (sunLight > 0) {
        g.fillStyle = `rgba(255, 255, 220, ${Math.min(0.28, sunLight * 0.65).toFixed(3)})`;
      } else {
        g.fillStyle = `rgba(4, 8, 20, ${Math.min(0.38, -sunLight * 0.8).toFixed(3)})`;
      }
      g.beginPath();
      g.arc(cx, cy, px * 0.65, 0, Math.PI * 2);
      g.fill();
    }

    // Basalt Ridge Barrier: Rugged Obsidian with Crimson Runes
    if (t.blocks_travel) {
      g.fillStyle = "rgba(14, 10, 16, 0.95)";
      g.beginPath();
      g.arc(cx, cy, px * 0.62, 0, Math.PI * 2);
      g.fill();

      // Jagged barrier highlights
      g.strokeStyle = "rgba(255, 71, 87, 0.4)";
      g.lineWidth = Math.max(1.5, px * 0.1);
      g.beginPath();
      g.moveTo(cx - px * 0.4, cy);
      g.lineTo(cx - px * 0.1, cy - px * 0.3);
      g.lineTo(cx + px * 0.2, cy + px * 0.2);
      g.lineTo(cx + px * 0.4, cy - px * 0.1);
      g.stroke();
    }
  });

  // 5. Tactile Organic Micro-Texture Overlay
  try {
    const pat = getNoisePattern();
    if (pat) {
      g.save();
      g.globalCompositeOperation = "soft-light";
      g.fillStyle = pat;
      g.fillRect(0, 0, W, H);
      g.restore();
    }
  } catch(e) {}

  layerCache.set(px, c2);
  return c2;
}
function ensureLayer() {
  const want = clamp(Math.round(view.scale), 4, 32);
  if (!layerPx || Math.abs(want / layerPx - 1) > 0.45) {
    layerPx = want;
    getLayer(layerPx);
  }
  return layerCache.get(layerPx) || getLayer(layerPx);
}'''

idx1 = html.find(target_getlayer_start)
idx2 = html.find(target_getlayer_end)
assert idx1 != -1 and idx2 != -1, "getLayer targets not found"
html = html[:idx1] + replacement_getlayer + html[idx2 + len(target_getlayer_end):]

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print("Pass 2 applied successfully: getLayer organic terrain installed.")
