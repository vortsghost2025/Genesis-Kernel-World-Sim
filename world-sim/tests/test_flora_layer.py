"""Phase 10QP - the world's flora, fruit and small life are drawn.

Operator, 2026-11-14: "its kinda plain in general no bugs or birds flowers
fruits veggies. i feel like its missing a ton of things that are world things."

The world's own true_map carries, per tile, the resources that were there.
Measured this hour across the known tiles the viewer already loads:

  fiber_plants 159, mushrooms 76, nuts 75, edible_roots 72, wild_apples 28,
  flint 24, fish 19, wild_grain 18, salt 15, iron_ore 15, shellfish 11,
  honeycomb 8

of which the picture drew: wild_apples and fiber_plants AS A BERRY BUSH,
iron_ore and flint AS A GENERIC BOULDER, and mushrooms, nuts, roots, grain,
salt, shellfish, honeycomb and fish as NOTHING AT ALL.

These tests run the pure planners in node against the extracted source, so
they need no browser and no GPU. They pin the classification and the density
rule rather than a picture.
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
    start = script.find("// Phase 10QP: one creator per kind")
    end = script.find("// Phase 10QP: which flora kind")
    assert start > 0 and end > start, "the 10QP creator block must be present"
    return script[start:end]


def _planners(script: str) -> str:
    start = script.find("// Phase 10QP: which flora kind")
    end = script.find("function computeMountainPeakScale")
    assert start > 0 and end > start, "the 10QP planner block must be present"
    return script[start:end]


def _run(assertions: str) -> None:
    if NODE is None:
        pytest.skip("node not available")
    script = _script()
    harness = (
        "const propTextures = new Proxy({}, { get: (t, k) => 'tex:' + String(k) });\n"
        "const _made = [];\n"
        "function createGroundedProp(tex, width, height, x, z, h) {\n"
        "  _made.push({ tex, width, height, x, z, h });\n"
        "  return { position: { set() {} }, userData: {} };\n"
        "}\n"
        + _creators(script)
        + _planners(script)
        + "\n"
        + assertions
    )
    tmp = Path(__file__).resolve().parent / ".tmp-flora-10qp.js"
    tmp.write_text(harness, encoding="utf-8", newline="\n")
    try:
        res = subprocess.run([NODE, str(tmp)], capture_output=True, text=True,
                             timeout=60)
        assert res.returncode == 0, res.stderr[:1500] or res.stdout[:1500]
    finally:
        tmp.unlink(missing_ok=True)


def test_every_kind_the_world_holds_has_a_builder_and_a_texture():
    """The eleven undrawn things the census found are each drawable."""
    _run("""
const wants = {
  mushroom: "mushroom", flower: "flower", wheat: "wheat", roots: "roots",
  nut: "nutBush", apple: "appleTree", hive: "beehive", salt: "salt",
  ore: "ore", fish: "fish", shells: "shells",
};
for (const [kind, tex] of Object.entries(wants)) {
  _made.length = 0;
  const prop = buildFloraProp(kind, 1, 2, 3, 1.0, 0xffffff);
  if (!prop) throw new Error(kind + " produced no prop");
  if (_made[0].tex !== "tex:" + tex) {
    throw new Error(kind + " used " + _made[0].tex + ", wanted tex:" + tex);
  }
  if (!(prop.userData instanceof Object)) throw new Error(kind + " no userData");
}
if (buildFloraProp("nonsense", 1, 2, 3, 1, 0) !== null) {
  throw new Error("an unknown kind must not build anything");
}
""")


def test_a_tile_of_mushrooms_gets_mushrooms_not_a_berry_bush():
    """The exact replacement: this tile held mushrooms and drew nothing."""
    _run("""
const p = floraKindFor(["stone", "mushrooms"], 4);   // 4 % 2 === 0
if (!p || p.kind !== "mushroom") throw new Error("got " + JSON.stringify(p));
if (p.n < 1 || p.n > 3) throw new Error("mushroom patch size " + p.n);
""")


def test_apples_are_apple_trees_not_berry_bushes():
    """Measured defect: `res.includes("apples")` drew a BERRY BUSH."""
    _run("""
