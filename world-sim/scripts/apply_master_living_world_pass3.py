"""Master Living World Pass 3:
Installs:
1. Environmental Scenery (trees, rocks, berry bushes, campfire, landmark) with wind sway & drop shadows.
2. Soft Feathered Exploration Horizon (Fog of War Mask).
3. Living Character Action Engine (movement interpolation, walking stride, dust, tool swing, floating loot cards, vitality sparkles, radar distress pulse).
4. Camera Tracking Mode (smoothly follows Adam or Eve as they explore).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

target_start = """// Floating Combat/Loot Text FX"""
target_end = """function renderBiometrics() {"""

replacement_code = '''// Particle & Effect Systems
const floatingTexts = [];
function spawnFloatingText(text, sx, sy, col = "#2ed573", icon = "") {
  floatingTexts.push({ text, icon, sx, sy, col, startTs: performance.now(), dur: 2200 });
  if (floatingTexts.length > 30) floatingTexts.shift();
}

const worldParticles = [];
function spawnParticle(x, y, vx, vy, col, size = 3, life = 800) {
  worldParticles.push({ x, y, vx, vy, col, size, startTs: performance.now(), life });
  if (worldParticles.length > 80) worldParticles.shift();
}

// Camera Tracking
let trackedAgentRef = null;
function toggleTrackAgent(ref) {
  if (trackedAgentRef === ref) {
    trackedAgentRef = null;
  } else {
    trackedAgentRef = ref;
  }
  const ind = document.getElementById("track-indicator");
  if (ind) {
    if (trackedAgentRef) {
      ind.style.display = "inline-block";
      ind.textContent = `🎥 TRACKING: ${trackedAgentRef.toUpperCase().replace(/.*_/, "")}`;
    } else {
      ind.style.display = "none";
    }
  }
  renderBiometrics();
}
window.toggleTrackAgent = toggleTrackAgent;

// Animated Agent Position Tracking (Smooth interpolation between heartbeats)
const agentAnimState = new Map();

function getAgentWorldPos(pairName, agentRef, hb, p = 1) {
  const pair = PAIRS[pairName] || {};
  const tl = pair.position_timeline || {};
  const currTid = (tl[hb] || pair.current_positions || {})[agentRef];
  const prevTid = (tl[Math.max(1, hb - 1)] || {})[agentRef] || currTid;

  const tCurr = tiles.get(currTid);
  const tPrev = tiles.get(prevTid);

  const cCurr = tCurr && tCurr.coordinates ? tCurr.coordinates : { x: 0, y: 0 };
  const cPrev = tPrev && tPrev.coordinates ? tPrev.coordinates : cCurr;

  // Ease-in-out interpolation
  const ease = p < 0.5 ? 2 * p * p : -1 + (4 - 2 * p) * p;
  const x = cPrev.x + (cCurr.x - cPrev.x) * ease;
  const y = cPrev.y + (cCurr.y - cPrev.y) * ease;
  const isMoving = (cCurr.x !== cPrev.x || cCurr.y !== cPrev.y) && p < 0.95;

  return { x, y, cCurr, cPrev, isMoving, currTid };
}

// Activity & Speech Text Extractor from Real Heartbeat Action
function getAgentRealAction(pairName, agentRef, hb) {
  const hbObj = (hbIndex[pairName] || new Map()).get(hb);
  const rawShort = agentRef.replace(`${pairName}_`, "");
  const act = (hbObj && hbObj.actions) ? (hbObj.actions[agentRef] || hbObj.actions[rawShort]) : null;

  if (!act) {
    // Check unheard asks
    const pair = PAIRS[pairName] || {};
    for (const ask of (pair.agent_asks || [])) {
      const askWho = String(ask.agent || "").toLowerCase();
      if (askWho.includes(rawShort) && ask.status === "unheard") {
        let q = String(ask.question || "");
        if (q.length > 55) q = q.slice(0, 52) + "...";
        return { type: "ask", label: `Asked: "${q}"`, fullReason: q, resource: null };
      }
    }
    return { type: "idle", label: "Exploring sector", fullReason: "", resource: null };
  }

  const t = String(act.type || "idle").toLowerCase();
  const res = act.resource ? act.resource.replace(/_/g, " ") : null;
  const reason = String(act.reason || "");

  let label = "Active";
  if (t === "gather") label = `Gathering ${res || "Flora"}`;
  else if (t === "eat") label = "Consuming Rations (+HP)";
  else if (t === "move") label = `Traveling to Sector`;
  else if (t === "build" || t === "create_public_object") label = "Constructing Structure";
  else if (t === "modify_owned_public_object") label = "Inscribing Rune Modification";
  else if (t === "ask_human" || t === "request_capability") label = `Querying: "${reason.slice(0, 45)}..."`;
  else if (t === "inspect_public_object" || t === "use_object") label = "Examining Landmark";
  else label = reason ? (reason.slice(0, 40) + "...") : "Exploring";

  return { type: t, label, fullReason: reason, resource: res, target_tile: act.target_tile };
}

// Character Figure Renderer (Smooth Movement + Tool Working + Overhead Telemetry)
function drawCharacter(g, a, worldX, worldY, s, ts, idx = 0) {
  const origin = screenToWorld(0, 0);
  const sx = (worldX + 0.5 - origin.x) * s;
  const sy = (worldY + 0.5 - origin.y) * s;

  const isAdam = a.ref.toLowerCase().includes("adam");
  const rawName = a.ref.split("_")[1] || a.ref;
  const name = rawName.toUpperCase();
  const pairData = PAIRS[a.pair] || {};
  const vitals = (pairData.vitals || {})[a.ref] || { hunger: 0, warmth: 80, vitality: 100, downed: false };
  const isDowned = Boolean(vitals.downed);
  const act = getAgentRealAction(a.pair, a.ref, currentHb);
  const factionCol = a.pair === "east" ? "#00d2d3" : "#feca57";

  g.save();
  const figScale = clamp(s / 16, 0.85, 1.35);

  // Faction Ground Aura & Footstep Shadow
  g.save();
  g.translate(sx, sy + 18 * figScale);

  // Soft Ground Shadow
  g.fillStyle = "rgba(0, 5, 14, 0.52)";
  g.beginPath();
  g.ellipse(0, 0, isDowned ? 36 * figScale : 20 * figScale, isDowned ? 14 * figScale : 7 * figScale, 0, 0, Math.PI * 2);
  g.fill();

  // Faction Selection Ring
  const ringPulse = 1 + Math.sin(ts / 400 + idx) * 0.08;
  g.strokeStyle = isDowned ? "rgba(255, 71, 87, 0.8)" : (a.pair === "east" ? "rgba(0, 210, 211, 0.75)" : "rgba(254, 202, 87, 0.75)");
  g.lineWidth = 1.8;
  g.beginPath();
  g.ellipse(0, 0, 24 * figScale * ringPulse, 8 * figScale * ringPulse, 0, 0, Math.PI * 2);
  g.stroke();

  // Concentric Distress Radar Waves for Downed Agents
  if (isDowned) {
    const wave = (ts % 2400) / 2400;
    const waveR = 24 * figScale + wave * 45 * figScale;
    g.strokeStyle = `rgba(255, 71, 87, ${(1 - wave) * 0.75})`;
    g.lineWidth = 1.5;
    g.beginPath();
    g.ellipse(0, 0, waveR, waveR * 0.35, 0, 0, Math.PI * 2);
    g.stroke();
  }
  g.restore();

  let figureTopY = sy - 40;

  if (isDowned) {
    // Prone Sprite with subtle breathing heave
    const breath = Math.sin(ts / 800) * 0.02;
    const proneSprite = isAdam ? sprites.adam_collapsed : sprites.eve_collapsed;
    if (proneSprite && proneSprite._ok) {
      const spriteW = Math.max(90, s * 2.2) * (1 + breath);
      const spriteH = spriteW * (proneSprite.height / proneSprite.width);
      const drawX = sx - spriteW / 2;
      const drawY = sy - spriteH * 0.52;
      g.drawImage(proneSprite, drawX, drawY, spriteW, spriteH);
      figureTopY = drawY;
    }
  } else {
    // Upright / Active / Walking Sprite
    const isGathering = act.type === "gather";
    const isEating = act.type === "eat";
    const isBuilding = act.type === "build" || act.type === "create_public_object";

    // Walking cadence & tool working heave
    let strideY = 0;
    let workAngle = 0;
    if (isGathering) {
      workAngle = Math.sin(ts / 180) * 0.08;
      strideY = Math.abs(Math.sin(ts / 180)) * 4;
      if (Math.random() < 0.25) {
        spawnParticle(worldX + 0.5 + (Math.random()-0.5)*0.3, worldY + 0.6, (Math.random()-0.5)*0.8, -0.4 - Math.random()*0.5, "#2ed573", 2.5, 600);
      }
    } else if (isBuilding) {
      workAngle = Math.sin(ts / 120) * 0.12;
      strideY = Math.abs(Math.sin(ts / 120)) * 3;
      if (Math.random() < 0.35) {
        spawnParticle(worldX + 0.5 + (Math.random()-0.5)*0.4, worldY + 0.5, (Math.random()-0.5)*1.2, -0.6 - Math.random()*0.8, "#feca57", 2, 500);
      }
    } else if (isEating) {
      strideY = Math.sin(ts / 250) * 2;
      if (Math.random() < 0.2) {
        spawnParticle(worldX + 0.5 + (Math.random()-0.5)*0.2, worldY + 0.2, (Math.random()-0.5)*0.4, -0.5, "#00d2d3", 2.5, 700);
      }
    } else {
      strideY = Math.sin(ts / 650) * 1.5;
    }

    const activeSprite = isAdam ? sprites.adam_standing : sprites.eve_standing;
    if (activeSprite && activeSprite._ok) {
      const figH = Math.max(85, s * 2.15);
      const figW = figH * (activeSprite.width / activeSprite.height);

      g.save();
      g.translate(sx, sy + 18 * figScale);
      g.rotate(workAngle);
      g.drawImage(activeSprite, -figW / 2, -figH + strideY, figW, figH);
      g.restore();

      figureTopY = (sy + 18 * figScale) - figH + strideY;
    }
  }

  // RPG Minimal Telemetry Overhead Bar & Name
  const barW = 60 * figScale;
  const barH = 5 * figScale;
  const barX = sx - barW / 2;
  const barY = figureTopY - 18;

  // Name Label
  g.font = "700 11px 'Plus Jakarta Sans', sans-serif";
  g.textAlign = "center";
  g.fillStyle = isDowned ? "#ff6b81" : "#ffffff";
  g.fillText(name, sx, barY - 4);

  // HP Bar Frame
  g.fillStyle = "rgba(4, 8, 16, 0.85)";
  g.fillRect(barX, barY, barW, barH);
  g.strokeStyle = "rgba(255, 255, 255, 0.25)";
  g.lineWidth = 1;
  g.strokeRect(barX, barY, barW, barH);

  // HP Fill
  const hpFill = clamp(vitals.vitality / 12, 0, 1);
  g.fillStyle = isDowned ? "#ff4757" : (hpFill > 0.4 ? "#2ed573" : "#ffa502");
  g.fillRect(barX + 1, barY + 1, (barW - 2) * hpFill, barH - 2);

  // Action / Comic Speech Bubble (Positioned dynamically above nameplate)
  let bubbleText = act.label;
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
  }

  g.font = "700 10.5px 'Plus Jakarta Sans', sans-serif";
  const tw = g.measureText(`${bubbleIcon} ${bubbleText}`).width;
  const bW = Math.min(tw + 20, cssW - 20);
  const bH = 22;
  const bX = clamp(sx - bW / 2, 10, cssW - bW - 10);
  const bY = barY - bH - 12 - (idx * (bH + 6));

  // Speech Bubble Pointer
  const tailX = clamp(sx, bX + 10, bX + bW - 10);
  g.fillStyle = isDowned ? "rgba(42, 10, 18, 0.95)" : "rgba(8, 14, 24, 0.95)";
  g.beginPath();
  g.moveTo(tailX - 4, bY + bH);
  g.lineTo(tailX, bY + bH + 5);
  g.lineTo(tailX + 4, bY + bH);
  g.closePath();
  g.fill();

  // Glass Badge Box
  g.fillRect(bX, bY, bW, bH);
  g.strokeStyle = isDowned ? "rgba(255, 71, 87, 0.85)" : (isAdam ? "rgba(0, 210, 211, 0.8)" : "rgba(254, 202, 87, 0.8)");
  g.lineWidth = 1.2;
  g.strokeRect(bX, bY, bW, bH);

  g.fillStyle = isDowned ? "#ffb8b8" : "#ffffff";
  g.textAlign = "left";
  g.fillText(`${bubbleIcon} ${bubbleText}`, bX + 8, bY + 15);

  g.restore();
}

// Master Canvas Drawing Loop
function drawFrame(ts) {
  if (panel.clientWidth !== cssW || panel.clientHeight !== cssH) resize();
  const g = ctx;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Deep Midnight Void
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
    g.globalAlpha = 0.22;
    g.drawImage(baseImg, -dx, -dy, dw, dh);
    g.restore();
  }

  // Continuous Organic Terrain Layer
  g.imageSmoothingEnabled = true;
  g.drawImage(terrain, -dx, -dy, dw, dh);

  // Animated Water Shoreline Caustics
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
  });

  const tl = screenToWorld(0, 0), br = screenToWorld(cssW, cssH);
  const vx0 = Math.floor(tl.x - 1), vx1 = Math.ceil(br.x + 1);
  const vy0 = Math.floor(tl.y - 1), vy1 = Math.ceil(br.y + 1);

  // Environmental Scenery Props (Trees, Rocks, Berry Bushes with Drop Shadows)
  if (s >= 8) {
    tiles.forEach(t => {
      const c = t.coordinates; if (!c || t.water) return;
      if (c.x < vx0 || c.x > vx1 || c.y < vy0 || c.y > vy1) return;

      const sx = (c.x + 0.5 - origin.x) * s;
      const sy = (c.y + 0.5 - origin.y) * s;
      const seed = ((c.x * 73856093) ^ (c.y * 19349663)) & 0xffff;
      const b = String(t.biome || "").toLowerCase();

      // Forest & Woodland Biomes: Rich Tree Groves
      if (b.includes("forest") || b.includes("woodland") || b.includes("thicket")) {
        if (sprites.tree_cluster && sprites.tree_cluster._ok) {
          const treeW = Math.max(38, s * 1.55) * (0.85 + (seed % 30) / 100);
          const treeH = treeW * (sprites.tree_cluster.height / sprites.tree_cluster.width);
          const swayX = Math.sin(ts / 800 + c.x * 1.8) * (1.2 * s / 16);

          // Soft Tree Drop Shadow
          g.fillStyle = "rgba(0, 8, 16, 0.42)";
          g.beginPath();
          g.ellipse(sx, sy + s * 0.15, treeW * 0.4, treeW * 0.18, 0, 0, Math.PI * 2);
          g.fill();

          g.drawImage(sprites.tree_cluster, sx - treeW / 2 + swayX, sy - treeH * 0.85, treeW, treeH);
        }
      }
      // Rocky / Highland Biomes: Weathered Granite Boulders
      else if (b.includes("hill") || b.includes("highland") || b.includes("cliff")) {
        if (sprites.boulder_rock && sprites.boulder_rock._ok) {
          const rockW = Math.max(26, s * 1.1) * (0.85 + (seed % 25) / 100);
          const rockH = rockW * (sprites.boulder_rock.height / sprites.boulder_rock.width);

          // Soft Rock Drop Shadow
          g.fillStyle = "rgba(0, 8, 16, 0.48)";
          g.beginPath();
          g.ellipse(sx, sy + s * 0.1, rockW * 0.45, rockW * 0.2, 0, 0, Math.PI * 2);
          g.fill();

          g.drawImage(sprites.boulder_rock, sx - rockW / 2, sy - rockH * 0.8, rockW, rockH);
        }
      }

      // Sustenance Flora: Wild Berry Bushes
      if (t.resources && t.resources.some(r => /berry|root|mushroom/.test(r))) {
        if (sprites.berry_bush && sprites.berry_bush._ok) {
          const bushW = Math.max(24, s * 0.95);
          const bushH = bushW * (sprites.berry_bush.height / sprites.berry_bush.width);

          // Bush Shadow
          g.fillStyle = "rgba(0, 8, 16, 0.35)";
          g.beginPath();
          g.ellipse(sx + s * 0.2, sy + s * 0.1, bushW * 0.4, bushW * 0.16, 0, 0, Math.PI * 2);
          g.fill();

          g.drawImage(sprites.berry_bush, sx + s * 0.2 - bushW / 2, sy - bushH * 0.72, bushW, bushH);
        }
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
      const fireGlow = g.createRadialGradient(sx, sy, 0, sx, sy, s * 1.8);
      fireGlow.addColorStop(0, "rgba(255, 140, 20, 0.52)");
      fireGlow.addColorStop(0.5, "rgba(255, 80, 10, 0.22)");
      fireGlow.addColorStop(1, "rgba(255, 50, 0, 0)");
      g.fillStyle = fireGlow;
      g.beginPath(); g.arc(sx, sy, s * 1.8, 0, Math.PI * 2); g.fill();

      if (sprites.campfire && sprites.campfire._ok) {
        const flamePulse = 1 + Math.sin(ts / 140) * 0.05;
        const fireW = Math.max(28, s * 0.98) * flamePulse;
        const fireH = fireW * (sprites.campfire.height / sprites.campfire.width);
        g.drawImage(sprites.campfire, sx - fireW / 2, sy - fireH * 0.65, fireW, fireH);
      }
    } else if (cat === "landmark") {
      if (sprites.landmark && sprites.landmark._ok) {
        const lmH = Math.max(38, s * 1.35);
        const lmW = lmH * (sprites.landmark.width / sprites.landmark.height);

        // Monolith Shadow
        g.fillStyle = "rgba(0, 8, 16, 0.55)";
        g.beginPath();
        g.ellipse(sx, sy + s * 0.15, lmW * 0.45, lmW * 0.22, 0, 0, Math.PI * 2);
        g.fill();

        g.drawImage(sprites.landmark, sx - lmW / 2, sy - lmH * 0.75, lmW, lmH);
      }
    }
  }

  // Camera Tracking Glide
  if (trackedAgentRef) {
    const pair = PAIRS[selectedPair] || {};
    const tl = pair.position_timeline || {};
    const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];
    const tid = pos[trackedAgentRef];
    const t = tiles.get(tid);
    if (t && t.coordinates) {
      view.cx += (t.coordinates.x + 0.5 - view.cx) * 0.08;
      view.cy += (t.coordinates.y + 0.5 - view.cy) * 0.08;
    }
  }

  // Living Characters with Movement Interpolation
  const tileAgentCounts = new Map();
  const tileAgentIndices = new Map();
  for (const a of agentsAll) {
    tileAgentCounts.set(a.tileId, (tileAgentCounts.get(a.tileId) || 0) + 1);
  }

  for (let i = 0; i < agentsAll.length; i++) {
    const a = agentsAll[i];
    const anim = getAgentWorldPos(a.pair, a.ref, currentHb, 1);
    const count = tileAgentCounts.get(a.tileId) || 1;
    const idx = tileAgentIndices.get(a.tileId) || 0;
    tileAgentIndices.set(a.tileId, idx + 1);

    const sep = count > 1 ? (idx - (count - 1) / 2) * Math.max(48, s * 0.9) : 0;
    drawCharacter(g, a, anim.x + sep / s, anim.y, s, ts, idx);
  }

  // Dynamic World Particles (Harvest leaves, embers, dust)
  for (let i = worldParticles.length - 1; i >= 0; i--) {
    const p = worldParticles[i];
    const age = ts - p.startTs;
    if (age > p.life) { worldParticles.splice(i, 1); continue; }
    const alpha = 1 - age / p.life;
    const px = (p.x - origin.x) * s + p.vx * (age / 16);
    const py = (p.y - origin.y) * s + p.vy * (age / 16);
    g.fillStyle = p.col;
    g.globalAlpha = alpha;
    g.beginPath();
    g.arc(px, py, p.size * (s / 16), 0, Math.PI * 2);
    g.fill();
    g.globalAlpha = 1;
  }

  // Floating Action / Loot Texts
  for (let i = floatingTexts.length - 1; i >= 0; i--) {
    const ft = floatingTexts[i];
    const age = ts - ft.startTs;
    if (age > ft.dur) { floatingTexts.splice(i, 1); continue; }
    const prog = age / ft.dur;
    const yOff = prog * 42;
    g.save();
    g.font = "700 12px 'Plus Jakarta Sans', sans-serif";
    g.textAlign = "center";
    g.fillStyle = ft.col;
    g.globalAlpha = Math.sin(prog * Math.PI);
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
    const sy = (c.y + 0.5 - origin.y) * view.scale - 35;

    const type = String(act.type || "").toLowerCase();
    if (type === "gather") {
      const res = act.resource ? act.resource.replace(/_/g, " ") : "wild flora";
      const icon = /berry/.test(res) ? "🫐" : (/wood/.test(res) ? "🪵" : (/clay/.test(res) ? "🏺" : "🪨"));
      spawnFloatingText(`+${icon} ${res.toUpperCase()}`, sx, sy, "#2ed573");
    } else if (type === "eat") {
      spawnFloatingText(`+❤️ VITALITY RESTORED (+15 FOOD)`, sx, sy, "#00d2d3");
    } else if (type === "build" || type === "create_public_object") {
      spawnFloatingText(`🔨 CONSTRUCTING STRUCTURE`, sx, sy, "#feca57");
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
  if (act.type === "eat") {
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

function renderBiometrics() {'''

