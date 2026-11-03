"""Test suite for Phase 10NE: Planetary Globe Rendering & Continental Scale.

Specification: docs/phase_10nc_planetary_globe_and_continental_scale_spec.md §5
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORLD_SIM))

PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _extract_js_function(script: str, fn_name: str) -> str:
    pattern = rf"function\s+{fn_name}\s*\([^)]*\)\s*\{{.*?\n\}}"
    m = re.search(pattern, script, re.DOTALL)
    assert m, f"Function '{fn_name}' must be defined in prototype/index.html"
    return m.group(0)


def _run_node(js: str):
    res = subprocess.run(["node", "-"], input=js, capture_output=True, text=True,
                         check=True)
    return json.loads(res.stdout.strip())


def _consts(script: str, *names: str) -> str:
    """Emit the declared constants we need for the projection."""
    out = []
    for n in names:
        m = re.search(rf"const\s+{n}\s*=\s*[^;]+;", script)
        assert m, f"constant {n} missing"
        out.append(m.group(0))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 1. Local coordinates preserved (orbit mode must not move local views)
# ---------------------------------------------------------------------------

def test_globe_projection_preserves_local_coordinates():
    """A tile's flat (local-mode) position must be the identity mapping."""
    script = _get_prototype_script()
    js = (
        _consts(script, "LOCAL_WORLD_SCALE", "GLOBE_RADIUS")
        + _extract_js_function(script, "computeLocalPosition")
        + "\n"
        + "const p = computeLocalPosition(12, -45, 3.5);\n"
        + "console.log(JSON.stringify(p));\n"
    )
    d = _run_node(js)
    assert d["x"] == 12, "local x must be the tile x"
    assert d["z"] == -45, "local z must be the tile y"
    assert d["y"] == 3.5, "local y must be the elevation"


def test_local_world_scale_is_exactly_one():
    """1 unit = 1 metre in local modes; no scale factor applied."""
    script = _get_prototype_script()
    m = re.search(r"LOCAL_WORLD_SCALE\s*=\s*([0-9.]+)", script)
    assert m, "LOCAL_WORLD_SCALE constant must be declared"
    assert float(m.group(1)) == 1.0, "local world scale must remain 1.0"


def _globe_setup(script):
    setup = (_consts(script, "LOCAL_WORLD_SCALE", "GLOBE_RADIUS",
                         "GLOBE_CONTINENT_SPAN", "GLOBE_PATCHES")
              + _extract_js_function(script, "computeGlobePosition"))
    return setup


def test_globe_positions_lie_on_sphere_of_radius_plus_elevation():
    """Every projected tile sits at radius + elevation from the planet centre."""
    script = _get_prototype_script()
    js = (
        _globe_setup(script)
        + "\n"
        + "const out = [];\n"
        + "for (const cid of ['cont_a','cont_b']) {\n"
        + "  for (const x of [-100,-50,0,50,99]) {\n"
        + "    for (const y of [-100,0,99]) {\n"
        + "      const p = computeGlobePosition(cid, x, y, 7.0);\n"
        + "      out.push({ cid: cid, r: Math.hypot(p.x, p.y, p.z) });\n"
        + "    }\n"
        + "  }\n"
        + "}\n"
        + "console.log(JSON.stringify(out));\n"
    )
    rows = _run_node(js)
    assert rows, "projection produced no output"
    for row in rows:
        expected = 900.0 + 7.0
        assert abs(row["r"] - expected) < 1e-6, (
            "%s: radius %.6f != %.6f" % (row["cid"], row["r"], expected)
        )


def test_globe_projection_is_pure_and_deterministic():
    """Same inputs must yield identical outputs; no RNG in the projection."""
    script = _get_prototype_script()
    js = (
        _globe_setup(script)
        + "\n"
        + "const a = computeGlobePosition('cont_b', 33, -12, 4.25);\n"
        + "const b = computeGlobePosition('cont_b', 33, -12, 4.25);\n"
        + "console.log(JSON.stringify({ ax: a.x, ay: a.y, az: a.z, bx: b.x, by: b.y, bz: b.z }));\n"
    )
    d = _run_node(js)
    assert d["ax"] == d["bx"] and d["ay"] == d["by"] and d["az"] == d["bz"]


def test_ocean_stays_below_zero_on_sphere():
    """Ocean tiles must project below land tiles on the globe."""
    script = _get_prototype_script()
    js = (
        _globe_setup(script)
        + "\n"
        + "const land = computeGlobePosition('cont_a', 0, 0, 2.0);\n"
        + "const sea  = computeGlobePosition('cont_a', 0, 0, -0.35);\n"
        + "console.log(JSON.stringify({ landR: Math.hypot(land.x, land.y, land.z),"
        + " seaR: Math.hypot(sea.x, sea.y, sea.z) }));\n"
    )
    d = _run_node(js)
    assert d["seaR"] < d["landR"], (
        "ocean radius %.3f must be below land radius %.3f" % (d["seaR"], d["landR"])
    )
    assert d["seaR"] < 900.0, "ocean must project below the nominal planet radius"