const p = floraKindFor(["wild_apples"], 6);   // 6 % 3 === 0
if (!p || p.kind !== "apple") throw new Error("got " + JSON.stringify(p));
""")


def test_ore_tiles_draw_ore_not_a_generic_boulder():
    _run("""
const iron = floraKindFor(["iron_ore"], 9);    // 9 % 3 === 0
if (!iron || iron.kind !== "ore") throw new Error("iron -> " + JSON.stringify(iron));
const flint = floraKindFor(["flint"], 8);      // 8 % 4 === 0
if (!flint || flint.kind !== "ore") throw new Error("flint -> " + JSON.stringify(flint));
""")


def test_the_density_rule_is_deterministic_and_gated():
    """A tile with the resource but the wrong seed places nothing, and the
    same seed always decides the same way -- the layer is reproducible."""
    _run("""
// fiber is the common one: 1 in 4 tiles, not 1 in 2, so flowers cannot eat
// the whole continent cap and starve the rare kinds.
for (const s of [1, 2, 3]) {
  if (floraKindFor(["fiber_plants"], s) !== null) {
    throw new Error("fiber at seed " + s + " should place nothing");
  }
}
const a = floraKindFor(["fiber_plants"], 0);
const b = floraKindFor(["fiber_plants"], 0);
if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error("not deterministic");
if (!a || a.kind !== "flower") throw new Error("seed 0 -> " + JSON.stringify(a));
// a tile with nothing living on it draws nothing
if (floraKindFor(["stone", "wood"], 3) !== null) {
  throw new Error("stone and wood are not flora");
}
if (floraKindFor([], 0) !== null) throw new Error("empty tile drew something");
""")


def test_water_life_is_placed_on_the_tiles_that_hold_it():
    _run("""
const fish = floraKindFor(["fish"], 8);          // 8 % 2 === 0
if (!fish || fish.kind !== "fish") throw new Error("fish -> " + JSON.stringify(fish));
if (fish.n < 1 || fish.n > 3) throw new Error("shoal size " + fish.n);
const shells = floraKindFor(["shellfish"], 8);
if (!shells || shells.kind !== "shells") throw new Error("shells -> " + JSON.stringify(shells));
""")


def test_the_common_kinds_cannot_starve_the_rare_ones():
    """The cap is a safety net: flowers are the most common flora, and if they
    were denser than the rare kinds the continent cap would truncate the map in
    scan order. Measured: flowers 1-in-4, mushrooms 1-in-2."""
    _run("""
const flowerTile = floraKindFor(["fiber_plants"], 0);   // 0 % 4 === 0
const mushroomTile = floraKindFor(["mushrooms", "fiber_plants"], 2); // 2 % 2 === 0
if (!flowerTile || flowerTile.kind !== "flower") throw new Error("flower missing");
// a tile with BOTH must prefer the rarer kind
if (!mushroomTile || mushroomTile.kind !== "mushroom") {
  throw new Error("rarer kind did not win: " + JSON.stringify(mushroomTile));
}
""")


def test_the_cap_is_declared_and_the_loop_counts_against_it():
    """A ceiling exists and is actually enforced, not just commented."""
    script = _script()
    assert "const FLORA_PER_CONTINENT_CAP = 700;" in script
    assert "let floraPlacedTotal = 0;" in script
    assert "floraPlacedTotal < FLORA_PER_CONTINENT_CAP" in script
    assert "floraPlacedTotal++" in script


def test_the_berry_branch_no_longer_claims_apples_and_fiber():
    """The old line drew a berry bush for apples and fiber plants."""
    script = _script()
    assert 'res.includes("berries") && (seed % 10 < 5)' in script
    assert '(res.includes("berries") || res.includes("apples") || res.includes("fiber"))' not in script
