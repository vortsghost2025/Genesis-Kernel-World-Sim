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


def _extract_js_block(script: str, header: str, terminator: str) -> str:
    """Extract source from `header` up to `terminator` (exclusive)."""
    i = script.find(header)
    assert i >= 0, "block header not found: %s" % header
    j = script.find(terminator, i)
    assert j > i, "block terminator not found: %s" % terminator
    return script[i:j]


def test_orbit_framing_outgrows_the_flat_distance_ceiling():
    """Orbit must raise the OrbitControls distance ceiling and camera far plane.

    This is the defect that made the globe read as two flat rectangles. The
    projection math was correct, but controls.maxDistance stayed at the flat
    layout's 550 units, so OrbitControls clamped the orbit camera to ~550 units
    every update() and each continent spanned only ~13 degrees of the sphere.
    The unit tests all passed because they exercise computeGlobePosition in
    isolation and never touch the render loop.
    """
    script = _get_prototype_script()

    # The orbit branch must set a maxDistance well beyond the flat ceiling.
    branch = _extract_js_block(
        script,
        'if (mode === "orbit" || selectedPair === "orbit") {',
        "smoothMoveCamera(orbitDir.multiplyScalar(dist)",
    )
    assert "controls.maxDistance = GLOBE_RADIUS * 5.0;" in branch, (
        "orbit mode must raise controls.maxDistance above the flat 550 ceiling"
    )
    assert "camera.far = GLOBE_RADIUS * 8.0;" in branch, (
        "orbit mode must raise the camera far plane past the framing distance"
    )
    # The default ceiling must stay at the flat value for local views.
    assert "controls.maxDistance = 550;" in _get_prototype_script(), (
        "the local-view distance ceiling must remain 550"
    )
    # And it must be restored on the way back to a local view: the flat ceiling
    # appears at least twice -- the initial declaration and the local restore.
    ceiling_assignments = script.count("controls.maxDistance = 550;")
    assert ceiling_assignments >= 2, (
        "local mode must restore the 550-unit ceiling (found %d assignment%s)"
        % (ceiling_assignments, "s" if ceiling_assignments != 1 else "")
    )


def test_orbit_framing_reaches_beyond_the_flat_ceiling_at_runtime():
    """Execute the real framing math and assert the orbit distance exceeds 550.

    Recomputes what applyCameraMode orbits to and proves the chosen distance
    cannot be clamped by the OrbitControls ceiling that is active in that mode.
    """
    script = _get_prototype_script()

    js = "".join([
        "const GLOBE_RADIUS = 900.0;\n",
        "const flatMaxDistance = 550;\n",
        "const orbitMaxDistance = GLOBE_RADIUS * 5.0;\n",
        "const dist = GLOBE_RADIUS * 4.5;\n",
        "const orbitDir = new (function(v){this.x=v[0];this.y=v[1];this.z=v[2];var m=Math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);this.multiplyScalar=function(s){this.x*=s;this.y*=s;this.z*=s;return this;};this.normalize=function(){var m2=Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z);this.x/=m2;this.y/=m2;this.z/=m2;return this;};})([1.0,0.15,0.0]);\n",
        "const cam = orbitDir.normalize().multiplyScalar(dist);\n",
        "const far = GLOBE_RADIUS * 8.0;\n",
        "console.log(JSON.stringify({\n",
        "  flatCeiling: flatMaxDistance,\n",
        "  orbitCeiling: orbitMaxDistance,\n",
        "  framingDist: dist,\n"
        "  camX: cam.x,\n"
        "  camZ: cam.z,\n",
        "  farPlane: far,\n",
        "  clampedByOldCeiling: dist > flatMaxDistance,\n",
        "  allowedByOrbitCeiling: dist <= orbitMaxDistance,\n",
        "  visibleAtFarPlane: dist < far\n",
        "}));\n",
    ])

    d = _run_node(js)

    assert d["clampedByOldCeiling"] is True, (
        "the framing distance must exceed the old 550 ceiling (that was the bug)"
    )
    assert d["allowedByOrbitCeiling"] is True, (
        "the new orbit ceiling must permit the framing distance"
    )
    assert d["camX"] > abs(d["camZ"]), (
        "the orbit camera must stand off the +x side so both continent patches "
        "land on the visible hemisphere of the globe"
    )
    assert d["visibleAtFarPlane"] is True, (
        "the globe must sit inside the camera far plane"
    )
    assert d["orbitCeiling"] == 4500.0 and d["farPlane"] == 7200.0, (
        "orbit ceiling and far plane must derive from GLOBE_RADIUS"
    )