def test_globe_uses_single_elevation_source():
    """Globe and flat views must read the same height source."""
    script = _get_prototype_script()
    assert "heightLookup" in script, "heightLookup must remain the single elevation source"
    # the globe projection must take elevation as an argument, not generate it
    m = re.search(r"function computeGlobePosition\([^)]*\)", script)
    assert m, "computeGlobePosition missing"
    assert "h" in m.group(0), (
        "computeGlobePosition must accept elevation 'h' rather than generating it"
    )
    # no second elevation generator introduced by the globe work
    assert "computeContinentHeightField" in script, (
        "existing elevation generator must still be the one used"
    )


def test_mode_switch_uses_one_position_entry_point():
    """Terrain, scenery, objects and fauna must share one position function."""
    script = _get_prototype_script()
    assert "computeWorldPosition" in script, (
        "a single computeWorldPosition entry point must exist for all layers"
    )
    # every layer group must be reachable by that shared mapping
    for layer in ("continentGroups", "sceneryGroups", "objectGroups",
                  "islandGroups", "faunaFiguresGroup", "waterMeshes"):
        assert layer in script, "%s must exist so the mapping can cover it" % layer


def test_projection_toggle_round_trips_losslessly():
    """Orbit projection must move vertices onto the globe and restore them."""
    script = _get_prototype_script()
    stubs = "".join([
        "var THREE = { Vector3: function (x, y, z) {",
        " this.x = x || 0; this.y = y || 0; this.z = z || 0; } };\n",
        "var terrainMeshes = {};\n",
        "var terrainFlatPositions = {};\n",
        "var globeProjectionActive = { cont_a: false, cont_b: false };\n"
        "var globalOceanGlobe = { visible: false };\n"
        "var setOceanProjection = function (u) { globalOceanGlobe.visible = u; };\n",
    ])
    fake = "".join([
        "var flat = [0,2,0, 10,3,-5, -7,1,9];\n",
        "terrainMeshes['cont_a'] = { geometry: {",
        " attributes: { position: { array: flat.slice(), needsUpdate: false } },",
        " computeVertexNormals: function () {},",
        " computeBoundingSphere: function () {} } };\n",
        "terrainFlatPositions['cont_a'] = Float32Array.from(flat);\n",
    ])
    checks = "".join([
        "var before = terrainMeshes['cont_a'].geometry.attributes.position.array.slice();\n",
        "setContinentProjection('cont_a', true);\n",
        "var onGlobe = globeProjectionActive['cont_a'];\n",
        "var globe = terrainMeshes['cont_a'].geometry.attributes.position.array.slice();\n",
        "setContinentProjection('cont_a', false);\n",
        "var restored = terrainMeshes['cont_a'].geometry.attributes.position.array.slice();\n",
        "var r0 = Math.hypot(globe[0], globe[1], globe[2]);\n",
        "console.log(JSON.stringify({ onGlobe: onGlobe,",
        " moved: Math.abs(globe[0] - before[0]) > 1.0, r0: r0,",
        " restored: before.every(function (v, i) { return Math.abs(v - restored[i]) < 1e-6; }),",
        " afterGlobe: globeProjectionActive['cont_a'] }));\n",
    ])
    js = (
        stubs
        + _consts(script, "LOCAL_WORLD_SCALE", "GLOBE_RADIUS",
                  "GLOBE_CONTINENT_SPAN", "GLOBE_PATCHES")
        + _extract_js_function(script, "computeLocalPosition")
        + _extract_js_function(script, "computeGlobePosition")
        + _extract_js_function(script, "setContinentProjection")
        + "\n" + fake + checks
    )
    d = _run_node(js)
    assert d["onGlobe"] is True, "orbit mode must flag the projection active"
    assert d["afterGlobe"] is False, "local mode must clear the flag"
    assert d["moved"], "orbit must move vertices off the flat plane"
    assert abs(d["r0"] - (900.0 + 2.0)) < 1e-6, "vertex radius must be R + elevation"
    assert d["restored"], "local mode must reproduce flat coordinates exactly"


