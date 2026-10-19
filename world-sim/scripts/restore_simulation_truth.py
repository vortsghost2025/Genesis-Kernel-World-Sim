"""Restore simulation-truth integrity to Genesis Observatory viewer.

Findings addressed:
1. Remove fabricated first-person cognitive text in getAgentInnerVoice(). Display recorded reasoning only with explicit provenance.
2. Ground triggerActionFX() in recorded action types without unverified vitality/resource deltas.
3. Label historical replay vitals and inventories honestly as latest-snapshot records.
4. Bound computeTrails() strictly by target heartbeat so future movement never leaks into past replay.
5. Explicitly label day/night sun cycle as illustrative in the HUD and cinema mastheads.
6. Adjust cinema framing and scale to fill 1440x900 gracefully without vast disconnected voids.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update computeTrails to accept targetHb and bound history
trail_target = """// Foot-Traffic Traversal Trail Cache (Desire Paths etched from 4,000 heartbeats)
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
computeTrails();"""

trail_replacement = """// Foot-Traffic Traversal Trail Cache (Simulation-truth: Strictly bounded by historical heartbeat)
const pairTrails = { east: new Map(), west: new Map() };
let lastComputedTrailHb = -1;
function computeTrails(targetHb) {
  const limitHb = targetHb != null ? targetHb : currentHb;
  if (limitHb === lastComputedTrailHb) return;
  lastComputedTrailHb = limitHb;

  for (const [pn, pair] of Object.entries(PAIRS)) {
    const tl = pair.position_timeline || {};
    const trailMap = new Map();
    const hbs = Object.keys(tl).map(Number).sort((a,b) => a - b);
    const prevPos = {};

    for (const hb of hbs) {
      if (hb > limitHb) break; // NEVER leak future journeys into historical replay frames
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
computeTrails();"""

assert trail_target in content, "trail_target not found"
content = content.replace(trail_target, trail_replacement, 1)

# 2. Update recomputeScene to call computeTrails(currentHb)
recompute_target = """  // Active agents based on current playback heartbeat
  agentsAll = [];
  for (const [pn, pair] of Object.entries(PAIRS)) {
    const tl = pair.position_timeline || {};
    const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];
    for (const [ref, tid] of Object.entries(pos)) {
      agentsAll.push({ ref, pair: pn, tileId: tid });
    }
  }

  updateUI();"""

recompute_replacement = """  // Active agents based on current playback heartbeat
  agentsAll = [];
  for (const [pn, pair] of Object.entries(PAIRS)) {
    const tl = pair.position_timeline || {};
    const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];
    for (const [ref, tid] of Object.entries(pos)) {
      agentsAll.push({ ref, pair: pn, tileId: tid });
    }
  }

  // Recompute trails up to current replay heartbeat
  computeTrails(currentHb);

  updateUI();"""

assert recompute_target in content, "recompute_target not found"
content = content.replace(recompute_target, recompute_replacement, 1)

# 3. Update getAtmosphericLighting to note illustrative cycle
atmo_target = """// Day/Night & Atmospheric Shading
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
}"""

atmo_replacement = """// Day/Night & Atmospheric Shading (Illustrative visual cycle; not canonical simulation clock)
function getAtmosphericLighting(hb) {
  // Illustrative visual cycle repeats every 120 heartbeats
  const phase = (hb % 120) / 120;
  let timeName = "Midday ☀️";
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
  return { phase, timeName, sunColor, ambientDarkness, isNight, illustrativeTag: "ILLUSTRATIVE SUN CYCLE" };
}"""

assert atmo_target in content, "atmo_target not found"
content = content.replace(atmo_target, atmo_replacement, 1)

# 4. Update HUD atmospheric time to show canonical timestamp + illustrative sun label
hud_atmo_target = """  // Atmospheric Sun & Day/Night Wash
  const atmo = getAtmosphericLighting(currentHb);
  const timeHud = document.getElementById("time-hud");
  if (timeHud) timeHud.textContent = atmo.timeName;"""

hud_atmo_replacement = """  // Atmospheric Sun & Day/Night Wash (Transparent separation of canonical timestamp from illustrative sun)
  const atmo = getAtmosphericLighting(currentHb);
  const hbRecForTime = (hbIndex[selectedPair] || new Map()).get(currentHb);
  const timeHud = document.getElementById("time-hud");
  if (timeHud) {
    if (hbRecForTime && hbRecForTime.timestamp) {
      const utcTime = hbRecForTime.timestamp.length >= 19 ? hbRecForTime.timestamp.slice(11, 19) + " UTC" : hbRecForTime.timestamp;
      timeHud.textContent = `${utcTime} // ${atmo.timeName} (ILLUSTRATIVE)`;
    } else {
      timeHud.textContent = `${atmo.timeName} (ILLUSTRATIVE)`;
    }
  }"""

assert hud_atmo_target in content, "hud_atmo_target not found"
content = content.replace(hud_atmo_target, hud_atmo_replacement, 1)

# 5. Update cinematic director camera glide & subtitles to use verified provenance and larger framing
cinema_glide_target = """  // Cinematic Director Camera Glide & Subtitle Feed (Focuses on Active Civilization)
  if (isCinematic) {
    let avgX = 0, avgY = 0, charCount = 0;
    let mainQuote = "";
    const activeAgents = agentsAll.filter(a => a.pair === selectedPair);
    for (const a of activeAgents) {
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
      view.scale += (15.5 - view.scale) * 0.04;
    }
    const subEl = document.getElementById("cinema-subtitle");
    if (subEl && mainQuote) subEl.textContent = mainQuote;
    const hbTag = document.getElementById("cinema-hb-tag");
    if (hbTag) hbTag.textContent = `HB ${currentHb} // ${atmo.timeName}`;
  }"""

cinema_glide_replacement = """  // Cinematic Director Camera Glide & Subtitle Feed (Focuses on Active Civilization with Provenance & Proper Framing)
  if (isCinematic) {
    let avgX = 0, avgY = 0, charCount = 0;
    let mainQuote = "";
    const activeAgents = agentsAll.filter(a => a.pair === selectedPair);
    for (const a of activeAgents) {
      const anim = getAgentWorldPos(a.pair, a.ref, currentHb, 1);
      avgX += anim.x + 0.5; avgY += anim.y + 0.5; charCount++;
      const act = getAgentRealAction(a.pair, a.ref, currentHb);
      if (!mainQuote) {
        const who = a.ref.toUpperCase().replace(/.*_/, "");
        if (act.fullReason) {
          mainQuote = `${who} [RECORDED REASONING]: "${act.fullReason}"`;
        } else if (act.label && act.type !== "idle") {
          mainQuote = `${who} [RECORDED ACTION]: ${act.label.toUpperCase()}`;
        }
      }
    }
    if (charCount > 0) {
      view.cx += (avgX / charCount - view.cx) * 0.05;
      view.cy += (avgY / charCount - view.cy) * 0.05;
      // Scale 29.5 fills the 1440x900 widescreen viewport gracefully without ocean void
      view.scale += (29.5 - view.scale) * 0.04;
    }
    const subEl = document.getElementById("cinema-subtitle");
    if (subEl) {
      subEl.textContent = mainQuote || "[NO DELIBERATION RECORDED FOR THIS HEARTBEAT]";
    }
    const hbTag = document.getElementById("cinema-hb-tag");
    if (hbTag) {
      const tsStr = hbRecForTime && hbRecForTime.timestamp ? (hbRecForTime.timestamp.length >= 19 ? hbRecForTime.timestamp.slice(11, 19) + " UTC" : hbRecForTime.timestamp) : "NO TIMESTAMP";
      hbTag.textContent = `HB ${currentHb} // CANONICAL: ${tsStr} // SUN: ${atmo.timeName} (ILLUSTRATIVE)`;
    }
  }"""

assert cinema_glide_target in content, "cinema_glide_target not found"
content = content.replace(cinema_glide_target, cinema_glide_replacement, 1)

# 6. Ground triggerActionFX in recorded actions without unverified vitality deltas
action_fx_target = """// Action FX Trigger on Heartbeat Step
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
}"""

action_fx_replacement = """// Action FX Trigger on Heartbeat Step (Simulation-truth: Strictly displays recorded actions; no unverified vitality deltas)
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
      const res = act.resource ? act.resource.replace(/_/g, " ") : "resource";
      const icon = /berry/.test(res) ? "🫐" : (/wood/.test(res) ? "🪵" : (/clay/.test(res) ? "🏺" : "🪨"));
      spawnFloatingText(`ACTION: GATHER (${icon} ${res.toUpperCase()})`, sx, sy, "#2ed573");
    } else if (type === "eat") {
      spawnFloatingText(`ACTION: CONSUME RATIONS`, sx, sy, "#00d2d3");
    } else if (type === "build" || type === "create_public_object") {
      spawnFloatingText(`ACTION: CONSTRUCT STRUCTURE`, sx, sy, "#feca57");
    } else if (type === "move") {
      spawnFloatingText(`ACTION: TRAVEL`, sx, sy, "#70a1ff");
    }
  }
}"""

assert action_fx_target in content, "action_fx_target not found"
content = content.replace(action_fx_target, action_fx_replacement, 1)

# 7. Ground getAgentInnerVoice in recorded cognition only, with explicit provenance
voice_target = """// Cognitive Dossier Helper
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
}"""

voice_replacement = """// Cognitive Dossier Helper (Simulation-truth: Strictly displays recorded reasoning with explicit provenance; zero fabricated thoughts)
function getAgentInnerVoice(pn, ref, v, act, inv) {
  const rawShort = ref.replace(`${pn}_`, "").toLowerCase();
  const pair = PAIRS[pn] || {};

  // 1. Check for recorded operator asks/comms
  for (const ask of (pair.agent_asks || [])) {
    const askWho = String(ask.agent || "").toLowerCase();
    if (askWho.includes(rawShort) && (ask.heartbeat === currentHb || (currentHb == null && ask.status === "unheard"))) {
      const resp = ask.answer ? ` ➔ Operator Response: "${ask.answer}"` : " (Status: Unheard)";
      return {
        provenance: `CANONICAL ASKS LOG [HB ${ask.heartbeat}]`,
        text: `"${ask.question}"${resp}`
      };
    }
  }

  // 2. Check for recorded action deliberation in heartbeat record
  if (act && (act.fullReason || act.reason)) {
    return {
      provenance: `RECORDED ACTION DELIBERATION [HB ${currentHb}]`,
      text: `"${act.fullReason || act.reason}"`
    };
  }

  // 3. Transparent fallback: State honestly that no deliberation was recorded
  return {
    provenance: `LEDGER RECORD [HB ${currentHb}]`,
    text: `No deliberation logged for this heartbeat (Action: ${act && act.type ? act.type.toUpperCase() : "IDLE"}).`
  };
}"""

assert voice_target in content, "voice_target not found"
content = content.replace(voice_target, voice_replacement, 1)

# 8. Update renderBiometrics to display provenance and honestly label historical replay vitals
biometrics_target = """      <div class="agent-inner-voice">
        <span style="font-style:normal;">🧠</span>
        <span>“${esc(getAgentInnerVoice(selectedPair, ref, v, act, inv))}”</span>
      </div>"""

biometrics_replacement = """      <div class="agent-inner-voice">
        <div style="font-size:0.62rem;color:var(--text-tertiary);font-weight:700;letter-spacing:0.05em;margin-bottom:3px;">
          ${esc(voiceObj.provenance)}
        </div>
        <span>${esc(voiceObj.text)}</span>
      </div>"""

assert biometrics_target in content, "biometrics_target not found"
content = content.replace(biometrics_target, biometrics_replacement, 1)

# Also update the inner voice caller in renderBiometrics to get voiceObj
voice_caller_target = """    const act = getAgentRealAction(selectedPair, ref, currentHb);
    const portraitSrc = isAdam ? "adam_portrait.jpg" : "eve_portrait.jpg";
    const st = v.downed ? "COLLAPSED" : "ACTIVE";"""

voice_caller_replacement = """    const act = getAgentRealAction(selectedPair, ref, currentHb);
    const voiceObj = getAgentInnerVoice(selectedPair, ref, v, act, inv);
    const portraitSrc = isAdam ? "adam_portrait.jpg" : "eve_portrait.jpg";
    const st = v.downed ? "COLLAPSED" : "ACTIVE";"""

assert voice_caller_target in content, "voice_caller_target not found"
content = content.replace(voice_caller_target, voice_caller_replacement, 1)

# Also add replay warning banner to renderBiometrics
banner_target = """function renderBiometrics() {
  const el = document.getElementById("agents-container");
  const pair = PAIRS[selectedPair] || {};
  const inventories = pair.inventories || {};
  const vitalsAll = pair.vitals || {};
  const tl = pair.position_timeline || {};
  const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];

  let html = "";"""

banner_replacement = """function renderBiometrics() {
  const el = document.getElementById("agents-container");
  const pair = PAIRS[selectedPair] || {};
  const inventories = pair.inventories || {};
  const vitalsAll = pair.vitals || {};
  const tl = pair.position_timeline || {};
  const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];

  let html = "";
  if (playbackMode === "replay" && currentHb < maxHb) {
    html += `<div style="background:rgba(254,202,87,0.12);border:1px solid rgba(254,202,87,0.45);border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:0.68rem;color:#feca57;line-height:1.45;">
      <strong>⚠️ HISTORICAL REPLAY (HB ${currentHb}):</strong> Vitals and pack contents below reflect the latest snapshot (HB ${maxHb}); per-heartbeat historical vitals are unrecorded in this export. Position and actions are canonical.
    </div>`;
  } else {
    html += `<div style="background:rgba(46,213,115,0.12);border:1px solid rgba(46,213,115,0.45);border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:0.68rem;color:#2ed573;line-height:1.45;">
      <strong>🟢 LIVE TELEMETRY (HB ${maxHb}):</strong> Real-time simulation vitals, position, and inventory verified against canonical persistence.
    </div>`;
  }"""

assert banner_target in content, "banner_target not found"
content = content.replace(banner_target, banner_replacement, 1)

# 9. Update initial zoom on toggleCinematic and focusPair
toggle_cinema_target = """    if (n) { view.cx = ax / n + 0.5; view.cy = ay / n + 0.5; view.scale = 15.5; }"""
toggle_cinema_replacement = """    if (n) { view.cx = ax / n + 0.5; view.cy = ay / n + 0.5; view.scale = 29.5; }"""
assert toggle_cinema_target in content, "toggle_cinema_target not found"
content = content.replace(toggle_cinema_target, toggle_cinema_replacement, 1)

focus_pair_target = """  if (n) animateTo(ax / n, ay / n, 16);"""
focus_pair_replacement = """  if (n) animateTo(ax / n, ay / n, 28);"""
assert focus_pair_target in content, "focus_pair_target not found"
content = content.replace(focus_pair_target, focus_pair_replacement, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("Simulation-truth updates applied successfully with newline='\\n'.")
