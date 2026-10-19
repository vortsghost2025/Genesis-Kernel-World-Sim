from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Truncate comic speech bubble on map to be compact and elegant
old_bubble = """  let bubbleText = act.label;
  let bubbleIcon = "🌿";"""

new_bubble = """  let rawLabel = act.label;
  if (rawLabel.length > 28) rawLabel = rawLabel.slice(0, 25) + "...";
  let bubbleText = rawLabel;
  let bubbleIcon = "🌿";"""

assert old_bubble in text, "old_bubble not found"
text = text.replace(old_bubble, new_bubble, 1)

# 2. Scenery density: naturally distributed (scattered), not on every single tile!
old_scenery = """      // Forest & Woodland Biomes: Rich Tree Groves
      if (b.includes("forest") || b.includes("woodland") || b.includes("thicket")) {
        if (sprites.tree_cluster && sprites.tree_cluster._ok) {"""

new_scenery = """      // Forest & Woodland Biomes: Rich Tree Groves (natural 40% canopy density)
      if ((b.includes("forest") || b.includes("woodland") || b.includes("thicket")) && (seed % 100 < 42)) {
        if (sprites.tree_cluster && sprites.tree_cluster._ok) {"""

assert old_scenery in text, "old_scenery not found"
text = text.replace(old_scenery, new_scenery, 1)

old_rocks = """      // Rocky / Highland Biomes: Weathered Granite Boulders
      else if (b.includes("hill") || b.includes("highland") || b.includes("cliff")) {
        if (sprites.boulder_rock && sprites.boulder_rock._ok) {"""

new_rocks = """      // Rocky / Highland Biomes: Weathered Granite Boulders (natural 28% outcropping density)
      else if ((b.includes("hill") || b.includes("highland") || b.includes("cliff")) && (seed % 100 < 30)) {
        if (sprites.boulder_rock && sprites.boulder_rock._ok) {"""

assert old_rocks in text, "old_rocks not found"
text = text.replace(old_rocks, new_rocks, 1)

old_bushes = """      // Sustenance Flora: Wild Berry Bushes
      if (t.resources && t.resources.some(r => /berry|root|mushroom/.test(r))) {
        if (sprites.berry_bush && sprites.berry_bush._ok) {"""

new_bushes = """      // Sustenance Flora: Wild Berry Bushes (natural 35% shrub density)
      if (t.resources && t.resources.some(r => /berry|root|mushroom/.test(r)) && (seed % 100 < 38)) {
        if (sprites.berry_bush && sprites.berry_bush._ok) {"""

assert old_bushes in text, "old_bushes not found"
text = text.replace(old_bushes, new_bushes, 1)

# 3. Soft seamless water & land polygons in getLayer(px)
# Make land and water fill a seamless cohesive grid with rounded edge bevels instead of isolated circles!
old_layer_land = """    const r = px * 0.72;

    const grad = g.createRadialGradient(cx, cy, px * 0.2, cx, cy, r);
    grad.addColorStop(0, `rgb(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])})`);
    grad.addColorStop(0.75, `rgb(${Math.round(col[0] * 0.95)}, ${Math.round(col[1] * 0.95)}, ${Math.round(col[2] * 0.95)})`);
    grad.addColorStop(1, `rgba(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])}, 0.2)`);

    g.fillStyle = grad;
    g.beginPath();
    g.arc(cx, cy, r, 0, Math.PI * 2);
    g.fill();"""

new_layer_land = """    const x = (c.x - minX) * px;
    const y = (c.y - minY) * px;
    g.fillStyle = `rgb(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])})`;
    g.fillRect(x, y, px, px);"""

assert old_layer_land in text, "old_layer_land not found"
text = text.replace(old_layer_land, new_layer_land, 1)

# And in water shoreline:
old_water_stroke = """        // Sand beach fringe
        g.strokeStyle = "rgba(194, 178, 128, 0.45)";
        g.lineWidth = Math.max(2, px * 0.18);
        g.beginPath();
        g.arc(cx, cy, px * 0.52, 0, Math.PI * 2);
        g.stroke();

        // Shallow turquoise water glow
        g.fillStyle = "rgba(32, 160, 180, 0.28)";
        g.beginPath();
        g.arc(cx, cy, px * 0.58, 0, Math.PI * 2);
        g.fill();"""

new_water_stroke = """        // Sand beach fringe along land borders
        const x = (c.x - minX) * px, y = (c.y - minY) * px;
        g.fillStyle = "rgba(194, 178, 128, 0.35)";
        g.fillRect(x - px*0.1, y - px*0.1, px * 1.2, px * 1.2);
        g.fillStyle = "rgba(32, 160, 180, 0.35)";
        g.fillRect(x, y, px, px);"""

assert old_water_stroke in text, "old_water_stroke not found"
text = text.replace(old_water_stroke, new_water_stroke, 1)

# Also in drawFrame: replace the water circles with subtle wave caustics over the water tile bounds!
old_water_drawframe = """  // Animated Water Shoreline Caustics
  const waterWave = Math.sin(ts / 900) * 0.15;
  tiles.forEach(t => {
    if (!t.water) return;
    const c = t.coordinates; if (!c) return;
    const sx = (c.x + 0.5 - origin.x) * s, sy = (c.y + 0.5 - origin.y) * s;
    if (sx < -s || sx > cssW + s || sy < -s || sy > cssH + s) return;
    g.fillStyle = `rgba(0, 242, 254, ${Math.max(0.04, 0.08 + waterWave).toFixed(3)})`;
    g.beginPath();
    g.arc(sx, sy, s * 0.45, 0, Math.PI * 2);
    g.fill();
  });"""

new_water_drawframe = """  // Animated Water Shoreline Caustics
  const waterWave = Math.sin(ts / 900) * 0.08;
  tiles.forEach(t => {
    if (!t.water) return;
    const c = t.coordinates; if (!c) return;
    const sx = (c.x - origin.x) * s, sy = (c.y - origin.y) * s;
    if (sx < -s || sx > cssW + s || sy < -s || sy > cssH + s) return;
    g.fillStyle = `rgba(0, 242, 254, ${Math.max(0.03, 0.06 + waterWave).toFixed(3)})`;
    g.fillRect(sx, sy, s, s);
  });"""

assert old_water_drawframe in text, "old_water_drawframe not found"
text = text.replace(old_water_drawframe, new_water_drawframe, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

print("Tuning applied successfully.")
