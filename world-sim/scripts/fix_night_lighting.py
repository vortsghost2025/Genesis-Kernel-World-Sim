from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# Replace the direct destination-out on main canvas with an offscreen darkness mask
old_lighting_pass = """  if (atmo.ambientDarkness > 0) {
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
  }"""

new_lighting_pass = """  if (atmo.ambientDarkness > 0) {
    // Render darkness on offscreen mask so destination-out doesn't erase terrain underneath
    if (!window._atmoMask || window._atmoMask.width !== canvas.width || window._atmoMask.height !== canvas.height) {
      window._atmoMask = document.createElement("canvas");
      window._atmoMask.width = canvas.width;
      window._atmoMask.height = canvas.height;
    }
    const mg = window._atmoMask.getContext("2d");
    mg.setTransform(dpr, 0, 0, dpr, 0, 0);
    mg.clearRect(0, 0, cssW, cssH);

    // Fill darkness
    mg.fillStyle = `rgba(4, 10, 24, ${atmo.ambientDarkness.toFixed(3)})`;
    mg.fillRect(0, 0, cssW, cssH);

    // Carve light holes for campfires, landmarks, and agents
    mg.globalCompositeOperation = "destination-out";

    // Hearth fires & monuments
    for (const o of objectsAll) {
      const t = tiles.get(o.tile_id);
      if (!t || !t.coordinates) continue;
      const c = t.coordinates;
      const sx = (c.x + 0.5 - origin.x) * s, sy = (c.y + 0.5 - origin.y) * s;
      const cat = objCategory(o.object_type);
      if (cat === "fire" || cat === "landmark") {
        const fireRad = mg.createRadialGradient(sx, sy, 0, sx, sy, s * 3.2);
        fireRad.addColorStop(0, "rgba(0, 0, 0, 1)");
        fireRad.addColorStop(0.5, "rgba(0, 0, 0, 0.8)");
        fireRad.addColorStop(1, "rgba(0, 0, 0, 0)");
        mg.fillStyle = fireRad;
        mg.beginPath();
        mg.arc(sx, sy, s * 3.2, 0, Math.PI * 2);
        mg.fill();
      }
    }

    // Agents carry a soft lantern glow at night
    for (const a of agentsAll) {
      const anim = getAgentWorldPos(a.pair, a.ref, currentHb, 1);
      const asx = (anim.x + 0.5 - origin.x) * s;
      const asy = (anim.y + 0.5 - origin.y) * s;
      const agentRad = mg.createRadialGradient(asx, asy, 0, asx, asy, s * 2.2);
      agentRad.addColorStop(0, "rgba(0, 0, 0, 1)");
      agentRad.addColorStop(0.6, "rgba(0, 0, 0, 0.6)");
      agentRad.addColorStop(1, "rgba(0, 0, 0, 0)");
      mg.fillStyle = agentRad;
      mg.beginPath();
      mg.arc(asx, asy, s * 2.2, 0, Math.PI * 2);
      mg.fill();
    }

    // Blend the darkness mask over the terrain
    g.save();
    g.drawImage(window._atmoMask, 0, 0, cssW, cssH);
    g.restore();
  }"""

assert old_lighting_pass in text, "old_lighting_pass not found"
text = text.replace(old_lighting_pass, new_lighting_pass, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

print("Offscreen darkness mask applied successfully.")