def test_ocean_globe_loads_without_temporal_dead_zone():
    """The load-time ocean sphere must come after GLOBE_RADIUS is initialised.

    Regression test for a real defect: the spherical-ocean block built
    SphereGeometry(GLOBE_RADIUS - 0.6) above the `const GLOBE_RADIUS = 900.0`
    declaration. `const` is hoisted into a temporal dead zone, so the block
    threw "Cannot access 'GLOBE_RADIUS' before initialization" at page load and
    killed the ENTIRE viewer script -- focusCiv and every other function went
    undefined and the page was dead. The existing function-extraction tests
    passed because they never execute the load-time ordering.

    This test reproduces the browser's initialisation order and asserts the
    constants plus the load-time geometry block execute cleanly.
    """
    script = _get_prototype_script()

    # Everything that runs at load time, in source order.
    stubs = "".join([
        "var THREE = {\n",
        " SphereGeometry: function (r, s, h) { this.r = r; },\n",
        " MeshBasicMaterial: function (o) { this.o = o; },\n",
        " Mesh: function (g, m) { this.geometry = g; this.material = m; this.visible = false; }\n",
        "};\n",
        "var scene = { added: [], add: function (m) { this.added.push(m); } };\n",
    ])

    load_time = "".join([
        "const LOCAL_WORLD_SCALE = 1.0;\n",
        "const GLOBE_RADIUS = 900.0;\n",
    ])

    m = re.search(r"const\s+GLOBE_PATCHES\s*=\s*\{[^}]*\{[^}]*\}[^}]*\{[^}]*\}[^}]*\};",
                  script, re.DOTALL)
    assert m, "GLOBE_PATCHES must be declared as a const block"

    ocean = re.search(
        r"const\s+globalOceanGlobeGeom\s*=\s*new THREE\.SphereGeometry\("
        r".*?\)\s*;.*?scene\.add\(globalOceanGlobe\);",
        script, re.DOTALL,
    )
    assert ocean, "the load-time spherical ocean block must exist"
    toggle = _extract_js_function(script, "setOceanProjection")

    js = (
        stubs
        + load_time
        + "\n"
        + m.group(0)
        + "\n"
        + ocean.group(0)
        + "\n"
        + toggle
        + "\n"
        + "globalOceanGlobe.visible = false;\n"
        + "globalOcean = { visible: true };\n"
        + "setOceanProjection(true);\n"
        + "var orbit = globalOceanGlobe.visible;\n"
        + "setOceanProjection(false);\n"
        + "var local = globalOcean.visible;\n"
        + "console.log(JSON.stringify({ orbit: orbit, local: local,"
        " r: globalOceanGlobeGeom.r }));\n"
    )

    d = _run_node(js)

    # radius must be GLOBE_RADIUS - 0.6, i.e. the constant was readable
    assert abs(d["r"] - (900.0 - 0.6)) < 1e-9, "SphereGeometry radius must come from GLOBE_RADIUS"
    assert d["orbit"] is True, "orbit must show the spherical ocean"
    assert d["local"] is True, "local must show the flat ocean"


def test_globe_constants_precede_their_load_time_uses():
    """Source-order guard: GLOBE_RADIUS must be declared before any load-time use."""
    script = _get_prototype_script()
    decl = script.find("const GLOBE_RADIUS")
    assert decl > 0, "GLOBE_RADIUS must be declared"
    use = script.find("globalOceanGlobeGeom")
    assert use > 0, "the spherical ocean block must exist"
    assert decl < use, (
        "GLOBE_RADIUS must be declared BEFORE the load-time SphereGeometry block "
        "that consumes it, otherwise the script throws a temporal-dead-zone error"
    )


def test_orbit_switches_ocean_to_sphere_and_back():
    """The ocean must become spherical in orbit mode and flat in local mode.

    Without this, the spherical continents hover over a flat disc that cuts
    through the globe -- the loose end left by projecting only the land.
    """
    script = _get_prototype_script()
    stubs = "".join([
        "var globalOcean = { visible: true };\n",
        "var globalOceanGlobe = { visible: false };\n",
        "function setOceanProjection(u) {",
        " globalOcean.visible = !u;",
        " globalOceanGlobe.visible = u; }\n",
    ])
    js = (
        stubs
        + _extract_js_function(script, "setOceanProjection")
        + "\n"
        + "setOceanProjection(true);\n"
        + "var orbit = { flat: globalOcean.visible, globe: globalOceanGlobe.visible };\n"
        + "setOceanProjection(false);\n"
        + "var local = { flat: globalOcean.visible, globe: globalOceanGlobe.visible };\n"
        + "console.log(JSON.stringify({ orbit: orbit, local: local }));\n"
    )
    d = _run_node(js)
    assert d["orbit"]["flat"] is False, "orbit mode must hide the flat ocean plane"
    assert d["orbit"]["globe"] is True, "orbit mode must show the spherical ocean"
    assert d["local"]["flat"] is True, "local mode must restore the flat ocean plane"
    assert d["local"]["globe"] is False, "local mode must hide the spherical ocean"
