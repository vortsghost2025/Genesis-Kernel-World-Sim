"""Test suite for the planetary surface (Phase 10NS) and the canonical
continent integration (Phase 10OK).

Specification: docs/phase_10nq_planetary_surface_synthesis_spec.md
              docs/phase_10oi_integrate_canonical_continents_into_the_globe_spec.md
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

PLANET_CANONICAL_LIFT_VAL = 2.0
PLANET_CANONICAL_OCEAN_DEPTH_VAL = -38.0


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _extract_js_function(script: str, fn_name: str) -> str:
    pattern = rf"function\s+{fn_name}\s*\([^)]*\)\s*\{{.*?\n\}}"
    m = re.search(pattern, script, re.DOTALL)
    assert m, "Function '%s' must be defined" % fn_name
    return m.group(0)


def _extract_js_function_nested(script: str, fn_name: str) -> str:
    i = script.find("function " + fn_name)
    assert i >= 0, "function %s not found" % fn_name
    j = script.find("{", i)
    depth, k = 0, j
    while k < len(script):
        if script[k] == "{":
            depth += 1
        elif script[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return script[i:k + 1]


def _consts(script: str, *names: str) -> str:
    """Emit module constants in dependency order.

    GLOBE_CONTINENT_SPAN is defined as 200.0 / GLOBE_RADIUS, so emitting the
    derived constant before its basis throws a temporal dead zone -- the same
    class of bug that killed the viewer in Phase 10JJ.
    """
    all_c = {m.group(1): m.group(0)
             for m in re.finditer(r"const\s+([A-Z][A-Z0-9_]*)\s*=\s*[^;]+;", script)}
    closure, stack = set(), list(names)
    while stack:
        n = stack.pop()
        if n in closure or n not in all_c:
            continue
        closure.add(n)
        for dep in re.findall(r"\b([A-Z][A-Z0-9_]*)\b", all_c[n]):
            if dep in all_c and dep not in closure:
                stack.append(dep)

    out, seen, remaining = [], set(), set(closure)
    while remaining:
        progressed = False
        for name in list(remaining):
            body = re.sub(r"^const\s+\w+\s*=\s*", "", all_c[name]).rsplit(";", 1)[0]
            deps = set(re.findall(r"\b([A-Z][A-Z0-9_]*)\b", body))
            if not (deps & closure) - seen:
                out.append(all_c[name])
                seen.add(name)
                remaining.discard(name)
                progressed = True
        if not progressed:
            out.extend(all_c[n] for n in remaining)
            break
    return "\n".join(out) + "\n" if out else ""


def _run_node(js: str):
    res = subprocess.run(["node", "-"], input=js, capture_output=True, text=True,
                         check=True)
    return json.loads(res.stdout.strip())


CANON_STUBS = (
    "var terrainDB = { cont_a: { terr: new Array(40000).fill('mountain') },"
    " cont_b: { terr: new Array(40000).fill('mountain') } };\n"
    "var heightLookup = { cont_a: new Float32Array(40000),"
    " cont_b: new Float32Array(40000) };\n"
)


def _terrain_parts(script: str) -> list[str]:
    return [
        _consts(script, "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN", "GLOBE_RADIUS",
                "PLANET_HEIGHT_SCALE", "PLANET_SEA_LEVEL",
                "PLANET_CANONICAL_OCEAN_DEPTH", "PLANET_CANONICAL_LIFT",
                "PLANET_PATCH_FEATHER", "PLANET_LANDMARKS"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "planetCanonicalHeight"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        CANON_STUBS,
    ]


def _fixture_stubs(terr, hl) -> str:
    terr_lit = "[" + ",".join('"%s"' % x for x in terr) + "]"
    hl_lit = "[" + ",".join(str(x) for x in hl) + "]"
    return (
        "var terrainDB = { cont_a: { terr: %s }, cont_b: { terr: %s } };\n"
        "var heightLookup = { cont_a: new Float32Array(%s),"
        " cont_b: new Float32Array(%s) };\n"
        % (terr_lit, terr_lit, hl_lit, hl_lit)
    )


def _fixture_arrays():
    """Ocean everywhere except a 20x20 block of land in the middle."""
    terr = ["ocean"] * 40000
    hl = [0.0] * 40000
    for cy in range(90, 110):
        for cx in range(90, 110):
            i = cy * 200 + cx
            terr[i] = "mountain"
            hl[i] = 20.0 + ((cx - 90) % 7)
    return terr, hl


def _uniform_land_fixture(height: float = 30.0):
    """Land of one height across the whole box, so the patch boundary is the
    only thing the feather test can possibly be measuring."""
    return ["mountain"] * 40000, [height] * 40000


# ---------------------------------------------------------------------------
# terrain synthesis (Phase 10NS)
# ---------------------------------------------------------------------------

def test_planet_noise_is_seamless_and_deterministic():
    script = _get_prototype_script()
    js = "".join([
        _consts(script, "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN", "GLOBE_RADIUS",
                "PLANET_CANONICAL_OCEAN_DEPTH", "PLANET_CANONICAL_LIFT",
                "PLANET_PATCH_FEATHER", "PLANET_LANDMARKS",
                "PLANET_SEA_LEVEL", "PLANET_HEIGHT_SCALE"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "planetCanonicalHeight"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        CANON_STUBS,
        "\nfunction probe(lon, lat) {\n",
        "  return computePlanetHeight(lon + 2.4, lat + 0.9);\n",
        "}\n",
        "var a = probe(0.3, 0.7), b = probe(0.3 + 6.283185307179586, 0.7);\n",
        "var c = probe(1.1, 1.57), d = probe(1.1 + 6.283185307179586, 1.57);\n",
        "var rep = probe(0.5, 0.2), rep2 = probe(0.5, 0.2);\n",
        "var np = probe(0.0, 1.5707963), sp = probe(3.14159, 1.5707963);\n",
        "var other = probe(1.7, 0.4);\n",
        "console.log(JSON.stringify({ seam: [a, b], poleSeam: [c, d],\n",
        "  rep: [rep, rep2], poles: [np, sp], other: other }));\n",
    ])
    d = _run_node(js)

    assert abs(d["seam"][0] - d["seam"][1]) < 1e-9, "longitude must be seamless"
    assert abs(d["poleSeam"][0] - d["poleSeam"][1]) < 1e-9, "poles must be seamless"
    assert d["rep"][0] == d["rep"][1], "the field must be deterministic"
    assert abs(d["poles"][0] - d["poles"][1]) < 1e-9, (
        "opposite longitudes at the pole must agree")
    assert d["seam"][0] != d["other"], "the field must vary across the globe"


def test_planet_has_land_outside_canonical_patches():
    script = _get_prototype_script()
    js = "".join(_terrain_parts(script)) + (
        "\nvar land = 0, total = 0, half = GLOBE_CONTINENT_SPAN / 2.0;\n"
        "for (var ii = 0; ii < 144; ii++) for (var jj = 1; jj < 72; jj++) {\n"
        "  var lon = (ii / 144.0) * 6.283185307179586;\n"
        "  var lat = (jj / 72.0) * 3.141592653589793 - 1.5707963267948966;\n"
        "  var inPatch = false;\n"
        "  Object.keys(GLOBE_PATCHES).forEach(function (cid) {\n"
        "    var p = GLOBE_PATCHES[cid];\n"
        "    if (Math.abs(lon - p.lon) < half && Math.abs(lat - p.lat) < half)"
        " inPatch = true;\n"
        "  });\n"
        "  if (inPatch) continue;\n"
        "  var w = Math.cos(lat);\n"
        "  total += w;\n"
        "  if (computePlanetHeight(lon, lat) > 0) land += w;\n"
        "}\n"
        "console.log(JSON.stringify({ land: land, total: total, frac: land / total }));\n"
    )
    d = _run_node(js)
    assert d["total"] > 1000, "the sweep must sample the globe, got %d" % d["total"]
    assert d["frac"] < 0.12, (
        "outside the canonical patches the planet should be ocean except for "
        "polar ice; observed land fraction was %.3f" % d["frac"])


def test_planet_heights_stay_bounded():
    script = _get_prototype_script()
    js = "".join(_terrain_parts(script)) + (
        "\nvar lo = 1e9, hi = -1e9;\n"
        "for (var ii = 0; ii < 120; ii++) for (var jj = 0; jj < 60; jj++) {\n"
        "  var h = computePlanetHeight((ii / 120.0) * 6.283185307179586,\n"
        "    (jj / 60.0) * 3.141592653589793 - 1.5707963267948966);\n"
        "  if (h < lo) lo = h; if (h > hi) hi = h;\n"
        "}\n"
        "console.log(JSON.stringify({ lo: lo, hi: hi,"
        " outer: GLOBE_RADIUS + hi, inner: GLOBE_RADIUS + lo }));\n"
    )
    d = _run_node(js)
    assert d["hi"] < 400.0, "land peaks too tall for the framing distance: %s" % d["hi"]
    assert d["lo"] > -400.0, "ocean floors too deep: %s" % d["lo"]
    assert d["outer"] < 7200.0, "outer radius must stay inside the camera far plane"
    assert d["inner"] > 0.0, "inner radius must stay positive"


# ---------------------------------------------------------------------------
# canonical continent integration (Phase 10OK)
# ---------------------------------------------------------------------------

def test_planet_samples_canonical_height_inside_the_patch_box():
    terr, hl = _fixture_arrays()
    body = (
        "var p = GLOBE_PATCHES.cont_a;\n"
        "var out = {};\n"
        "[[0, 0], [-5, -5], [9, 9]].forEach(function (xy) {\n"
        "  var t = (xy[0] + 100) / 200.0, v = (xy[1] + 100) / 200.0;\n"
        "  var lon = p.lon + (t - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "  var lat = p.lat + (v - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "  out[xy.join(',')] = computePlanetHeight(lon, lat);\n"
        "});\n"
        "console.log(JSON.stringify(out));\n"
    )
    js = "".join(_terrain_parts(_get_prototype_script())) \
        .replace(CANON_STUBS, _fixture_stubs(terr, hl)) + body
    d = _run_node(js)

    # tile cx for input x=0 is 100 -> 20 + ((100 - 90) % 7) = 23
    assert abs(d["0,0"] - (23.0 + PLANET_CANONICAL_LIFT_VAL)) < 1e-6, (
        "an interior land tile must carry its canonical height, got %s" % d["0,0"])
    # x=-5 -> cx 95 -> 20 + (5 % 7) = 25
    assert abs(d["-5,-5"] - (25.0 + PLANET_CANONICAL_LIFT_VAL)) < 1e-6, d["-5,-5"]
    # x=9 -> cx 109 -> 20 + (19 % 7) = 25
    assert abs(d["9,9"] - (25.0 + PLANET_CANONICAL_LIFT_VAL)) < 1e-6, d["9,9"]


def test_canonical_ocean_tiles_read_as_ocean():
    terr, hl = _fixture_arrays()
    body = (
        "var p = GLOBE_PATCHES.cont_a;\n"
        "var t = (10 + 100) / 200.0, v = (10 + 100) / 200.0;\n"
        "var lon = p.lon + (t - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "var lat = p.lat + (v - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "console.log(JSON.stringify({ h: computePlanetHeight(lon, lat) }));\n"
    )
    js = "".join(_terrain_parts(_get_prototype_script())) \
        .replace(CANON_STUBS, _fixture_stubs(terr, hl)) + body
    d = _run_node(js)
    assert d["h"] == PLANET_CANONICAL_OCEAN_DEPTH_VAL, (
        "a canonical ocean tile must be ocean on the planet, got %s" % d["h"])


def test_inverse_mapping_matches_the_forward_mapping():
    script = _get_prototype_script()
    stubs = (
        "var TERR = new Array(40000).fill('mountain');\n"
        "var IDX = new Float32Array(40000);\n"
        "for (var i = 0; i < 40000; i++) IDX[i] = i;\n"
        "var heightLookup = { cont_a: IDX, cont_b: IDX };\n"
        "var terrainDB = { cont_a: { terr: TERR }, cont_b: { terr: TERR } };\n"
    )
    body = (
        "var p = GLOBE_PATCHES.cont_a;\n"
        "var worst = 0;\n"
        "for (var gx = 0; gx < 20; gx++) for (var gy = 0; gy < 20; gy++) {\n"
        "  var x = -90 + gx * 9, y = -90 + gy * 9;\n"
        "  var t = (x + 100) / 200.0, v = (y + 100) / 200.0;\n"
        "  var lon = p.lon + (t - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "  var lat = p.lat + (v - 0.5) * GLOBE_CONTINENT_SPAN;\n"
        "  var back = planetCanonicalHeight('cont_a', lon, lat)"
        " - PLANET_CANONICAL_LIFT;\n"
        "  var expect = (y + 100) * 200 + (x + 100);\n"
        "  worst = Math.max(worst, Math.abs(back - expect));\n"
        "}\n"
        "console.log(JSON.stringify({ worst: worst }));\n"
    )
    js = "".join([
        _consts(script, "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN", "GLOBE_RADIUS",
                "PLANET_CANONICAL_OCEAN_DEPTH", "PLANET_CANONICAL_LIFT"),
        stubs,
        _extract_js_function_nested(script, "planetCanonicalHeight"),
        body,
    ])
    d = _run_node(js)
    assert d["worst"] < 1e-6, (
        "the inverse mapping must recover the tile the forward mapping produced; "
        "worst error was %s" % d["worst"])


def test_patch_boundary_is_feathered_not_a_cliff():
    terr, hl = _uniform_land_fixture(30.0)
    body = (
        "var p = GLOBE_PATCHES.cont_a, half = GLOBE_CONTINENT_SPAN / 2.0;\n"
        "var prev = null, worst = 0;\n"
        "for (var k = 0; k <= 80; k++) {\n"
        "  var d = (k / 80.0) * (half + PLANET_PATCH_FEATHER * 1.5);\n"
        "  var lat = p.lat + d;\n"
        "  var h = computePlanetHeight(p.lon, lat);\n"
        "  if (prev !== null) worst = Math.max(worst, Math.abs(h - prev));\n"
        "  prev = h;\n"
        "}\n"
        "console.log(JSON.stringify({ worst: worst }));\n"
    )
    js = "".join(_terrain_parts(_get_prototype_script())) \
        .replace(CANON_STUBS, _fixture_stubs(terr, hl)) + body
    d = _run_node(js)
    assert d["worst"] < 25.0, (
        "crossing the patch boundary must ramp through the feather; a step of %s "
        "world units is a visible cliff" % d["worst"])


def test_planet_mesh_builds_after_the_continent_meshes():
    """Built eagerly, the planet ran before the canonical data existed."""
    script = _get_prototype_script()
    assert "let globalPlanetMesh = null;" in script, (
        "the planet mesh must be declared deferred, not constructed at load")
    assert "const globalPlanetMesh = buildPlanetSurface();" not in script, (
        "the planet mesh must not be constructed at module load")
    continent_build = script.find('buildContinentMesh("cont_a");')
    planet_build = script.find("globalPlanetMesh = buildPlanetSurface();")
    assert planet_build > continent_build, (
        "buildPlanetSurface must run after buildContinentMesh, because it now "
        "samples the canonical height data those meshes produce")


# ---------------------------------------------------------------------------
# projection state
# ---------------------------------------------------------------------------

def test_set_ocean_projection_handles_three_states():
    script = _get_prototype_script()
    js = (
        "var globalOcean = { visible: false };\n"
        "var globalOceanGlobe = { visible: false };\n"
        "var globalPlanetMesh = { visible: false };\n"
        + _extract_js_function_nested(script, "setOceanProjection")
        + "\nfunction readback() {\n"
        "  return { flat: globalOcean.visible, shell: globalOceanGlobe.visible,"
        " planet: globalPlanetMesh.visible };\n"
        "}\n"
        "var res = {};\n"
        "setOceanProjection(false); res.local = readback();\n"
        "setOceanProjection('shell'); res.shell = readback();\n"
        "setOceanProjection(true); res.orbit = readback();\n"
        "setOceanProjection(false); res.back = readback();\n"
        "console.log(JSON.stringify(res));\n"
    )
    d = _run_node(js)
    assert d["local"] == {"flat": True, "shell": False, "planet": False}, (
        "local mode must show only the flat ocean plane")
    assert d["shell"] == {"flat": False, "shell": True, "planet": False}, (
        "the legacy shell state must remain reachable")
    assert d["orbit"] == {"flat": False, "shell": False, "planet": True}, (
        "orbit mode must show the planet sphere and nothing else")
    assert d["back"] == d["local"], "local mode must restore exactly"


def test_orbit_uses_the_planet_mesh_not_the_legacy_shell():
    script = _get_prototype_script()
    assert "globalPlanetMesh" in script, "the planet surface mesh must exist"
    assert "setOceanProjection(true)" in script, (
        "the orbit branch must switch to the planet projection")
    tail = script.split("function setOceanProjection")[1][:800]
    assert "globalPlanetMesh" in tail, (
        "setOceanProjection must control the planet mesh")


def _extract_js_pattern(script: str, pattern: str) -> str:
    m = re.search(pattern, script, re.DOTALL)
    assert m, "pattern not found: %s" % pattern[:60]
    return m.group(0)


def test_local_mode_still_restores_the_flat_plane():
    script = _get_prototype_script()
    local = _extract_js_pattern(
        script,
        r'if \(globalOceanGlobe\.visible\) setOceanProjection\(false\);'
        r'.*?continentGroups\[cid\]\.position\.set\(0, 0, 0\)')
    assert "setOceanProjection(false)" in local, (
        "local mode must restore the flat ocean projection")
