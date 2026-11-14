"""Phase 10QR - the ground reads as ground: grass, loose stones, riverbank reeds.

Operator, 2026-11-14: "what else can we fix to make things look better? its
kinda plain in general".

This layer is terrain-driven (it IS the ground), so it keys off terr/biome and
the water of the neighbouring tile, not resources. Two measured facts are
pinned here because they are the whole design:

  * the scenery loop skips water tiles, so reeds must sit on the BANK;
  * ground cover carries NO shadow decal - at 1,359 props on one continent a
    decal mesh each would double the object count for nothing a tuft needs.

Densities were chosen by measurement against the live snapshot
(ground_count2.py): grass 1-in-3, stones 1-in-11, reeds 1-in-3 on banks,
explored-vicinity only -> 1,359 east / 339 west, under a 1,500 cap that
therefore never binds. A binding cap truncates in scan order.

These tests run the pure planners in node: no browser, no GPU.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"

NODE = shutil.which("node")


def _script() -> str:
    html = HTML.read_text(encoding="utf-8")
    return max(re.findall(r"<script>(.*?)</script>", html, re.DOTALL), key=len)


def _creators(script: str) -> str:
    start = script.find("// Phase 10QR: ground cover.")
    end = script.find("// Which ground cover a tile's own terrain calls for")
    assert start > 0 and end > start, "the 10QR creator block must be present"
    return script[start:end]


def _planners(script: str) -> str:
    start = script.find("// Which ground cover a tile's own terrain calls for")
    end = script.find("function computeMountainPeakScale")
    assert start > 0 and end > start, "the 10QR planner block must be present"
    return script[start:end]


def _run(assertions: str) -> None:
    if NODE is None:
        pytest.skip("node not available")
    script = _script()
    harness = (
        "const propTextures = new Proxy({}, { get: (t, k) => 'tex:' + String(k) });\n"
        "const _made = [];\n"
        "function createGroundedProp(tex, width, height, x, z, h, shadowRx,\n"
        "                            shadowRz, sink, tintHex) {\n"
        "  _made.push({ tex, width, height, x, z, h, shadowRx, shadowRz });\n"
        "  return { userData: {} };\n"
        "}\n"
        + _creators(script)
        + _planners(script)
        + "\n"
        + assertions
    )
    tmp = Path(__file__).resolve().parent / ".tmp-ground-10qr.js"
    tmp.write_text(harness, encoding="utf-8", newline="\n")
    try:
        res = subprocess.run([NODE, str(tmp)], capture_output=True, text=True,
                             timeout=60)
        assert res.returncode == 0, res.stderr[:1500] or res.stdout[:1500]
    finally:
        tmp.unlink(missing_ok=True)


def test_grass_covers_the_grassy_terrain_it_describes():
    _run("""
for (const [t, b] of [["grassland", "warm_coast"], ["hill", "temperate_hills"],
                      ["forest", "dense_woodland"], ["grassland", "temperate_valley"]]) {
  const p = groundCoverKindFor(t, b, false, 3);   // 3 % 3 === 0
  if (!p || p.kind !== "grass") {
    throw new Error(t + "/" + b + " -> " + JSON.stringify(p));
  }
  if (p.n < 1 || p.n > 2) throw new Error("grass clump size " + p.n);
}
""")


def test_reeds_go_on_the_bank_not_in_the_water():
    """The loop skips water tiles, so bankWater is the only way reeds appear."""
    _run("""
const p = groundCoverKindFor("grassland", "warm_coast", true, 3);
if (!p || p.kind !== "reeds") throw new Error("bank -> " + JSON.stringify(p));
// and without a water neighbour it is plain grass, never reeds
const q = groundCoverKindFor("grassland", "warm_coast", false, 3);
if (!q || q.kind !== "grass") throw new Error("dry bank -> " + JSON.stringify(q));
""")


def test_stones_cover_the_rocky_terrain():
    _run("""
for (const t of ["mountain", "hill", "highland"]) {
  const p = groundCoverKindFor(t, "highland", false, 11);   // 11 % 11 === 0
  if (!p || p.kind !== "stones") throw new Error(t + " -> " + JSON.stringify(p));
}
""")


def test_no_cover_is_placed_on_the_sea_or_on_nothing():
    _run("""
for (const [t, b] of [["ocean", "open_sea"], ["ocean", ""], ["", ""]]) {
  if (groundCoverKindFor(t, b, false, 3) !== null) {
    throw new Error(t + "/" + b + " should place nothing");
  }
}
// a bank beside water is still not cover if the tile is sea
if (groundCoverKindFor("ocean", "open_sea", true, 3) !== null) {
  throw new Error("sea bank placed cover");
}
""")


def test_density_is_deterministic_and_thin():
    _run("""
// grass is 1-in-3 on grass tiles: two of three seeds place nothing
for (const s of [1, 2]) {
  if (groundCoverKindFor("grassland", "warm_coast", false, s) !== null) {
    throw new Error("grass at seed " + s + " should place nothing");
  }
}
const a = groundCoverKindFor("grassland", "warm_coast", false, 3);
const b = groundCoverKindFor("grassland", "warm_coast", false, 3);
if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error("not deterministic");
""")


def test_ground_cover_carries_no_shadow_decal():
    """Measured design: one sprite per prop, not a sprite plus a shadow mesh."""
    _run("""
for (const kind of ["grass", "stones", "reeds"]) {
  _made.length = 0;
  const prop = buildGroundProp(kind, 1, 2, 3, 1.0, 0xffffff);
  if (!prop) throw new Error(kind + " produced no prop");
  if (_made[0].shadowRx !== 0 || _made[0].shadowRz !== 0) {
    throw new Error(kind + " asked for a shadow: " + _made[0].shadowRx + "/" + _made[0].shadowRz);
  }
}
if (buildGroundProp("nonsense", 1, 2, 3, 1, 0) !== null) {
  throw new Error("an unknown kind must not build anything");
}
""")


def test_each_kind_uses_its_own_texture():
    _run("""
const wants = { grass: "grass", stones: "stones", reeds: "reeds" };
for (const [kind, tex] of Object.entries(wants)) {
  _made.length = 0;
  buildGroundProp(kind, 1, 2, 3, 1.0, 0xffffff);
  if (_made[0].tex !== "tex:" + tex) {
    throw new Error(kind + " used " + _made[0].tex);
  }
}
""")


def test_the_cap_is_declared_and_the_loop_counts_against_it():
    script = _script()
    assert "const GROUND_PER_CONTINENT_CAP = 1500;" in script
    assert "let groundPlacedTotal = 0;" in script
    assert "groundPlacedTotal < GROUND_PER_CONTINENT_CAP" in script
    assert "groundPlacedTotal++" in script
    # it is checked BEFORE placing, so it can never be exceeded
    assert "inExploredVicinity && groundPlacedTotal < GROUND_PER_CONTINENT_CAP" in script