idx1 = html.find(target_start)
idx2 = html.find(target_end)
assert idx1 != -1 and idx2 != -1, f"Targets not found: idx1={idx1}, idx2={idx2}"
html = html[:idx1] + replacement_code + html[idx2 + len(target_end):]

# Also update renderBiometrics to add the "Track Cam 🎥" button
old_sector_row = """      <div class="sector-row">
        <span>SECTOR: ${esc(tileId)}</span>
        <span class="sector-cta" onclick="focusTile('${esc(tileId)}')">PULSE ON MAP ↗</span>
      </div>"""

new_sector_row = """      <div class="sector-row">
        <span>SECTOR: ${esc(tileId)}</span>
        <div style="display:flex;gap:6px;align-items:center;">
          <button class="btn-track ${trackedAgentRef === ref ? 'active' : ''}" onclick="toggleTrackAgent('${ref}')">
            ${trackedAgentRef === ref ? '🎥 TRACKING' : '🎥 TRACK'}
          </button>
          <span class="sector-cta" onclick="focusTile('${esc(tileId)}')">PULSE ↗</span>
        </div>
      </div>"""

assert old_sector_row in html, "old_sector_row not found"
html = html.replace(old_sector_row, new_sector_row, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

print("Pass 3 applied successfully: Scenery, Living Actions, Particles & Camera Tracking installed.")