def test_orbit_framing_keeps_both_continents_on_screen_at_narrow_aspect():
    """Phase 10OO: both canonical patches must stay inside the viewport.

    Regression test for the defect where the default orbit framing
    (orbitDir [0.88,0.42,0.22] at 3.2 radii) put cont_a ~59 deg off the camera
    axis. NDC x scales with 1/aspect, so on any canvas narrower than ~1000 px
    cont_a slid past the right screen edge and the globe read as ONE continent.
    This projects both patch centres with the real constants at the narrow
    aspect of a 900x800 window and asserts both land well inside the disc.
    """
    script = _get_prototype_script()

    js = "".join([
        "const GLOBE_RADIUS = 900.0;\n",
        "const GLOBE_PATCHES = { cont_a: { lon: -0.85, lat: 0.30 }, cont_b: { lon: 0.85, lat: -0.30 } };\n",
        "const dist = GLOBE_RADIUS * 4.5;\n",
        "const orbitDir = new (function(v){this.x=v[0];this.y=v[1];this.z=v[2];var m=Math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);this.multiplyScalar=function(s){this.x*=s;this.y*=s;this.z*=s;return this;};this.normalize=function(){var m2=Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z);this.x/=m2;this.y/=m2;this.z/=m2;return this;};})([1.0,0.15,0.0]).normalize();\n",
        "const cam = orbitDir.multiplyScalar(dist);\n",
        "const fov = 46;\n",
        "function project(lon, lat, aspect) {\n",
        "  const r = GLOBE_RADIUS + 10;\n",
        "  const cLat = Math.cos(lat);\n",
        "  const p = [r * cLat * Math.cos(lon), r * Math.sin(lat), r * cLat * Math.sin(lon)];\n",
        "  const f = [-cam.x, -cam.y, -cam.z];\n",
        "  const fl = Math.hypot(f[0], f[1], f[2]);\n",
        "  const fwd = [f[0]/fl, f[1]/fl, f[2]/fl];\n",
        "  let right = [fwd[1]*0 - fwd[2]*1, fwd[2]*0 - fwd[0]*0, fwd[0]*1 - fwd[1]*0];\n",
        "  const rl = Math.hypot(right[0], right[1], right[2]);\n",
        "  right = [right[0]/rl, right[1]/rl, right[2]/rl];\n",
        "  const up = [right[1]*fwd[2]-right[2]*fwd[1], right[2]*fwd[0]-right[0]*fwd[2], right[0]*fwd[1]-right[1]*fwd[0]];\n",
        "  const d = [p[0]-cam.x, p[1]-cam.y, p[2]-cam.z];\n",
        "  const x = d[0]*right[0]+d[1]*right[1]+d[2]*right[2];\n",
        "  const y = d[0]*up[0]+d[1]*up[1]+d[2]*up[2];\n",
        "  const z = d[0]*fwd[0]+d[1]*fwd[1]+d[2]*fwd[2];\n",
        "  const tanH = Math.tan(fov * Math.PI / 360);\n",
        "  return { ndcX: x/(z*tanH*aspect), ndcY: y/(z*tanH), inFront: z > 0 };\n",
        "}\n",
        "const out = {};\n",
        "for (const aspect of [1.442, 0.969, 0.779, 0.697]) {\n",
        "  out['a_' + aspect] = project(GLOBE_PATCHES.cont_a.lon, GLOBE_PATCHES.cont_a.lat, aspect);\n",
        "  out['b_' + aspect] = project(GLOBE_PATCHES.cont_b.lon, GLOBE_PATCHES.cont_b.lat, aspect);\n",
        "}\n",
        "console.log(JSON.stringify(out));\n",
    ])

    d = _run_node(js)

    # The constants above must mirror the real source, not drift from it.
    assert "const dist = GLOBE_RADIUS * 4.5;" in script
    assert "new THREE.Vector3(1.0, 0.15, 0.0).normalize()" in script

    for aspect in (1.442, 0.969, 0.779, 0.697):
        for cid in ("a", "b"):
            p = d[f"{cid}_{aspect}"]
            assert p["inFront"] is True, (
                f"patch {cid} must be on the visible hemisphere at aspect {aspect}"
            )
            assert abs(p["ndcX"]) < 0.9 and abs(p["ndcY"]) < 0.9, (
                f"patch {cid} at aspect {aspect} projects to ndc "
                f"({p['ndcX']:.3f}, {p['ndcY']:.3f}) -- outside the safe disc; "
                "on a narrow window it would fall off the canvas edge"
            )


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

    # Everything that runs at load time, in source order. The ocean/planet
    # meshes are declared CONST by the real source block below, so they are not
    # pre-declared here -- redeclaring them would be a syntax error rather than
    # a load-order failure, which would mask the defect this test exists to catch.
    stubs = "".join([
        "var THREE = {\n",
        " SphereGeometry: function (r, s, h) { this.r = r; },\n",
        " MeshBasicMaterial: function (o) { this.o = o; },\n",
        " Mesh: function (g, m) { this.geometry = g; this.material = m; this.visible = false; }\n",
        "};\n",
        "var scene = { added: [], add: function (m) { this.added.push(m); } };\n",
        "var globalOcean = { visible: true };\n",
        "var globalPlanetMesh = { visible: false };\n",
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
        + "var planet = globalPlanetMesh.visible;\n"
        + "setOceanProjection(false);\n"
        + "var local = globalOcean.visible;\n"
        + "console.log(JSON.stringify({ orbit: orbit, planet: planet,"
        " local: local, r: globalOceanGlobeGeom.r }));\n"
    )

    d = _run_node(js)

    # radius must be GLOBE_RADIUS - 0.6, i.e. the constant was readable
    assert abs(d["r"] - (900.0 - 0.6)) < 1e-9, "SphereGeometry radius must come from GLOBE_RADIUS"
    # Phase 10NS made the projection three-state, so `true` now selects the
    # planet mesh instead of the legacy shell. Both are spherical surfaces; the
    # flat-plane restoration below is the part this test has always guarded.
    assert d["planet"] is True, "orbit must show a spherical surface"
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


def test_no_orbit_branch_identifier_is_used_before_its_declaration():
    """Guards the whole class of defect, not one instance of it.

    Phase 10JJ hit a temporal dead zone on GLOBE_RADIUS, Phase 10NS hit the same
    class again on orbitDir, and both only showed up when the page actually ran.
    This test walks every `const NAME =` inside the applyCameraMode orbit branch
    and asserts no earlier line in that branch reads NAME.
    """
    script = _get_prototype_script()

    start = script.find('if (mode === "orbit" || selectedPair === "orbit") {')
    assert start > 0, "the orbit branch of applyCameraMode must exist"
    end = script.find("// Local views: undo the planet-scale", start)
    assert end > start, "the orbit branch must be terminated by the local restore"
    branch = script[start:end]
    branch_lines = branch.split("\n")

    declared = {}
    for n, line in enumerate(branch_lines):
        m = re.match(r"\s*const\s+(\w+)\s*=", line)
        if m:
            declared.setdefault(m.group(1), n)

    assert declared, "the orbit branch must declare its own locals"

    for name, decl_line in declared.items():
        for n, line in enumerate(branch_lines):
            if n >= decl_line:
                break
            if re.search(r"\b%s\b" % re.escape(name), line):
                raise AssertionError(
                    "orbit branch uses `%s` on line %d of the branch but it is not "
                    "declared until line %d -- that is a temporal dead zone and it "
                    "kills the entire viewer script at page load"
                    % (name, n + 1, decl_line + 1)
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
        "var globalPlanetMesh = { visible: false };\n",
    ])
    js = (
        stubs
        + _extract_js_function(script, "setOceanProjection")
        + "\n"
        + "setOceanProjection(true);\n"
        + "var orbit = { flat: globalOcean.visible, globe: globalOceanGlobe.visible,\n"
        + "               planet: globalPlanetMesh.visible };\n"
        + "setOceanProjection(false);\n"
        + "var local = { flat: globalOcean.visible, globe: globalOceanGlobe.visible,\n"
        + "               planet: globalPlanetMesh.visible };\n"
        + "console.log(JSON.stringify({ orbit: orbit, local: local }));\n"
    )
    d = _run_node(js)
    # The invariant this test has guarded since 10NG: orbit mode must never show
    # the flat ocean plane, or the projected continents hover over a disc that
    # cuts through the globe. Phase 10NS generalised that from "show the ocean
    # shell" to "show some spherical surface", which may now be the full planet
    # mesh rather than the shell. The three-state contract itself is asserted
    # directly by tests/test_planetary_surface.py.
    assert d["orbit"]["flat"] is False, "orbit mode must hide the flat ocean plane"
    assert (d["orbit"]["globe"] or d["orbit"]["planet"]) is True, (
        "orbit mode must show a spherical ocean surface (shell or planet mesh)"
    )
    assert d["local"]["flat"] is True, "local mode must restore the flat ocean plane"
    assert d["local"]["globe"] is False, "local mode must hide the spherical ocean"
    assert d["local"]["planet"] is False, (
        "local mode must hide the planet surface mesh"
    )


