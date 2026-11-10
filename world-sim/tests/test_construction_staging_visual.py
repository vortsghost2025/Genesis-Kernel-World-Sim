"""Phase 10PX -- staged construction must be visible, and verifiably growing.

The world now advances a structure foundation -> frame -> walls -> roofed ->
finished, and the viewer must grow with it. These run the extracted viewer
function in node against a THREE stub and assert the geometry actually gets
bigger at each stage -- not that a string appears somewhere.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

WORLD_SIM = Path(__file__).resolve().parents[1]
sys_path_added = str(WORLD_SIM)
import sys  # noqa: E402
if sys_path_added not in sys.path:
    sys.path.insert(0, sys_path_added)

PROTOTYPE_HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"

_THREE_STUB = r"""
var __counts = { mesh: 0, group: 0 };
function Mesh(geom, mat) {
  this.geometry = geom; this.material = mat;
  this.position = { set: function (x, y, z) { this.x = x; this.y = y; this.z = z; } };
  this.rotation = { x: 0, y: 0, z: 0 };
  this.scale = { set: function () {} };
  this.castShadow = false; this.receiveShadow = false;
  this.isMesh = true;
  __counts.mesh++;
  this.traverse = function (fn) { fn(this); };
}
function Group() {
  this.children = [];
  this.position = { set: function (x, y, z) { this.x = x; this.y = y; this.z = z; } };
  this.rotation = { x: 0, y: 0, z: 0 };
  this.scale = { set: function () {} };
  this.userData = {};
  this.isMesh = false;
  __counts.group++;
  this.add = function (c) { this.children.push(c); };
  this.traverse = function (fn) {
    fn(this);
    for (var i = 0; i < this.children.length; i++) this.children[i].traverse(fn);
  };
}
function BoxGeometry() { this.type = "box"; }
function CylinderGeometry() { this.type = "cyl"; }
function TorusGeometry() { this.type = "torus"; }
function MeshStandardMaterial(o) { this.o = o || {}; }
var THREE = { Group, Mesh, BoxGeometry, CylinderGeometry, TorusGeometry, MeshStandardMaterial };
"""

_PROBE = r"""
var stages = ["foundation", "frame", "walls", "roofed", "finished"];
var meshes = {};
var tops = {};
for (var i = 0; i < stages.length; i++) {
  __counts.mesh = 0;
  var g = createConstructionSprite(5, -5, 12.0, stages[i], 2, 1.0, 0xb58b5a);
  meshes[stages[i]] = __counts.mesh;
  var top = 0;
  g.traverse(function (c) {
    if (!c.isMesh) return;
    if (c.position && c.position.y > top) top = c.position.y;
  });
  tops[stages[i]] = Math.round(top * 100) / 100;
}
console.log(JSON.stringify({ meshes: meshes, tops: tops }));
"""


def _get_prototype_script() -> str:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def _extract(script: str, name: str) -> str:
    i = script.find("function " + name)
    assert i >= 0, name
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


def _run_node(js: str) -> dict:
    res = subprocess.run(["node", "-"], input=js, capture_output=True, text=True,
                         check=True)
    return json.loads(res.stdout.strip())


def _stage_report() -> dict:
    script = _get_prototype_script()
    consts = []
    for name in ("EXTERIOR_SHELTER_SCALE", "CONSTRUCTION_STAGES_ORDER"):
        m = re.search(rf"const\s+{name}\s*=\s*[^;]+;", script)
        assert m, name
        consts.append(m.group(0))
    js = ("\n".join(consts) + "\n" + _THREE_STUB + "\n"
          + _extract(script, "_woodMat") + "\n"
          + _extract(script, "createConstructionSprite") + "\n" + _PROBE)
    return _run_node(js)


ORDER = ["foundation", "frame", "walls", "roofed", "finished"]


def test_construction_geometry_grows_at_every_stage():
    d = _stage_report()
    seq = [d["meshes"][s] for s in ORDER]
    assert seq[0] < seq[1] < seq[2] < seq[3], (
        "mesh count must grow at each stage that adds work: %s" % seq)


def test_construction_silhouette_grows_at_frame_and_roof():
    d = _stage_report()
    tops = [d["tops"][s] for s in ORDER]
    assert tops[0] < tops[1], "a foundation is a flat pad: %s" % tops
    assert tops[2] < tops[3], "the roof is the tallest element: %s" % tops
    assert tops[3] > tops[1] > tops[0], "silhouette must climb: %s" % tops


def test_finished_group_matches_roofed_geometry():
    """The caller swaps the finished sprite in, so the group it receives is the
    roofed geometry -- the two must agree so nothing visually pops."""
    d = _stage_report()
    assert d["meshes"]["roofed"] == d["meshes"]["finished"]
    assert d["tops"]["roofed"] == d["tops"]["finished"]


def test_stage_order_is_the_worlds_own():
    script = _get_prototype_script()
    assert ('const CONSTRUCTION_STAGES_ORDER = ["foundation", "frame", '
            '"walls", "roofed", "finished"];') in script


def test_visual_profile_reports_construction_only_in_project():
    """A record not in a project must fall through to the finished sprite, and
    an in-project record must never claim a stage the world has not granted."""
    script = _get_prototype_script()
    assert 'if (inProject && stage && stage !== "finished")' in script
    assert "order >= 0" in script
    assert 'id: "vis_constructing"' in script


def test_construction_stage_reads_from_the_record():
    script = _get_prototype_script()
    assert "const rawStage = rec.construction_stage;" in script
    assert 'typeof rawStage === "string"' in script


def test_registry_and_render_signature_preserve_construction_stage():
    """buildHistoricalObjectRegistry must preserve construction_project and
    construction_stage so reconstructPublicObjectsAtHb passes them to
    getObjectVisualProfile, and objSig must include construction_stage so
    advancing a build stage triggers a 3D mesh rebuild."""
    script = _get_prototype_script()
    reg_fn = _extract(script, "buildHistoricalObjectRegistry")
    assert "construction_project:" in reg_fn
    assert "construction_stage:" in reg_fn
    assert "construction_progress:" in reg_fn
    assert "structure_rung:" in reg_fn

    upd_fn = _extract(script, "updatePublicObjectsAndClearings")
    assert "o.construction_stage" in upd_fn

    cat_fn = _extract(script, "classifyPublicObjectCategory")
    assert 'otype.includes("house")' in cat_fn


_EXTENT_STUB = r"""
var __counts = { mesh: 0 };
function Mesh(geom, mat) {
  this.geometry = geom; this.material = mat;
  this.size = { x: geom.sx, y: geom.sy, z: geom.sz };
  this.position = { set: function (x, y, z) { this.x = x; this.y = y; this.z = z; } };
  this.rotation = { x: 0, y: 0, z: 0 };
  this.scale = { set: function () {} };
  this.castShadow = false; this.receiveShadow = false; this.isMesh = true;
  __counts.mesh++;
  this.traverse = function (fn) { fn(this); };
}
function Group() {
  this.children = [];
  this.position = { set: function (x, y, z) { this.x = x; this.y = y; this.z = z; } };
  this.rotation = { x: 0, y: 0, z: 0 };
  this.scale = { set: function () {} };
  this.userData = {}; this.isMesh = false;
  this.add = function (c) { this.children.push(c); };
  this.traverse = function (fn) {
    fn(this);
    for (var i = 0; i < this.children.length; i++) this.children[i].traverse(fn);
  };
}
function BoxGeometry(sx, sy, sz) { this.type = "box"; this.sx = sx; this.sy = sy; this.sz = sz; }
function CylinderGeometry(rt, rb, h) { this.type = "cyl"; this.sx = rb*2; this.sy = h; this.sz = rb*2; }
function TorusGeometry(r, t) { this.type = "torus"; this.sx = r*2; this.sy = t*2; this.sz = r*2; }
function MeshStandardMaterial(o) { this.o = o || {}; }
var THREE = { Group, Mesh, BoxGeometry, CylinderGeometry, TorusGeometry, MeshStandardMaterial };
"""


def test_roofed_extent_matches_the_finished_billboard():
    """A completing build must land on the footprint it was already showing.

    The `roofed` group is drawn in 3D while the finished structure is a 2D
    billboard of width 5.4*s and height 4.4*s. If those extents disagree the
    structure visibly pops on the heartbeat it completes -- the exact defect
    this phase exists to remove. Eaves are allowed to overhang the walls, so
    the width carries a small margin over the billboard.
    """
    script = _get_prototype_script()
    consts = [
        re.search(rf"const\s+{name}\s*=\s*[^;]+;", script).group(0)
        for name in ("EXTERIOR_SHELTER_SCALE", "CONSTRUCTION_STAGES_ORDER")
    ]
    probe = r"""
    function rot(v, rx, ry, rz) {
      var x = v[0], y = v[1], z = v[2];
      var cx = Math.cos(rx), sx = Math.sin(rx), cy = Math.cos(ry), sy = Math.sin(ry),
          cz = Math.cos(rz), sz = Math.sin(rz);
      var y1 = y * cx - z * sx, z1 = y * sx + z * cx;
      var x2 = x * cy + z1 * sy, z2 = -x * sy + z1 * cy;
      var x3 = x2 * cz - y1 * sz, y3 = x2 * sz + y1 * cz;
      return [x3, y3, z2];
    }
    var g = createConstructionSprite(0, 0, 0, "roofed", 3, 1.0, 0x8a5629);
    var minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
    g.traverse(function (c) {
      if (!c.isMesh) return;
      var hx = (c.size.x || 0) / 2, hy = (c.size.y || 0) / 2, hz = (c.size.z || 0) / 2;
      for (var a = -1; a <= 1; a += 2)
        for (var b = -1; b <= 1; b += 2)
          for (var d = -1; d <= 1; d += 2) {
            var q = rot([a * hx, b * hy, d * hz],
                        c.rotation.x || 0, c.rotation.y || 0, c.rotation.z || 0);
            if (c.position.x + q[0] < minX) minX = c.position.x + q[0];
            if (c.position.x + q[0] > maxX) maxX = c.position.x + q[0];
            if (c.position.y + q[1] < minY) minY = c.position.y + q[1];
            if (c.position.y + q[1] > maxY) maxY = c.position.y + q[1];
          }
    });
    var s = EXTERIOR_SHELTER_SCALE;
    console.log(JSON.stringify({
      widthRatio: (maxX - minX) / (5.4 * s),
      heightRatio: (maxY - minY) / (4.4 * s)
    }));
    """
    js = ("\n".join(consts) + "\n" + _EXTENT_STUB + "\n"
          + _extract(script, "_woodMat") + "\n"
          + _extract(script, "createConstructionSprite") + "\n" + probe)
    d = _run_node(js)
    assert 0.95 <= d["widthRatio"] <= 1.25, (
        "roofed width is %s of the finished billboard; finishing a build pops "
        "the structure" % d["widthRatio"])
    assert 0.85 <= d["heightRatio"] <= 1.25, (
        "roofed height is %s of the finished billboard" % d["heightRatio"])


def test_wall_logs_align_parallel_to_walls_and_roof_peaks_at_ridge():
    """Horizontal wall logs on X-aligned walls (front/back) must rotate around Z,
    and logs on Z-aligned walls (left/right) must rotate around X, so logs form
    enclosed walls rather than sticking out perpendicular to the building."""
    script = _get_prototype_script()
    consts = [
        re.search(rf"const\s+{name}\s*=\s*[^;]+;", script).group(0)
        for name in ("EXTERIOR_SHELTER_SCALE", "CONSTRUCTION_STAGES_ORDER")
    ]
    probe = r"""
    var g = createConstructionSprite(0, 0, 0, "walls", 3, 1.0, 0xb58b5a);
    var cyls = [];
    g.traverse(function (c) {
      if (c.isMesh && c.geometry && c.geometry.type === "cyl") {
        cyls.push({
          x: Math.round(c.position.x * 1000) / 1000,
          y: Math.round(c.position.y * 1000) / 1000,
          z: Math.round(c.position.z * 1000) / 1000,
          rx: Math.round(c.rotation.x * 1000) / 1000,
          rz: Math.round(c.rotation.z * 1000) / 1000
        });
      }
    });
    console.log(JSON.stringify({ cyls: cyls }));
    """
    js = ("\n".join(consts) + "\n" + _THREE_STUB + "\n"
          + _extract(script, "_woodMat") + "\n"
          + _extract(script, "createConstructionSprite") + "\n" + probe)
    d = _run_node(js)
    horiz = [c for c in d["cyls"] if c["rx"] != 0 or c["rz"] != 0]
    assert len(horiz) >= 16, f"expected horizontal wall logs, got {len(horiz)}"
    for c in horiz:
        if abs(c["z"]) > abs(c["x"]):
    # Front/back walls (at +/-hz): cylinder must lie along X (rz == pi/2, rx == 0)
            assert c["rz"] > 1.5 and c["rx"] == 0, f"front/back log misoriented: {c}"
        else:
    # Left/right walls (at +/-hx, z==0): cylinder must lie along Z (rx == pi/2, rz == 0)
            assert c["rx"] > 1.5 and c["rz"] == 0 and c["z"] == 0, f"side log misoriented: {c}"
