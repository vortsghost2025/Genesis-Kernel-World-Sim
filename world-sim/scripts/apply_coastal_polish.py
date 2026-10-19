from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Truncate comic speech bubble on map properly for all types
old_bubble_block = """  // Action / Comic Speech Bubble (Positioned dynamically above nameplate)
  let rawLabel = act.label;
  if (rawLabel.length > 28) rawLabel = rawLabel.slice(0, 25) + "...";
  let bubbleText = rawLabel;
  let bubbleIcon = "🌿";
  if (isDowned) {
    bubbleIcon = "⚠️";
    bubbleText = `COLLAPSED PRONE (${vitals.vitality.toFixed(1)}/12 HP)`;
  } else if (act.type === "gather") {
    bubbleIcon = /berry/.test(act.resource) ? "🫐" : (/wood/.test(act.resource) ? "🪵" : (/clay/.test(act.resource) ? "🏺" : "🪨"));
    bubbleText = `Gathering ${act.resource || "Flora"}`;
  } else if (act.type === "eat") {
    bubbleIcon = "🫐";
    bubbleText = "Nourished with Berries (+HP)";
  } else if (act.type === "build" || act.type === "create_public_object") {
    bubbleIcon = "🔨";
    bubbleText = "Constructing Hearth / Monument";
  } else if (act.type === "ask") {
    bubbleIcon = "💬";
    bubbleText = act.label;
  }"""

new_bubble_block = """  // Action / Comic Speech Bubble (Compact, elegant RPG speech pill)
  let bubbleIcon = "🌿";
  let bubbleText = act.label;
  if (isDowned) {
    bubbleIcon = "⚠️";
    bubbleText = `COLLAPSED PRONE (${vitals.vitality.toFixed(1)}/12 HP)`;
  } else if (act.type === "gather") {
    bubbleIcon = /berry/.test(act.resource) ? "🫐" : (/wood/.test(act.resource) ? "🪵" : (/clay/.test(act.resource) ? "🏺" : "🪨"));
    bubbleText = `Gathering ${act.resource || "Flora"}`;
  } else if (act.type === "eat") {
    bubbleIcon = "🫐";
    bubbleText = "Nourished (+HP)";
  } else if (act.type === "build" || act.type === "create_public_object") {
    bubbleIcon = "🔨";
    bubbleText = "Constructing Hearth";
  } else if (act.type === "ask") {
    bubbleIcon = "💬";
    bubbleText = act.fullReason || act.label;
  }

  // Ensure speech bubble is compact and never sprawls across other agents
  if (bubbleText.length > 32) bubbleText = bubbleText.slice(0, 29) + "...";"""

assert old_bubble_block in text, "old_bubble_block not found"
text = text.replace(old_bubble_block, new_bubble_block, 1)

# 2. In getLayer(px): Fill base ocean so unmapped coordinates are deep ocean, not void!
old_layer_start = """  const W = GW * px, H = GH * px;
  const c2 = document.createElement("canvas");
  c2.width = W; c2.height = H;
  const g = c2.getContext("2d");

  // 1. Base Biomes (Soft Rounded Organic Blending)"""

new_layer_start = """  const W = GW * px, H = GH * px;
  const c2 = document.createElement("canvas");
  c2.width = W; c2.height = H;
  const g = c2.getContext("2d");

  // Base Abyssal Ocean Fill (Surrounds the continents in rich deep water)
  g.fillStyle = "#081d34";
  g.fillRect(0, 0, W, H);

  // 1. Base Biomes (Soft Rounded Organic Blending)"""

assert old_layer_start in text, "old_layer_start not found"
text = text.replace(old_layer_start, new_layer_start, 1)

# 3. Soften coastlines: when land borders open ocean (no tile), draw sand beach and shallow water fringe
old_neighbor_feather = """    for (const n of neighbors) {
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
    }"""

new_neighbor_feather = """    for (const n of neighbors) {
      const nt = tileByCoord.get((c.x + n.dx) + "," + (c.y + n.dy));
      const nx = (c.x + n.dx - minX + 0.5) * px;
      const ny = (c.y + n.dy - minY + 0.5) * px;

      if (!nt) {
        // Border with open ocean: draw soft sandy shore into turquoise shoals
        if (!t.water) {
          const shoreGrad = g.createLinearGradient(cx, cy, nx, ny);
          shoreGrad.addColorStop(0, "rgba(194, 178, 128, 0.5)");
          shoreGrad.addColorStop(0.5, "rgba(32, 160, 180, 0.45)");
          shoreGrad.addColorStop(1, "rgba(8, 29, 52, 0.8)");
          g.fillStyle = shoreGrad;
          g.beginPath();
          g.arc((cx + nx) / 2, (cy + ny) / 2, px * 0.5, 0, Math.PI * 2);
          g.fill();
        }
        continue;
      }

      if (nt.biome === t.biome) continue;
      const ncol = baseColor(nt);

      const bridgeGrad = g.createLinearGradient(cx, cy, nx, ny);
      bridgeGrad.addColorStop(0, `rgba(${Math.round(col[0])}, ${Math.round(col[1])}, ${Math.round(col[2])}, 0.45)`);
      bridgeGrad.addColorStop(1, `rgba(${Math.round(ncol[0])}, ${Math.round(ncol[1])}, ${Math.round(ncol[2])}, 0.45)`);

      g.fillStyle = bridgeGrad;
      g.beginPath();
      const midX = (cx + nx) / 2, midY = (cy + ny) / 2;
      g.arc(midX, midY, px * 0.48, 0, Math.PI * 2);
      g.fill();
    }"""

assert old_neighbor_feather in text, "old_neighbor_feather not found"
text = text.replace(old_neighbor_feather, new_neighbor_feather, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

print("Coastlines and compact speech bubbles updated.")
