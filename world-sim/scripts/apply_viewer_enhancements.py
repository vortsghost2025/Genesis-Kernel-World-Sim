"""Apply high-fidelity character sprites, campfire & landmark rendering, and Cognitive Dossier to viewer/index.html."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "viewer" / "index.html"

content = HTML_FILE.read_text(encoding="utf-8")

# 1. Add .agent-inner-voice CSS
target_css = """.holding-pill.depleted-alert {
  background: rgba(255, 71, 87, 0.14);
  border-color: rgba(255, 71, 87, 0.45);
  color: #ff7675;
  font-weight: 700;
  width: 100%;
  justify-content: center;
  margin-bottom: 4px;
}"""

replacement_css = target_css + """

/* Cognitive Dossier / Internal Monologue */
.agent-inner-voice {
  background: rgba(0, 0, 0, 0.45);
  border-left: 2px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 12px;
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.72rem;
  line-height: 1.4;
  color: var(--text-secondary);
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.agent-card.adam .agent-inner-voice { border-left-color: rgba(0, 210, 211, 0.6); }
.agent-card.eve .agent-inner-voice { border-left-color: rgba(254, 202, 87, 0.6); }
.agent-card.collapsed .agent-inner-voice { border-left-color: rgba(255, 71, 87, 0.7); background: rgba(30, 8, 12, 0.55); color: #ffb8b8; }
.agent-inner-voice .voice-icon {
  font-style: normal;
  font-size: 0.85rem;
  opacity: 0.85;
  flex-shrink: 0;
}
.agent-inner-voice .voice-text {
  flex: 1;
}"""

assert target_css in content, "target_css not found"
content = content.replace(target_css, replacement_css, 1)

# 2. Add sprites preloading
target_preloads = """portraitImgs.eve._ok = false;
portraitImgs.eve.onload = () => { portraitImgs.eve._ok = true; drawFrame(performance.now()); };
portraitImgs.eve.src = "eve_portrait.jpg";"""

replacement_preloads = target_preloads + """

// High-Res Painterly Character & Landmark Sprites
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
}"""

assert target_preloads in content, "target_preloads not found"
content = content.replace(target_preloads, replacement_preloads, 1)

# 3. Enhance drawObjGlyph with campfire & landmark sprites
target_draw_obj = """function drawObjGlyph(g, cat, x, y, s, rgb) {
  const col = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.92)`;
  const dark = `rgba(${Math.round(rgb[0]*0.25)},${Math.round(rgb[1]*0.25)},${Math.round(rgb[2]*0.25)},0.95)`;
  g.lineWidth = Math.max(1.2, s * 0.09);

  switch (cat) {
    case "tower": {
      g.fillStyle = col;
      g.fillRect(x - s*0.10, y - s*0.42, s*0.20, s*0.84);
      g.beginPath(); g.arc(x, y - s*0.42, s*0.18, Math.PI, 0); g.fill();
      g.fillStyle = dark;
      g.fillRect(x - s*0.06, y + s*0.10, s*0.12, s*0.16);
      break;
    }
    case "fire": {
      // Warm glowing light halo on surrounding tile
      const fireGlow = g.createRadialGradient(x, y, 0, x, y, s * 1.5);
      fireGlow.addColorStop(0, "rgba(255, 140, 20, 0.45)");
      fireGlow.addColorStop(1, "rgba(255, 140, 20, 0)");
      g.fillStyle = fireGlow;
      g.beginPath(); g.arc(x, y, s * 1.5, 0, Math.PI * 2); g.fill();

      g.fillStyle = "rgba(255, 100, 20, 0.95)";
      g.beginPath();
      g.moveTo(x, y - s*0.35); g.lineTo(x + s*0.25, y + s*0.22); g.lineTo(x - s*0.25, y + s*0.22);
      g.closePath(); g.fill();
      g.fillStyle = "rgba(255, 235, 160, 0.98)";
      g.beginPath();
      g.moveTo(x, y - s*0.12); g.lineTo(x + s*0.12, y + s*0.18); g.lineTo(x - s*0.12, y + s*0.18);
      g.closePath(); g.fill();
      break;
    }
    case "box": {
      g.strokeStyle = col;
      g.strokeRect(x - s*0.24, y - s*0.24, s*0.48, s*0.48);
      g.fillStyle = "rgba(10, 16, 26, 0.7)";
      g.fillRect(x - s*0.24, y - s*0.24, s*0.48, s*0.48);
      g.beginPath(); g.moveTo(x - s*0.24, y); g.lineTo(x + s*0.24, y); g.stroke();
      break;
    }
    default: {
      g.fillStyle = col;
      g.beginPath();
      g.moveTo(x, y - s*0.26); g.lineTo(x + s*0.26, y); g.lineTo(x, y + s*0.26); g.lineTo(x - s*0.26, y);
      g.closePath(); g.fill();
      g.strokeStyle = dark;
      g.stroke();
    }
  }
}"""

replacement_draw_obj = """function drawObjGlyph(g, cat, x, y, s, rgb) {
  const col = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.92)`;
  const dark = `rgba(${Math.round(rgb[0]*0.25)},${Math.round(rgb[1]*0.25)},${Math.round(rgb[2]*0.25)},0.95)`;
  g.lineWidth = Math.max(1.2, s * 0.09);

  switch (cat) {
    case "tower":
    case "star": {
      if (sprites.landmark && sprites.landmark._ok) {
        const monPulse = 0.3 + 0.2 * Math.sin(performance.now() / 900);
        const aura = g.createRadialGradient(x, y, 0, x, y, s * 1.2);
        aura.addColorStop(0, `rgba(0, 210, 211, ${monPulse.toFixed(2)})`);
        aura.addColorStop(1, "rgba(0, 210, 211, 0)");
        g.fillStyle = aura;
        g.beginPath(); g.arc(x, y, s * 1.2, 0, Math.PI * 2); g.fill();

        const lmH = Math.max(36, s * 1.25);
        const lmW = lmH * (sprites.landmark.width / sprites.landmark.height);
        g.drawImage(sprites.landmark, x - lmW / 2, y - lmH * 0.72, lmW, lmH);
      } else {
        g.fillStyle = col;
        g.fillRect(x - s*0.10, y - s*0.42, s*0.20, s*0.84);
        g.beginPath(); g.arc(x, y - s*0.42, s*0.18, Math.PI, 0); g.fill();
        g.fillStyle = dark;
        g.fillRect(x - s*0.06, y + s*0.10, s*0.12, s*0.16);
      }
      break;
    }
    case "fire": {
      // Warm glowing light halo on surrounding tile
      const fireGlow = g.createRadialGradient(x, y, 0, x, y, s * 1.6);
      fireGlow.addColorStop(0, "rgba(255, 140, 20, 0.48)");
      fireGlow.addColorStop(0.5, "rgba(255, 90, 10, 0.22)");
      fireGlow.addColorStop(1, "rgba(255, 60, 0, 0)");
      g.fillStyle = fireGlow;
      g.beginPath(); g.arc(x, y, s * 1.6, 0, Math.PI * 2); g.fill();

      if (sprites.campfire && sprites.campfire._ok) {
        const flamePulse = 1 + Math.sin(performance.now() / 150) * 0.04;
        const fireW = Math.max(28, s * 0.95) * flamePulse;
        const fireH = fireW * (sprites.campfire.height / sprites.campfire.width);
        g.drawImage(sprites.campfire, x - fireW / 2, y - fireH * 0.65, fireW, fireH);

        // Rising spark motes
        const emberTime = performance.now() * 0.003;
        for (let i = 0; i < 3; i++) {
          const ep = ((emberTime + i * 0.33) % 1);
          const ex = x + Math.sin(emberTime * 3 + i) * (s * 0.22);
          const ey = y - fireH * 0.3 - ep * (s * 0.55);
          g.fillStyle = `rgba(255, 210, 80, ${(1 - ep).toFixed(2)})`;
          g.beginPath();
          g.arc(ex, ey, Math.max(1, 1.8 * (1 - ep)), 0, Math.PI * 2);
          g.fill();
        }
      } else {
        g.fillStyle = "rgba(255, 100, 20, 0.95)";
        g.beginPath();
        g.moveTo(x, y - s*0.35); g.lineTo(x + s*0.25, y + s*0.22); g.lineTo(x - s*0.25, y + s*0.22);
        g.closePath(); g.fill();
        g.fillStyle = "rgba(255, 235, 160, 0.98)";
        g.beginPath();
        g.moveTo(x, y - s*0.12); g.lineTo(x + s*0.12, y + s*0.18); g.lineTo(x - s*0.12, y + s*0.18);
        g.closePath(); g.fill();
      }
      break;
    }
    case "box": {
      g.strokeStyle = col;
      g.strokeRect(x - s*0.24, y - s*0.24, s*0.48, s*0.48);
      g.fillStyle = "rgba(10, 16, 26, 0.7)";
      g.fillRect(x - s*0.24, y - s*0.24, s*0.48, s*0.48);
      g.beginPath(); g.moveTo(x - s*0.24, y); g.lineTo(x + s*0.24, y); g.stroke();
      break;
    }
    default: {
      g.fillStyle = col;
      g.beginPath();
      g.moveTo(x, y - s*0.26); g.lineTo(x + s*0.26, y); g.lineTo(x, y + s*0.26); g.lineTo(x - s*0.26, y);
      g.closePath(); g.fill();
      g.strokeStyle = dark;
      g.stroke();
    }
  }
}"""

assert target_draw_obj in content, "target_draw_obj not found"
content = content.replace(target_draw_obj, replacement_draw_obj, 1)

# 4. Enhance drawCharacterFigure with high-res character sprites
idx_start = content.find("function drawCharacterFigure(g, a, sx, sy, s, ts, idx = 0) {")
idx_end = content.find("function roundRect(g, x, y, w, h, r) {", idx_start)
assert idx_start != -1 and idx_end != -1, "drawCharacterFigure boundaries not found"

replacement_draw_character = """function drawCharacterFigure(g, a, sx, sy, s, ts, idx = 0) {
  const isAdam = a.ref.toLowerCase().includes("adam");
  const rawName = a.ref.split("_")[1] || a.ref;
  const name = rawName.toUpperCase();
  const pairData = PAIRS[a.pair] || {};
  const vitals = (pairData.vitals || {})[a.ref] || { hunger: 0, warmth: 80, vitality: 100, downed: false };
  const isDowned = Boolean(vitals.downed);
  const act = getAgentActivity(a.pair, a.ref);
  const civTag = a.pair === "east" ? "EAST VALLEY" : "WEST DAWN";
  const rgb = PAIR_RGB[a.pair] || [180, 180, 180];
  const accentHex = isAdam ? "#00d2d3" : "#feca57";

  g.save();

  // Figure scale: Clamp so characters are always clear human figures, never a dot or pixel
  const figScale = clamp(s / 16, 0.85, 1.4);

  let figureTopY = sy - 40;

  if (isDowned) {
    // =========================================================================
    // POSTURE A: PRONE / COLLAPSED ON SOIL (RESTING / RECOVERING ON THE GROUND)
    // =========================================================================
    const breath = Math.sin(ts / 750);
    const p = ((ts / 1400) + (isAdam ? 0 : 0.5)) % 1;

    // Ground Depression Shadow under resting body
    g.fillStyle = "rgba(0, 0, 0, 0.55)";
    g.beginPath();
    g.ellipse(sx, sy + 6 * figScale, 34 * figScale, 13 * figScale, 0, 0, Math.PI * 2);
    g.fill();

    // Soft Emergency Warmth / Soil Pulse
    const halo = g.createRadialGradient(sx, sy + 4 * figScale, 0, sx, sy + 4 * figScale, 40 * figScale);
    halo.addColorStop(0, `rgba(255, 71, 87, ${(0.35 + 0.15 * breath).toFixed(3)})`);
    halo.addColorStop(1, "rgba(0, 0, 0, 0)");
    g.fillStyle = halo;
    g.beginPath();
    g.ellipse(sx, sy + 4 * figScale, 40 * figScale, 18 * figScale, 0, 0, Math.PI * 2);
    g.fill();

    // Pulse Ring on Soil
    g.strokeStyle = `rgba(255, 71, 87, ${(0.8 * (1 - p)).toFixed(3)})`;
    g.lineWidth = 2;
    g.beginPath();
    g.ellipse(sx, sy + 5 * figScale, (24 + p * 20) * figScale, (10 + p * 8) * figScale, 0, 0, Math.PI * 2);
    g.stroke();

    const proneSprite = isAdam ? sprites.adam_collapsed : sprites.eve_collapsed;
    if (proneSprite && proneSprite._ok) {
      // High-Fidelity Transparent Prone Character Sprite
      const spriteW = Math.max(90, s * 2.2) * (1 + breath * 0.02);
      const spriteH = spriteW * (proneSprite.height / proneSprite.width);
      const drawX = sx - spriteW / 2;
      const drawY = sy - spriteH * 0.55;
      g.drawImage(proneSprite, drawX, drawY, spriteW, spriteH);
      figureTopY = drawY;
    } else {
      // PRONE CHARACTER BODY (Vector fallback)
      g.save();
      g.translate(sx, sy);
      g.scale(figScale, figScale);

      // 1. Legs & Boots (lying sideways to the left)
      g.fillStyle = "#3d271d";
      roundRect(g, -22, 2, 8, 6, 2);
      g.fill();
      g.fillStyle = "#593c28";
      g.fillRect(-17, 1, 3, 7);

      g.fillStyle = "#252e38";
      g.beginPath();
      g.moveTo(-16, 2); g.lineTo(-6, 0); g.lineTo(-6, 8); g.lineTo(-16, 7);
      g.closePath();
      g.fill();

      // 2. Torso
      const chestRise = breath * 1.2;
      g.fillStyle = isAdam ? "#34495e" : "#3d5a45";
      roundRect(g, -7, -2 - chestRise, 16, 11 + chestRise, 3);
      g.fill();

      g.strokeStyle = accentHex;
      g.lineWidth = 1.5;
      g.beginPath();
      g.moveTo(4, -2 - chestRise); g.lineTo(9, 3); g.lineTo(4, 9);
      g.stroke();

      g.fillStyle = "#1e1713";
      g.fillRect(-1, -1 - chestRise, 3, 10 + chestRise);
      g.fillStyle = "#d4af37";
      g.fillRect(-1, 3, 3, 3);

      // 3. Arms
      g.fillStyle = isAdam ? "#2c3e50" : "#2f4435";
      g.fillRect(-4, 7, 12, 3);
      g.fillStyle = "#d8a47f";
      g.beginPath();
      g.arc(9, 8, 2.2, 0, Math.PI * 2);
      g.fill();

      g.fillStyle = isAdam ? "#34495e" : "#3d5a45";
      g.beginPath();
      g.moveTo(7, -1); g.lineTo(15, -2); g.lineTo(14, 2); g.lineTo(7, 2);
      g.closePath();
      g.fill();

      // 4. Head & Face
      g.fillStyle = "#d8a47f";
      g.beginPath();
      g.arc(16, 2, 6, 0, Math.PI * 2);
      g.fill();

      g.strokeStyle = "#4a3328";
      g.lineWidth = 1.2;
      g.beginPath();
      g.arc(17, 2, 2, 0.1 * Math.PI, 0.9 * Math.PI);
      g.stroke();

      if (isAdam) {
        g.fillStyle = "#1c1815";
        g.beginPath();
        g.arc(15, 0, 6.2, Math.PI * 0.7, Math.PI * 1.9);
        g.fill();
        g.fillStyle = "#2d241e";
        g.beginPath();
        g.moveTo(11, -2); g.lineTo(18, -4); g.lineTo(16, 0);
        g.closePath();
        g.fill();
      } else {
        g.fillStyle = "#161311";
        g.beginPath();
        g.arc(15, 0, 6.2, Math.PI * 0.7, Math.PI * 1.9);
        g.fill();
        g.strokeStyle = "#161311";
        g.lineWidth = 2.8;
        g.beginPath();
        g.moveTo(14, 4);
        g.quadraticCurveTo(11, 9, 3, 9);
        g.stroke();
        g.fillStyle = "#ffd32a";
        g.beginPath();
        g.arc(10, 8, 1.5, 0, Math.PI * 2);
        g.arc(6, 9, 1.5, 0, Math.PI * 2);
        g.fill();
      }
      g.restore();
      figureTopY = sy - 20 * figScale;
    }

    // Gentle floating recovery motes
    const moteOff = (ts * 0.02 + (isAdam ? 0 : 50)) % 22;
    g.font = "700 9px 'Plus Jakarta Sans', sans-serif";
    g.fillStyle = `rgba(255, 234, 167, ${(0.85 * (1 - moteOff / 22)).toFixed(3)})`;
    g.fillText("z", sx + 22 * figScale, sy - 8 * figScale - moteOff);

  } else {
    // =========================================================================
    // POSTURE B: UPRIGHT ACTIVE (STANDING, WALKING, EATING, CRAFTING)
    // =========================================================================
    const breath = Math.sin(ts / 650);
    const p = ((ts / 1600) + (isAdam ? 0 : 0.5)) % 1;
    const isEating = act.kind === "eat" || (vitals.hunger < 5 && vitals.vitality < 30);
    const isBuilding = act.kind === "build";
    const isAsking = act.kind === "ask";

    // Ground Shadow under feet
    g.fillStyle = "rgba(0, 0, 0, 0.45)";
    g.beginPath();
    g.ellipse(sx, sy + 18 * figScale, 18 * figScale, 6 * figScale, 0, 0, Math.PI * 2);
    g.fill();

    // Civilization aura pulse around feet
    g.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]}, ${(0.55 * (1 - p)).toFixed(3)})`;
    g.lineWidth = 1.8;
    g.beginPath();
    g.ellipse(sx, sy + 18 * figScale, (15 + p * 13) * figScale, (5 + p * 4) * figScale, 0, 0, Math.PI * 2);
    g.stroke();

    const activeSprite = isAdam ? sprites.adam_standing : sprites.eve_standing;
    if (activeSprite && activeSprite._ok) {
      // High-Fidelity Painterly Standing Character Sprite
      const sway = Math.sin(ts / 600) * 1.2;
      const breathH = Math.sin(ts / 750) * 1.0;
      const figH = Math.max(85, s * 2.1) + breathH;
      const figW = figH * (activeSprite.width / activeSprite.height);
      const drawX = sx - figW / 2 + sway;
      const drawY = (sy + 18 * figScale) - figH;
      g.drawImage(activeSprite, drawX, drawY, figW, figH);
      figureTopY = drawY;

      // Subtle activity indicators above sprite
      if (isEating) {
        const chew = Math.sin(ts / 180) * 2;
        g.font = "14px sans-serif";
        g.fillText("🫐", sx + figW * 0.28, drawY + figH * 0.35 + chew);
      } else if (isBuilding) {
        const spark = Math.sin(ts / 140) * 3;
        g.font = "14px sans-serif";
        g.fillText("🔨", sx + figW * 0.3, drawY + figH * 0.3 + spark);
      } else if (isAsking) {
        g.font = "14px sans-serif";
        g.fillText("💭", sx + figW * 0.28, drawY + figH * 0.25);
      }
    } else {
      // UPRIGHT CHARACTER BODY (Vector fallback)
      g.save();
      g.translate(sx, sy);
      g.scale(figScale, figScale);

      // 1. Boots & Legs
      g.fillStyle = "#3d271d";
      roundRect(g, -7, 13, 6, 6, 2);
      roundRect(g, 1, 13, 6, 6, 2);
      g.fill();
      g.fillStyle = "#593c28";
      g.fillRect(-7, 12, 6, 2);
      g.fillRect(1, 12, 6, 2);

      g.fillStyle = "#252e38";
      g.fillRect(-6, 3, 4, 10);
      g.fillRect(2, 3, 4, 10);

      // 2. Torso & Tunic
      const chestRise = breath * 1.0;
      g.fillStyle = isAdam ? "#34495e" : "#3d5a45";
      roundRect(g, -8, -10 - chestRise, 16, 15 + chestRise, 3);
      g.fill();

      g.strokeStyle = accentHex;
      g.lineWidth = 1.6;
      g.beginPath();
      g.moveTo(-4, -10 - chestRise);
      g.lineTo(0, -4);
      g.lineTo(4, -10 - chestRise);
      g.stroke();

      g.beginPath();
      g.moveTo(-8, 5);
      g.lineTo(8, 5);
      g.stroke();

      g.fillStyle = "#1e1713";
      g.fillRect(-8, 0, 16, 3);
      g.fillStyle = "#d4af37";
      g.fillRect(-2, 0, 4, 3);
      g.fillStyle = "#4a3328";
      g.fillRect(5, -1, 3, 4);

      // 3. Arms & Hands
      if (isEating) {
        const chew = Math.sin(ts / 180) * 1.2;
        g.strokeStyle = isAdam ? "#34495e" : "#3d5a45";
        g.lineWidth = 3.2;
        g.lineCap = "round";
        g.beginPath();
        g.moveTo(7, -8);
        g.lineTo(10, -14 + chew);
        g.lineTo(4, -14 + chew);
        g.stroke();

        g.fillStyle = "#d8a47f";
        g.beginPath();
        g.arc(3, -14 + chew, 2.2, 0, Math.PI * 2);
        g.fill();

        g.fillStyle = "#4834d4";
        g.beginPath();
        g.arc(2, -15 + chew, 1.8, 0, Math.PI * 2);
        g.arc(4, -16 + chew, 1.8, 0, Math.PI * 2);
        g.arc(4, -13 + chew, 1.5, 0, Math.PI * 2);
        g.fill();

        g.beginPath();
        g.moveTo(-7, -8);
        g.lineTo(-9, 0);
        g.stroke();
        g.fillStyle = "#d8a47f";
        g.beginPath();
        g.arc(-9, 1, 2, 0, Math.PI * 2);
        g.fill();

      } else if (isBuilding) {
        const hammer = Math.sin(ts / 150) * 4;
        g.strokeStyle = isAdam ? "#34495e" : "#3d5a45";
        g.lineWidth = 3.2;
        g.lineCap = "round";
        g.beginPath();
        g.moveTo(7, -8);
        g.lineTo(12, -16 + hammer);
        g.stroke();

        g.fillStyle = "#a4b0be";
        g.fillRect(10, -20 + hammer, 6, 4);
        g.fillStyle = "#593c28";
        g.fillRect(12, -17 + hammer, 2, 6);

        g.beginPath();
        g.moveTo(-7, -8);
        g.lineTo(-9, -2);
        g.stroke();

      } else if (isAsking) {
        const wave = Math.sin(ts / 350) * 2;
        g.strokeStyle = isAdam ? "#34495e" : "#3d5a45";
        g.lineWidth = 3.2;
        g.lineCap = "round";
        g.beginPath();
        g.moveTo(7, -8);
        g.lineTo(12, -18 + wave);
        g.stroke();
        g.fillStyle = "#d8a47f";
        g.beginPath();
        g.arc(12, -19 + wave, 2.2, 0, Math.PI * 2);
        g.fill();

        g.beginPath();
        g.moveTo(-7, -8);
        g.lineTo(-10, -2);
        g.lineTo(-7, 0);
        g.stroke();

      } else {
        const sway = Math.sin(ts / 500) * 2;
        g.strokeStyle = isAdam ? "#34495e" : "#3d5a45";
        g.lineWidth = 3.2;
        g.lineCap = "round";
        g.beginPath();
        g.moveTo(-7, -8);
        g.lineTo(-9 - sway * 0.5, 0);
        g.moveTo(7, -8);
        g.lineTo(9 + sway * 0.5, 0);
        g.stroke();

        g.fillStyle = "#d8a47f";
        g.beginPath();
        g.arc(-9 - sway * 0.5, 1, 2, 0, Math.PI * 2);
        g.arc(9 + sway * 0.5, 1, 2, 0, Math.PI * 2);
        g.fill();
      }

      // 4. Head & Face
      g.fillStyle = "#c8966f";
      g.fillRect(-2, -12 - chestRise, 4, 3);

      g.fillStyle = "#d8a47f";
      g.beginPath();
      g.arc(0, -17 - chestRise, 6.2, 0, Math.PI * 2);
      g.fill();

      g.fillStyle = "#ffffff";
      g.fillRect(-3.5, -18.5 - chestRise, 2.2, 2.2);
      g.fillRect(1.5, -18.5 - chestRise, 2.2, 2.2);
      g.fillStyle = "#1e1713";
      g.fillRect(-2.5, -18 - chestRise, 1.4, 1.4);
      g.fillRect(2.5, -18 - chestRise, 1.4, 1.4);

      g.strokeStyle = "#4a3328";
      g.lineWidth = 1;
      g.beginPath();
      g.moveTo(-4, -20 - chestRise); g.lineTo(-1.5, -20 - chestRise);
      g.moveTo(1.5, -20 - chestRise); g.lineTo(4, -20 - chestRise);
      g.stroke();

      if (isAdam) {
        g.fillStyle = "#1c1815";
        g.beginPath();
        g.arc(0, -19 - chestRise, 6.8, Math.PI * 0.85, Math.PI * 2.15);
        g.fill();
        g.beginPath();
        g.moveTo(-6, -17 - chestRise);
        g.lineTo(-4, -13 - chestRise);
        g.lineTo(-2, -17 - chestRise);
        g.lineTo(2, -19 - chestRise);
        g.lineTo(5, -14 - chestRise);
        g.lineTo(6, -17 - chestRise);
        g.closePath();
        g.fill();
      } else {
        g.fillStyle = "#161311";
        g.beginPath();
        g.arc(0, -19 - chestRise, 6.8, Math.PI * 0.85, Math.PI * 2.15);
        g.fill();
        g.strokeStyle = "#161311";
        g.lineWidth = 3;
        g.beginPath();
        g.moveTo(5, -16 - chestRise);
        g.quadraticCurveTo(8, -10, 6, 2);
        g.stroke();
        g.fillStyle = "#ffd32a";
        g.beginPath();
        g.arc(7, -8, 1.5, 0, Math.PI * 2);
        g.arc(6.5, -2, 1.5, 0, Math.PI * 2);
        g.fill();
      }

      g.restore();
      figureTopY = (sy - 26 * figScale);
    }
  }

  // =========================================================================
  // PAINTED PORTRAIT CAMEO MEDALLION (High-Res Face Cameo on Map)
  // =========================================================================
  const portraitImg = isAdam ? portraitImgs.adam : portraitImgs.eve;
  const medR = 14 * figScale;
  const medY = figureTopY - medR - 8;

  if (portraitImg && portraitImg._ok) {
    g.save();
    g.beginPath();
    g.arc(sx, medY, medR, 0, Math.PI * 2);
    g.clip();
    g.drawImage(portraitImg, sx - medR, medY - medR, medR * 2, medR * 2);
    g.restore();

    // Medallion Golden/Crimson/Cyan Rim
    g.strokeStyle = isDowned ? "#ff4757" : accentHex;
    g.lineWidth = 2.4;
    g.beginPath();
    g.arc(sx, medY, medR, 0, Math.PI * 2);
    g.stroke();

    // Status Emblem at bottom-right of Medallion
    const embX = sx + medR * 0.7, embY = medY + medR * 0.7;
    g.fillStyle = isDowned ? "#ff4757" : (act.kind === "eat" ? "#10ac84" : accentHex);
    g.beginPath();
    g.arc(embX, embY, 5 * figScale, 0, Math.PI * 2);
    g.fill();
    g.strokeStyle = "#080c14";
    g.lineWidth = 1.5;
    g.stroke();
  }

  // =========================================================================
  // LIVE ACTION / SPEECH BUBBLE (Tells Sean exactly what they are doing!)
  // =========================================================================
  let bannerText = "";
  let iconPrefix = "";
  if (isDowned) {
    if (act.kind === "eat") {
      iconPrefix = "🫐";
      bannerText = `${name}: RECOVERING ON SOIL · ATE BERRIES (${vitals.vitality.toFixed(1)}/12 HP)`;
    } else if (act.kind === "ask") {
      iconPrefix = "💬";
      bannerText = `${name}: COLLAPSED · "${act.short}"`;
    } else {
      iconPrefix = "💤";
      bannerText = `${name}: COLLAPSED PRONE ON SOIL · RESTING (${vitals.vitality.toFixed(1)}/12 HP)`;
    }
  } else if (act.kind === "eat") {
    iconPrefix = "🫐";
    bannerText = `${name}: CONSUMING WILD BERRIES (+15 FOOD)`;
  } else if (act.kind === "build") {
    iconPrefix = "🔥";
    bannerText = `${name}: ${act.text.toUpperCase()}`;
  } else if (act.kind === "ask") {
    iconPrefix = "💬";
    bannerText = `${name}: "${act.short}"`;
  } else if (vitals.hunger >= 88) {
    iconPrefix = "⚠️";
    bannerText = `${name}: STARVING · SEARCHING FOR FORAGE`;
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

  // Speech bubble pointer tail (anchored to character position sx)
  const tailX = clamp(sx, bubbleX + 12, bubbleX + bubbleW - 12);
  g.fillStyle = isDowned ? "rgba(40, 10, 18, 0.95)" : "rgba(8, 14, 24, 0.95)";
  g.beginPath();
  g.moveTo(tailX - 5, bubbleY + bubbleH);
  g.lineTo(tailX, bubbleY + bubbleH + 5);
  g.lineTo(tailX + 5, bubbleY + bubbleH);
  g.closePath();
  g.fill();

  // Glass background
  roundRect(g, bubbleX, bubbleY, bubbleW, bubbleH, 6);
  g.fill();

  // Glowing border
  g.strokeStyle = isDowned ? "rgba(255, 71, 87, 0.9)" : (isAdam ? "rgba(0, 210, 211, 0.85)" : "rgba(254, 202, 87, 0.85)");
  g.lineWidth = 1.4;
  roundRect(g, bubbleX, bubbleY, bubbleW, bubbleH, 6);
  g.stroke();

  // Text inside bubble
  g.fillStyle = isDowned ? "#ffc2c7" : "#ffffff";
  g.fillText(fullLabel, bubbleX + 10, bubbleY + 15);

  g.restore();
}

"""

content = content[:idx_start] + replacement_draw_character + content[idx_end:]

# 5. Add Cognitive Dossier / getAgentInnerVoice and inject into renderBiometricsTab
target_bio = """function renderBiometricsTab() {
  const el = document.getElementById("agents-list");"""

inner_voice_helper = """function getAgentInnerVoice(pn, ref, v, act, inv) {
  const isAdam = ref.toLowerCase().includes("adam");
  const name = isAdam ? "Adam" : "Eve";
  const partner = isAdam ? "Eve" : "Adam";
  const pair = PAIRS[pn] || {};

  // 1. Unheard question
  for (const ask of (pair.agent_asks || [])) {
    const askWho = String(ask.agent || "").toLowerCase();
    if (askWho.includes(name.toLowerCase()) && ask.status === "unheard") {
      return `"${ask.question}" — We wait for an answer from beyond the silence.`;
    }
  }

  // 2. Critical vitals
  if (v.downed) {
    if (v.vitality > 8) {
      return `Strength is slowly returning to my limbs. In a few moments I will rise and stand beside ${partner}.`;
    }
    return `Exhaustion overcame me... the ground is cold, but my breath is steadying. Gathering strength to stand.`;
  }
  if (v.hunger >= 85) {
    return `Hunger is gnawing at my senses. I must search every shrub and ridge for wild berries before darkness settles.`;
  }
  if (v.warmth <= 25) {
    return `The wind cuts deep. I need kindling and the hearth fire before my fingers go numb.`;
  }

  // 3. Current activity
  if (act.kind === "eat") {
    return `Wild berries are reviving my blood. I must forage extra so ${partner} has rations as well.`;
  }
  if (act.kind === "build") {
    return `Shaping stone and tending the hearth. With a solid fire, the cold valley cannot break us.`;
  }

  // 4. Pack & Exploration
  const foodCount = (inv.wild_berries || 0) + (inv.mushrooms || 0) + (inv.edible_roots || 0);
  if (foodCount > 10) {
    return `We have provisions (${foodCount} rations in pack). We can explore further into uncharted ground today.`;
  }
  return `Watching the horizon with ${partner}. Every path we walk together carves our home into this earth.`;
}

"""

assert target_bio in content, "target_bio not found"
content = content.replace(target_bio, inner_voice_helper + target_bio, 1)

# Now inject inner voice into agent card HTML
target_card_body = """        <div class="telemetry-grid">
          ${row("HUNGER", "fill-hunger", v.hunger, hungerDanger, "%")}
          ${row("VITAL", "fill-vital", v.vitality, vitalCrit, " HP")}
          ${row("WARMTH", "fill-warmth", v.warmth, warmthCold, "°C")}
          ${row("WETNESS", "fill-wet", v.wetness || 0, "", "%")}
        </div>

        <div class="holdings-tray">"""

replacement_card_body = """        <div class="telemetry-grid">
          ${row("HUNGER", "fill-hunger", v.hunger, hungerDanger, "%")}
          ${row("VITAL", "fill-vital", v.vitality, vitalCrit, " HP")}
          ${row("WARMTH", "fill-warmth", v.warmth, warmthCold, "°C")}
          ${row("WETNESS", "fill-wet", v.wetness || 0, "", "%")}
        </div>

        <div class="agent-inner-voice">
          <span class="voice-icon">🧠</span>
          <span class="voice-text">“${esc(getAgentInnerVoice(pn, ref, v, act, inv))}”</span>
        </div>

        <div class="holdings-tray">"""

assert target_card_body in content, "target_card_body not found"
content = content.replace(target_card_body, replacement_card_body, 1)

# Ensure strictly LF line endings
content = content.replace("\r\n", "\n")

HTML_FILE.write_text(content, encoding="utf-8", newline="\n")
print("SUCCESS: viewer/index.html updated cleanly with LF line endings.")
