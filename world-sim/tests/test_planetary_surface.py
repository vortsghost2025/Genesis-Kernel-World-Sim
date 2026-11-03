"""Test suite for Phase 10NS: Planetary Surface Synthesis (fill the globe).

Specification: docs/phase_10nq_planetary_surface_synthesis_spec.md
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


def _extract_js_pattern(script: str, pattern: str) -> str:
    m = re.search(pattern, script, re.DOTALL)
    assert m, "pattern not found in prototype/index.html: %s" % pattern[:70]
    return m.group(0)


def _extract_js_function(script: str, fn_name: str) -> str:
    return _extract_js_pattern(
        script, rf"function\s+{fn_name}\s*\([^)]*\)\s*\{{.*?\n\}}"
    )


def _extract_js_function_nested(script: str, fn_name: str) -> str:
    """Extract a function whose body contains nested braces, by brace matching."""
    i = script.find("function " + fn_name)
    assert i >= 0, "function %s not found" % fn_name
    j = script.find("{", i)
    depth = 0
    k = j
    while k < len(script):
        if script[k] == "{":
            depth += 1
        elif script[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return script[i : k + 1]


def _consts(script: str, *names: str) -> str:
    """Emit the named constants, plus any constants their definitions reference.

    GLOBE_CONTINENT_SPAN is defined as 200.0 / GLOBE_RADIUS, so pulling only the
    derived constant would leave GLOBE_RADIUS undefined in the Node harness.
    Dependencies are resolved transitively so the harness always initialises clean.
    """
    out = []
    seen = set()
    pending = list(names)
    # Only module-level constants (ALL_CAPS by convention) may be auto-resolved.
    # The file is full of function-local `const lon = ...` declarations which
    # would otherwise be pulled in and shadow the functions' own locals.
    all_consts = {m.group(1): m.group(0)
                  for m in re.finditer(r"const\s+([A-Z][A-Z0-9_]*)\s*=\s*[^;]+;", script)}

    # Collect the closure of needed constants first...
    closure = set()
    stack = list(names)
    while stack:
        name = stack.pop()
        if name in closure or name not in all_consts:
            continue
        closure.add(name)
        for dep in re.findall(r"\b([A-Z][A-Z0-9_]*)\b", all_consts[name]):
            if dep in all_consts and dep not in closure:
                stack.append(dep)

    # ...then emit them in dependency order. Emitting a derived constant before
    # its own basis (GLOBE_CONTINENT_SPAN before GLOBE_RADIUS) throws the same
    # temporal-dead-zone error that killed the viewer in Phase 10JJ.
    remaining = set(closure)
    while remaining:
        progressed = False
        for name in list(remaining):
            body = re.sub(r"^const\s+\w+\s*=\s*", "", all_consts[name])
            body = body.rsplit(";", 1)[0]
            deps = {d for d in re.findall(r"\b([A-Z][A-Z0-9_]*)\b", body)}
            unsatisfied = deps & closure
            if not (unsatisfied - seen):
                out.append(all_consts[name])
                seen.add(name)
                remaining.discard(name)
                progressed = True
        if not progressed:
            # cyclic (should not happen for this codebase); emit what is left
            for name in remaining:
                out.append(all_consts[name])
            break

    return "\n".join(out) + "\n" if out else ""


def _run_node(js: str):
    res = subprocess.run(["node", "-"], input=js, capture_output=True, text=True,
                         check=True)
    return json.loads(res.stdout.strip())


# ---------------------------------------------------------------------------
# terrain synthesis
# ---------------------------------------------------------------------------

def test_planet_height_is_flat_inside_canonical_patches():
    """Procedural terrain must not intrude on the agents' own continents.

    If noise could raise a mountain inside a patch's lat/lon box it would intersect
    the flat canonical continent mesh projected at the same radius, tearing the
    settlement out of its own landscape.
    """
    script = _get_prototype_script()

    js = "".join([
        _consts(script, "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN", "PLANET_PATCH_PLAIN_H",
                "PLANET_SEA_LEVEL", "PLANET_HEIGHT_SCALE", "PLANET_LANDMARKS"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        "\nvar out = {};\n",
        "Object.keys(GLOBE_PATCHES).forEach(function (cid) {\n",
        "  var p = GLOBE_PATCHES[cid]; var half = GLOBE_CONTINENT_SPAN / 2.0;\n",
        "  var vals = [];\n",
        "  for (var i = -6; i <= 6; i++) for (var j = -6; j <= 6; j++) {\n",
        "    vals.push(computePlanetHeight(p.lon + (i * half) / 6.0,\n",
        "                                   p.lat + (j * half) / 6.0));\n",
        "  }\n",
        "  out[cid] = vals;\n",
        "});\n",
        "console.log(JSON.stringify(out));\n",
    ])

    d = _run_node(js)
    for cid, vals in d.items():
        assert vals, "%s produced no samples" % cid
        assert all(abs(v - 0.5) < 1e-9 for v in vals), (
            "%s patch box must be forced to a flat plain, got range %s..%s"
            % (cid, min(vals), max(vals))
        )


def test_planet_noise_is_seamless_and_deterministic():
    """The field must be seamless in longitude, continuous at the poles, and stable.

    Equirectangular noise has two classic failure modes: a visible seam where the
    texture wraps, and pinched garbage at the poles where longitude collapses. This
    samples the sphere direction instead, and asserts both properties hold.
    """
    script = _get_prototype_script()

    js = "".join([
        _consts(script, "GLOBE_CONTINENT_SPAN", "PLANET_PATCH_PLAIN_H",
                "PLANET_SEA_LEVEL", "PLANET_HEIGHT_SCALE", "PLANET_LANDMARKS",
                "GLOBE_PATCHES"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        "\nfunction probe(lon, lat) {\n",
        "  // sample well away from both canonical patch boxes\n",
        "  return computePlanetHeight(lon + 2.4, lat + 0.9);\n",
        "}\n",
        "var a = probe(0.3, 0.7), b = probe(0.3 + 6.283185307179586, 0.7);\n",
        "var c = probe(1.1, 1.57), d = probe(1.1 + 6.283185307179586, 1.57);\n",
        "var repeat = [probe(0.5, 0.2), probe(0.5, 0.2)];\n",
        "var north = probe(0.0, 1.5707963);\n",
        "var south = probe(3.14159, 1.5707963);\n",
        "var other = probe(1.7, 0.4);\n",
        "console.log(JSON.stringify({ seam: [a, b], poleSeam: [c, d],\n",
        "  repeat: repeat, poles: [north, south], other: other }));\n",
    ])

    d = _run_node(js)

    assert abs(d["seam"][0] - d["seam"][1]) < 1e-9, "longitude must be seamless"
    assert abs(d["poleSeam"][0] - d["poleSeam"][1]) < 1e-9, "poles must be seamless"
    assert d["repeat"][0] == d["repeat"][1], "the field must be deterministic"
    assert abs(d["poles"][0] - d["poles"][1]) < 1e-9, (
        "opposite longitudes at the pole must agree (they are the same point)"
    )
    assert d["seam"][0] != d["other"], "the field must actually vary across the globe"


def test_planet_has_land_outside_canonical_patches():
    """The atlas must stop being empty: measurable land beyond the two patches."""
    script = _get_prototype_script()

    js = "".join([
        _consts(script, "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN",
                "PLANET_PATCH_PLAIN_H", "PLANET_SEA_LEVEL",
                "PLANET_HEIGHT_SCALE", "PLANET_LANDMARKS"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        "\nvar land = 0, total = 0, half = GLOBE_CONTINENT_SPAN / 2.0;\n",
        "for (var ii = 0; ii < 144; ii++) for (var jj = 1; jj < 72; jj++) {\n",
        "  var lon = (ii / 144.0) * 6.283185307179586;\n",
        "  var lat = (jj / 72.0) * 3.141592653589793 - 1.5707963267948966;\n",
        "  var inPatch = false;\n",
        "  Object.keys(GLOBE_PATCHES).forEach(function (cid) {\n",
        "    var p = GLOBE_PATCHES[cid];\n",
        "    if (Math.abs(lon - p.lon) < half && Math.abs(lat - p.lat) < half)",
        " inPatch = true;\n",
        "  });\n",
        "  if (inPatch) continue;\n",
        # equal-area weighting: a degree of latitude near the pole covers far
        # less surface than one at the equator, so an unweighted sweep would
        # over-report ocean by counting polar rows the same as equatorial ones.
        "  var w = Math.cos(lat);\n",
        "  total += w;\n",
        "  if (computePlanetHeight(lon, lat) > PLANET_SEA_LEVEL) land += w;\n",
        "}\n",
        "console.log(JSON.stringify({ land: land, total: total,\n",
        "  frac: land / total }));\n",
    ])

    d = _run_node(js)

    assert d["total"] > 1000, "the sweep must sample the globe, got %d" % d["total"]
    assert 0.20 <= d["frac"] <= 0.55, (
        "land fraction outside the patches was %.3f; the spec targets 30-35%% "
        "so the globe reads as a real planet rather than a desert or an ocean"
        % d["frac"]
    )


def test_planet_heights_stay_bounded():
    """Extreme heights would punch through the sky dome or the near/far planes."""
    script = _get_prototype_script()

    js = "".join([
        _consts(script, "GLOBE_RADIUS", "GLOBE_PATCHES", "GLOBE_CONTINENT_SPAN",
                "PLANET_PATCH_PLAIN_H", "PLANET_DEEP_OCEAN",
                "PLANET_SEA_LEVEL", "PLANET_HEIGHT_SCALE", "PLANET_LANDMARKS"),
        _extract_js_function_nested(script, "planetHash3"),
        _extract_js_function_nested(script, "planetValueNoise"),
        _extract_js_function_nested(script, "planetBaseField"),
        _extract_js_function_nested(script, "computePlanetHeight"),
        "\nvar lo = 1e9, hi = -1e9;\n",
        "for (var ii = 0; ii < 120; ii++) for (var jj = 0; jj < 60; jj++) {\n",
        "  var h = computePlanetHeight((ii / 120.0) * 6.283185307179586,\n",
        "    (jj / 60.0) * 3.141592653589793 - 1.5707963267948966);\n",
        "  if (h < lo) lo = h; if (h > hi) hi = h;\n",
        "}\n",
        "console.log(JSON.stringify({ lo: lo, hi: hi,\n",
        "  outer: GLOBE_RADIUS + hi, inner: GLOBE_RADIUS + lo }));\n",
    ])

    d = _run_node(js)

    assert d["hi"] < 400.0, "land peaks too tall for the framing distance: %s" % d["hi"]
    assert d["lo"] > -400.0, "ocean floors too deep: %s" % d["lo"]
    assert d["outer"] < 7200.0, "outer radius must stay inside the orbit camera far plane"
    assert d["inner"] > 0.0, "inner radius must stay positive"


# ---------------------------------------------------------------------------
# projection state
# ---------------------------------------------------------------------------

def test_set_ocean_projection_handles_three_states():
    """One switch, three exclusive states: flat plane, legacy shell, planet sphere.

    A two-state toggle would let the flat ocean plane show through the planet and
    reintroduce the 10NG defect where continents hovered over a flat disc.
    """
    script = _get_prototype_script()

    # Run the REAL setOceanProjection from the source against mesh stubs. An
    # inline reimplementation of the function would be a circular test.
    js = "".join([
        "var globalOcean = { visible: false };\n",
        "var globalOceanGlobe = { visible: false };\n",
        "var globalPlanetMesh = { visible: false };\n",
        _extract_js_function_nested(script, "setOceanProjection"),
        "\nfunction readback() {\n",
        "  return { flat: globalOcean.visible, shell: globalOceanGlobe.visible,\n",
        "          planet: globalPlanetMesh.visible };\n",
        "}\n",
        "var res = {};\n",
        "setOceanProjection(false); res.local = readback();\n",
        "setOceanProjection('shell'); res.shell = readback();\n",
        "setOceanProjection(true); res.orbit = readback();\n",
        "setOceanProjection(false); res.back = readback();\n",
        "console.log(JSON.stringify(res));\n",
    ])

    d = _run_node(js)

    assert d["local"] == {"flat": True, "shell": False, "planet": False}, (
        "local mode must show only the flat ocean plane"
    )
    assert d["shell"] == {"flat": False, "shell": True, "planet": False}, (
        "the legacy shell state must remain reachable"
    )
    assert d["orbit"] == {"flat": False, "shell": False, "planet": True}, (
        "orbit mode must show the planet sphere and nothing else"
    )
    assert d["back"] == d["local"], "local mode must restore exactly"


def test_orbit_uses_the_planet_mesh_not_the_legacy_shell():
    """The orbit camera path must ask for the planet, not the coloured shell."""
    script = _get_prototype_script()

    assert "globalPlanetMesh" in script, (
        "the planet surface mesh must exist"
    )
    orbit_branch = _extract_js_pattern(
        script,
        r'if \(pairName === "orbit"\) \{.*?applyCameraMode\("orbit"',
    )
    assert 'setOceanProjection(true)' in orbit_branch, (
        "the orbit branch must switch to the planet projection"
    )
    assert "globalPlanetMesh" in script.split("function setOceanProjection")[1][:800], (
        "setOceanProjection must control the planet mesh"
    )


def test_local_mode_still_restores_the_flat_plane():
    """The human-scale view must not drift: flat plane on, planet off."""
    script = _get_prototype_script()

    local_branch = _extract_js_pattern(
        script,
        r'if \(globalOceanGlobe\.visible\) setOceanProjection\(false\);'
        r'.*?continentGroups\[cid\]\.position\.set\(0, 0, 0\)',
    )
    assert "setOceanProjection(false)" in local_branch, (
        "local mode must restore the flat ocean projection"
    )


def test_local_mode_restores_the_valley_sun_direction():
    """Orbit mode relights the planet; local mode must undo that exactly.

    The valley sun sits at (-95, 84, 55). If orbit mode moved it and local mode
    did not put it back, every human-scale view would inherit side-lighting from
    the globe camera -- a regression nobody would catch from the tests that only
    exercise the projection helpers.
    """
    script = _get_prototype_script()

    assert "LOCAL_SUN_POSITION" in script, (
        "the local sun direction must be captured as a named constant"
    )
    assert "sunLight.position.set(" in script, (
        "orbit mode must reposition the sun for the planet"
    )
    restore = _extract_js_pattern(
        script,
        r'if \(camera\.far !== 1600\) camera\.far = 1600;'
        r'.*?sunLight\.position\.set\(LOCAL_SUN_POSITION\.x, LOCAL_SUN_POSITION\.y'
    )
    assert "LOCAL_SUN_POSITION" in restore, (
        "local mode must restore the valley sun direction from the constant"
    )
    assert "sunLight.position.set(LOCAL_SUN_POSITION.x" in restore, (
        "local mode must write the restored sun direction back to the light"
    )
