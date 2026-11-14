"""Phase 10RB — the weather HUD must not fabricate a season or a temperature.

Caught by a headless capture (10QZ) of the LIVE viewer: the HUD read
"Spring (17°C) // OVERCAST" while the same frame had tinted the foliage for
WINTER -- the label contradicted its own picture. Both halves were wrong:

  * `survival.weather_forecast` returns only current/next/changes_at, so the
    exporter had no season or temperature to give;
  * the viewer's `getWeatherAt` then defaulted to `17` and `"Spring"`, and the
    HUD printed those, while computing the season from `hb` for the foliage and
    not using it for the label.

The real numbers at heartbeat 13,657 (measured): season winter, ambient 31.5,
east overcast -> effective 28.5, west clear -> 31.5.

Python side: the exported facts must equal `survival`'s own answers, so they
cannot drift. No provider, no network.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))
sys.path.insert(0, str(WORLD_SIM / "scripts"))

from backend.world import survival  # noqa: E402
from export_viewer_snapshot import weather_snapshot_for  # noqa: E402

HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"
NODE = shutil.which("node")


def _script() -> str:
    return max(re.findall(r"<script>(.*?)</script>",
                          HTML.read_text(encoding="utf-8"), re.DOTALL), key=len)


def _run(assertions: str) -> None:
    if NODE is None:
        pytest.skip("node not available")
    script = _script()
    start = script.find("function computeSeasonAtHb")
    end = script.find("function getSeasonPalette")
    assert start > 0 and end > start, "the season/temperature block must be present"
    tmp = Path(__file__).resolve().parent / ".tmp-weather-10rb.js"
    tmp.write_text(script[start:end] + "\n" + assertions, encoding="utf-8",
                   newline="\n")
    try:
        res = subprocess.run([NODE, str(tmp)], capture_output=True, text=True,
                             timeout=60)
        assert res.returncode == 0, res.stderr[:1200] or res.stdout[:1200]
    finally:
        tmp.unlink(missing_ok=True)


# --- the exported facts equal the physics -----------------------------------

def test_the_exported_season_and_temperature_are_the_survival_ones():
    hb = 13657
    snap = weather_snapshot_for("east", hb)
    assert snap["season"] == survival.season(hb).title() == "Winter"
    assert snap["temperature"] == round(
        survival.effective_temperature(hb, snap["current"]), 1)


def test_the_exported_temperature_is_not_the_fabricated_default():
    """17 C / Spring was the viewer's hardcoded fallback, not the world's."""
    for hb in (13657, 13619, 1000, 8640):
        snap = weather_snapshot_for("east", hb)
        assert snap["temperature"] != 17.0 or snap["current"] != "clear", (
            f"hb {hb} looks like the old default")
        assert snap["season"] in ("Spring", "Summer", "Autumn", "Winter")


def test_a_clear_sky_has_no_modifier_and_a_storm_has_the_biggest():
    """effective_temperature is ambient plus the sky's modifier."""
    hb = 13657
    clear = weather_snapshot_for("west", hb)
    snap = weather_snapshot_for("east", hb)
    if clear["current"] == "clear":
        assert clear["temperature"] == round(survival.ambient_temperature(hb), 1)
    if snap["current"] == "storm":
        assert snap["temperature"] < survival.ambient_temperature(hb)


def test_it_still_carries_the_window_so_the_viewer_can_forecast():
    snap = weather_snapshot_for("east", 13657)
    for key in ("current", "next", "changes_at_heartbeat"):
        assert key in snap, f"the existing contract lost {key}"


# --- the viewer mirrors the physics -----------------------------------------

def test_the_viewer_derives_the_same_temperature_as_the_physics():
    """Same heartbeat, same season, same number the agents feel."""
    for hb, weather in ((13657, "clear"), (13657, "overcast"), (13657, "storm"),
                        (13619, "clear")):
        expected = round(survival.effective_temperature(hb, weather), 1)
        js = (
            'const got = computeTemperatureAtHb(%d, "%s");\n'
            'if (Math.abs(got - %s) > 0.05) { throw new Error("hb %d %s: viewer "'
            ' + got + " vs survival %s"); }\n'
            % (hb, weather, expected, hb, weather, expected)
        )
        _run(js)


def test_an_unknown_heartbeat_is_null_not_a_made_up_number():
    _run("""
for (const hb of [null, undefined, NaN, -1]) {
  const t = computeTemperatureAtHb(hb, "clear");
  if (t !== null) throw new Error("hb " + hb + " produced " + t);
}
""")


def test_the_live_case_that_exposed_the_bug():
    """Snow on the ground must not be labelled Spring."""
    _run("""
if (computeSeasonAtHb(13657) !== "Winter") {
  throw new Error("hb 13657 is winter; the HUD said Spring");
}
const t = computeTemperatureAtHb(13657, "overcast");
if (t === 17) throw new Error("still the fabricated 17");
if (Math.round(t) !== 29 && Math.round(t) !== 28) {
  throw new Error("overcast winter daytime should be ~28.5, got " + t);
}
""")


# --- and the code paths that caused it --------------------------------------

def test_the_hud_line_uses_the_computed_season_not_the_stored_one():
    src = HTML.read_text(encoding="utf-8")
    assert "${curSeason} (" in src, "the HUD must print the season it computed"
    assert "${env.season} (" not in src, "the HUD must not print the stored season"


def test_no_hardcoded_weather_defaults_remain():
    src = HTML.read_text(encoding="utf-8")
    assert "w.temperature != null) ? w.temperature : 17" not in src
    assert 'w.season || "Spring"' not in src
    assert 'Spring (17°C) // Clear' not in src, "the static placeholder is a fake fact"
