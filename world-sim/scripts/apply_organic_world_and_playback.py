"""Pass 3C: Wire playback deck UI listeners, keyboard shortcuts, focusPair sync, and action character animations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "viewer" / "index.html"

content = HTML_FILE.read_text(encoding="utf-8")

# 1. Update focusPair to synchronize playback timeline with active civilization
target_focus = """function focusPair(pn) {
  selectedPair = pn;
  const pair = PAIRS[pn];
  if (!pair) return;
  const pos = pair.current_positions || {};
  let ax = 0, ay = 0, n = 0;
  for (const tid of Object.values(pos)) {
    const t = tiles.get(tid);
    if (t && t.coordinates) { ax += t.coordinates.x; ay += t.coordinates.y; n++; }
  }
  if (n) animateTo(ax / n, ay / n, 16);
  renderBiometricsTab();
}"""

replacement_focus = """function focusPair(pn) {
  selectedPair = pn;
  const pair = PAIRS[pn];
  if (!pair) return;

  const hbs = timelineHbs[pn] || [];
  if (hbs.length) {
    minHb = hbs[0];
    maxHb = hbs[hbs.length - 1];
    if (playbackMode === "live") currentHb = maxHb;
    else currentHb = clamp(currentHb, minHb, maxHb);
  }

  const pos = getActivePositions(pn, currentHb);
  let ax = 0, ay = 0, n = 0;
  for (const tid of Object.values(pos)) {
    const t = tiles.get(tid);
    if (t && t.coordinates) { ax += t.coordinates.x; ay += t.coordinates.y; n++; }
  }
  if (n) animateTo(ax / n, ay / n, 16);
  recomputeScene();
  renderBiometricsTab();
}"""

assert target_focus in content, "target_focus not found"
content = content.replace(target_focus, replacement_focus, 1)

# 2. Add event listeners for playback deck and keyboard hotkeys before initialize
target_init = "// Initialize"
idx_init = content.find(target_init)
assert idx_init != -1, "Initialize block not found"

event_listeners_code = """// ---------- Replay Playback Deck Event Listeners ----------
const btnPlay = document.getElementById("pb-play");
if (btnPlay) btnPlay.addEventListener("click", togglePlay);

const btnStart = document.getElementById("pb-start");
if (btnStart) btnStart.addEventListener("click", () => seekHb(minHb));

const btnPrev10 = document.getElementById("pb-prev10");
if (btnPrev10) btnPrev10.addEventListener("click", () => stepHb(-10));

const btnPrev = document.getElementById("pb-prev");
if (btnPrev) btnPrev.addEventListener("click", () => stepHb(-1));

const btnNext = document.getElementById("pb-next");
if (btnNext) btnNext.addEventListener("click", () => stepHb(1));

const btnNext10 = document.getElementById("pb-next10");
if (btnNext10) btnNext10.addEventListener("click", () => stepHb(10));

const btnLive = document.getElementById("pb-live");
if (btnLive) btnLive.addEventListener("click", goToLive);

const slider = document.getElementById("pb-slider");
if (slider) {
  slider.addEventListener("input", e => {
    seekHb(Number(e.target.value));
  });
}

// Speed Pill Selection
document.querySelectorAll("#speed-select .pb-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#speed-select .pb-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    playSpeed = Number(pill.dataset.speed || 2);
  });
});

// Follow Pill Selection
document.querySelectorAll("#follow-select .pb-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll("#follow-select .pb-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    followTarget = pill.dataset.follow || "none";
    drawFrame(performance.now());
  });
});

// Global Keyboard Hotkeys for Replay (Space = Play/Pause, Left/Right = Step)
window.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.code === "Space") {
    e.preventDefault();
    togglePlay();
  } else if (e.code === "ArrowLeft") {
    e.preventDefault();
    stepHb(-1);
  } else if (e.code === "ArrowRight") {
    e.preventDefault();
    stepHb(1);
  }
});

"""

content = content[:idx_init] + event_listeners_code + "\n" + content[idx_init:]

# Ensure strictly LF line endings
content = content.replace("\r\n", "\n")

HTML_FILE.write_text(content, encoding="utf-8", newline="\n")
print("PASS 3C: Playback UI listeners and hotkeys injected successfully.")
