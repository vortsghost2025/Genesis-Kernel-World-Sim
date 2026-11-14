"""Phase 10QO - the interior shows the home's real contents.

Operator, 2026-11-14: "i still find the interior of the house to be very bland
they have 8 houses but zero things inside."

Measured on the live West settlement the same hour:

  the interior view picked the NEAREST roofed structure to the walking agent:
  `shelter @ cont_b_gen_31_52`, one tile away, whose only object was itself,
  and drew a beige box -- while 147 objects stood within two tiles of the
  settlement core and the richest single tile held 72.

Two defects, both in the viewer:

  1. it read ONE tile's objects, but a home is a connected compound;
  2. its prop vocabulary covered six object types, while the lanes hold
     wells, forges, furnaces, containers, barrels, ladders, tools, gardens
     and storage -- every one drawn as nothing.

These tests run the pure functions in node: no browser, no GPU, cheap enough
for CI, and they pin the classification and the bounds rather than a picture.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"

NODE = shutil.which("node")


def _extract_functions() -> str:
    html = HTML.read_text(encoding="utf-8")
    names = ("INTERIOR_PROP_CAP", "INTERIOR_PROP_LIMITS", "interiorPropKind",
             "interiorPropPlan", "_tileCoordOf", "neighbourhoodObjects")
    # take the script block and cut the region that defines them
    import re
    js = max(re.findall(r"<script>(.*?)</script>", html, re.DOTALL), key=len)
    start = js.find("const INTERIOR_PROP_CAP")
    end = js.find("function rebuildInteriorProps")
    assert start > 0 and end > start, "the 10QO interior block must be present"
    return js[start:end]


def _run(assertions: str) -> None:
    if NODE is None:
        import pytest
        pytest.skip("node not available")
    harness = _extract_functions() + "\n" + assertions
    tmp = Path(__file__).resolve().parent / ".tmp-interior-10qo.js"
    tmp.write_text(harness, encoding="utf-8", newline="\n")
    try:
        res = subprocess.run([NODE, str(tmp)], capture_output=True, text=True,
                             timeout=60)
        assert res.returncode == 0, res.stderr[:1500] or res.stdout[:1500]
    finally:
        tmp.unlink(missing_ok=True)


def test_the_room_is_not_empty_when_the_house_has_things_in_it():
    _run("""
const objs = [
  { object_id: "f1", object_type: "campfire", tile_id: "cont_b_gen_35_51" },
  { object_id: "s1", object_type: "storage", tile_id: "cont_b_gen_35_51" },
  { object_id: "c1", object_type: "crafting_surface", tile_id: "cont_b_gen_35_51" },
  { object_id: "w1", object_type: "well", tile_id: "cont_b_gen_35_52" },
  { object_id: "g1", object_type: "forge", tile_id: "cont_b_gen_35_51" },
];
const plan = interiorPropPlan(objs);
const kinds = plan.map(p => p.kind).sort();
const want = ["forge", "hearth", "storage", "well", "workbench"].sort();
if (JSON.stringify(kinds) !== JSON.stringify(want)) {
  throw new Error("plan was " + JSON.stringify(kinds));
}
""")


def test_a_neighbouring_tiles_furniture_is_part_of_the_home():
    """The compound: a shelter's furniture stands on the tile beside it."""
    _run("""
// twelve shelters with nothing in them, and one hearth next door
const objs = [];
for (let i = 0; i < 12; i++) {
  objs.push({ object_id: "s" + i, object_type: "shelter",
              tile_id: "cont_b_gen_3" + (i % 2) + "_51" });
}
objs.push({ object_id: "f", object_type: "campfire",
            tile_id: "cont_b_gen_34_51" });
const plan = interiorPropPlan(objs);
if (plan.length !== 1 || plan[0].kind !== "hearth") {
  throw new Error("expected exactly the hearth, got " + JSON.stringify(plan));
}
""")


def test_structures_are_never_drawn_as_furniture():
    """The room IS the structure; drawing 68 shelters as props is not a room."""
    _run("""
const objs = [
  { object_id: "a", object_type: "shelter", tile_id: "t_0_0" },
  { object_id: "b", object_type: "cabin", tile_id: "t_0_0" },
  { object_id: "c", object_type: "lean-to", tile_id: "t_0_0" },
  { object_id: "d", object_type: "wall", tile_id: "t_0_0" },
  { object_id: "e", object_type: "roof", tile_id: "t_0_0" },
  { object_id: "f", object_type: "landmark", tile_id: "t_0_0" },
];
const plan = interiorPropPlan(objs);
if (plan.length !== 0) throw new Error("structures leaked: " + JSON.stringify(plan));
""")


def test_a_room_does_not_fill_with_forty_containers():
    """Bounds: the cap keeps it a room, not a warehouse."""
    _run("""
const objs = [];
for (let i = 0; i < 40; i++) {
  objs.push({ object_id: "c" + i, object_type: "container", tile_id: "t_0_0" });
}
for (let i = 0; i < 9; i++) {
  objs.push({ object_id: "f" + i, object_type: "campfire", tile_id: "t_0_0" });
}
const plan = interiorPropPlan(objs);
const stores = plan.filter(p => p.kind === "storage").length;
const hearths = plan.filter(p => p.kind === "hearth").length;
if (stores > 4) throw new Error("too many containers: " + stores);
if (hearths > 1) throw new Error("too many hearths: " + hearths);
if (plan.length > INTERIOR_PROP_CAP) throw new Error("cap exceeded");
""")


def test_the_kinds_the_lanes_actually_built_are_recognised():
    _run("""
const cases = {
  campfire: "hearth", hearth: "hearth", forge: "forge", furnace: "forge",
  well: "well", cistern: "well", ladder: "ladder", storage: "storage",
  storage_cellar: "storage", container: "storage", barrel: "storage",
  clay_pot: "storage", crafting_surface: "workbench", workbench: "workbench",
  tool: "tools", garden: "garden", bed: "bed", table: "table", chair: "chair",
};
for (const [type, want] of Object.entries(cases)) {
  const got = interiorPropKind(type);
  if (got !== want) throw new Error(type + " -> " + got + ", wanted " + want);
}
for (const type of ["shelter", "cabin", "hut", "lean-to", "wall", "roof",
                    "landmark", "road", "tree", "berry"]) {
  if (interiorPropKind(type) !== null) {
    throw new Error(type + " should not be a prop");
  }
}
""")


def test_neighbourhood_gathering_covers_the_compound_only():
    """Chebyshev 1 is the home; two tiles away is somebody else's house."""
    _run("""
// stub the world it reads
globalThis.reconstructPublicObjectsAtHb = (pair, hb) => ([
  { object_id: "here", object_type: "campfire", tile_id: "cont_b_gen_35_51" },
  { object_id: "next", object_type: "storage", tile_id: "cont_b_gen_34_51" },
  { object_id: "diag", object_type: "well", tile_id: "cont_b_gen_34_52" },
  { object_id: "far", object_type: "forge", tile_id: "cont_b_gen_33_51" },
  { object_id: "vfar", object_type: "tools", tile_id: "cont_b_gen_35_49" },
]);
const near = neighbourhoodObjects("west", 100, "cont_b_gen_35_51");
const ids = near.map(o => o.object_id).sort();
if (JSON.stringify(ids) !== JSON.stringify(["diag", "here", "next"])) {
  throw new Error("gathered " + JSON.stringify(ids));
}
""")