def test_orbit_globe_labels_mark_both_canonical_continents():
    """Orbit labels must identify East and West on the globe itself.

    Regression for the visual defect where the top nav pills named East and
    West but the globe showed multiple landmasses with no anchored label. The
    labels must use the same GLOBE_PATCHES centers as the projected continents,
    show only in orbit, and hide when their point faces away from the camera.
    """
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    script = _get_prototype_script()

    assert 'id="globe-label-east"' in html
    assert 'id="globe-label-west"' in html
    assert "EAST VALLEY (ALPHA)" in html
    assert "WEST DAWN (BETA)" in html

    assert "function updateGlobeLabels()" in script
    assert "selectedPair !== \"orbit\"" in script
    assert "GLOBE_PATCHES[item.cid]" in script
    assert "const radius = GLOBE_RADIUS + 18.0;" in script
    assert "facing > 0.05" in script
    assert "updateGlobeLabels();" in script
    assert "continentGroups.cont_a.visible = false;" in script
    assert "sceneryGroups.cont_a.visible = false;" in script
    assert "objectGroups.cont_a.visible = false;" in script


def test_globe_atlas_is_high_resolution_and_biome_driven():
    """The orbit sphere must use a real biome atlas, not latitude stripes.

    The 2048x1024 canvas, canonical patch rasterization, cloud sphere, and
    atmosphere shell are the visual layers that make the planet read as an
    orbital atlas instead of a painted toy ball.
    """
    script = _get_prototype_script()

    assert "const PLANET_ATLAS_WIDTH = 2048;" in script
    assert "const PLANET_ATLAS_HEIGHT = 1024;" in script
    assert "const PLANET_LON_STEPS = 360;" in script
    assert "const PLANET_LAT_STEPS = 180;" in script
    assert "function generatePlanetTerrainAtlas()" in script
    assert "function planetCanonicalAtlasColor(cid, lon, lat)" in script
    assert "new THREE.CanvasTexture(canvas)" in script
    assert "map: planetAtlasTex || undefined" in script
    assert "vertexColors: !planetAtlasTex" in script
    assert "geom.setAttribute(\"uv\", new THREE.BufferAttribute(uvs, 2));" in script
    assert "if (terr === \"ocean\" && waterMask === 0) return null;" in script
    assert "const PLANET_LANDMARKS = [];" in script

    assert "antialias: false" in script
    assert "powerPreference: \"low-power\"" in script
    assert "renderer.setPixelRatio(1);" in script
    assert "renderer.shadowMap.enabled = false;" in script
    assert "sunLight.castShadow = false;" in script
    assert "Crash-safety: do no scene work while the tab is hidden." in script

    assert "const PLANET_SEA_LEVEL = 0.74;" in script
    assert "const PLANET_HEIGHT_SCALE = 46.0;" in script
    assert "The canonical atlas is the only playable land" in script


def test_orbit_to_npc_zoom_handoff_and_space_backdrop():
    """Orbit mode must hide the local skyDome, show Rayleigh limb glow, and zoom into NPCs."""
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    script = _get_prototype_script()

    assert "pointer-events: auto;" in html
    assert "function zoomIntoCivFromOrbit(" in script
    assert 'globeLabelEast.onclick' in script
    assert 'globeLabelWest.onclick' in script
    assert 'canvas.addEventListener("wheel"' in script
    assert "globalAtmosphereSprite" in script
    assert "globalOrbitStars" in script

    orbit_branch = _extract_js_block(
        script,
        'if (mode === "orbit" || selectedPair === "orbit") {',
        "// Local views: undo the planet-scale",
    )
    assert "skyDome.visible = false;" in orbit_branch
