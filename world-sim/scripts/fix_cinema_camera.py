from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "viewer" / "index.html"

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    text = f.read()

target = """  // Cinematic Director Camera Glide & Subtitle Feed
  if (isCinematic) {
    let avgX = 0, avgY = 0, charCount = 0;
    let mainQuote = "";
    for (const a of agentsAll) {"""

replacement = """  // Cinematic Director Camera Glide & Subtitle Feed (Focuses on Active Civilization)
  if (isCinematic) {
    let avgX = 0, avgY = 0, charCount = 0;
    let mainQuote = "";
    const activeAgents = agentsAll.filter(a => a.pair === selectedPair);
    for (const a of activeAgents) {"""

assert target in text, "target not found"
text = text.replace(target, replacement, 1)

# Also ensure smooth cinematic zoom is 15.5, not 19.0 so we see the full landscape context around the agents
text = text.replace("view.scale += (19.0 - view.scale) * 0.02;", "view.scale += (15.5 - view.scale) * 0.04;")

# Also when toggling cinema mode on, immediately snap camera to active civilization center so there is no awkward pan delay
target_toggle = """  if (isCinematic) {
    overlay.style.display = "flex";
    sidebar.style.display = "none";
    pbBar.style.bottom = "92px";
    if (btn) btn.classList.add("active");
    if (!isPlaying) togglePlay();
  }"""

replacement_toggle = """  if (isCinematic) {
    overlay.style.display = "flex";
    sidebar.style.display = "none";
    pbBar.style.bottom = "92px";
    if (btn) btn.classList.add("active");
    // Center camera on active civilization agents immediately
    const pair = PAIRS[selectedPair] || {};
    const tl = pair.position_timeline || {};
    const pos = (playbackMode === "live" || !tl[currentHb]) ? (pair.current_positions || {}) : tl[currentHb];
    let ax = 0, ay = 0, n = 0;
    for (const tid of Object.values(pos)) {
      const t = tiles.get(tid);
      if (t && t.coordinates) { ax += t.coordinates.x; ay += t.coordinates.y; n++; }
    }
    if (n) { view.cx = ax / n + 0.5; view.cy = ay / n + 0.5; view.scale = 15.5; }
    if (!isPlaying) togglePlay();
  }"""

assert target_toggle in text, "target_toggle not found"
text = text.replace(target_toggle, replacement_toggle, 1)

with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

print("Cinematic camera focus fixed to active civilization.")
