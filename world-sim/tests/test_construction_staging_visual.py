"""Phase 10PX — staged construction must be visible, and verifiably growing.

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
