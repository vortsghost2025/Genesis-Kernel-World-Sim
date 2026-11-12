"""Does the 10PZ viewer keep its crash-safety caps, and does the inline script parse?

A static gate on the deployed viewer: no antialiasing, pixel ratio 1,
no shadow map, low-power context, hidden-tab pause, and the staged
construction markers all present. Runs without a browser, so CI can
execute it cheaply.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

WORLD_SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD_SIM))

HTML = WORLD_SIM / "viewer" / "prototype" / "index.html"


def _script() -> str:
    html = HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert scripts, "prototype index.html must contain an inline script"
    return max(scripts, key=len)


def test_inline_script_parses():
    """Node's parser must accept the viewer script: a syntax error here is a
    dead page, which is the worst possible failure for an operator watching."""
    js = _script()
    # tmp_path is platform-native; a hardcoded 'S:\...' path would be handed
    # to node as a literal string with backslashes, which it URL-encodes and
    # then rejects as an unresolvable module specifier on POSIX runners.
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(js)
        out = Path(fh.name)
    try:
        res = subprocess.run(["node", "--check", str(out)],
                             capture_output=True, text=True)
        assert res.returncode == 0, "inline script syntax error:\n" + res.stderr[:1500]
    finally:
        out.unlink(missing_ok=True)


def test_crash_safety_caps_are_present():
    """Desktop GPUs were being driven to shutdown by this viewer.

    These five caps are what made it survivable; each is asserted directly so
    a future edit cannot quietly remove one and ship a machine-killer again.
    """
    js = _script()
    assert "antialias: false" in js, "antialiasing must stay off"
    assert "powerPreference: \"low-power\"" in js, (
        "the WebGL context must request low-power")
    assert "renderer.setPixelRatio(1);" in js, (
        "pixel ratio must stay at 1.0 -- 2x Hi-DPI upscaling doubled fill cost"
    )
    assert "renderer.shadowMap.enabled = false;" in js, (
        "shadow maps must stay off")
    assert "sunLight.castShadow = false;" in js, (
        "the sun must not cast shadows")
    assert "if (document.hidden) {" in js and "return;" in js.split("if (document.hidden) {")[1][:200], (
        "the render loop must do no work while the tab is hidden")


def test_staged_construction_markers_are_present():
    """The 10PW/10PX/10PZ chain put construction stages into the world; the
    viewer must still be wired to draw them."""
    js = _script()
    assert "function createConstructionSprite" in js
    assert 'const CONSTRUCTION_STAGES_ORDER = ["foundation", "frame", "walls", "roofed", "finished"];' in js
    assert 'vis_constructing' in js
    assert 'getHomeRungReport()' in js
    # the registry must pass the construction fields through to the renderer
    assert "construction_stage:" in _extract(js, "buildHistoricalObjectRegistry")
    # and the rebuild signature must include the stage
    assert "o.construction_stage" in _extract(js, "updatePublicObjectsAndClearings")


def _extract(src: str, name: str) -> str:
    i = src.find("function " + name)
    assert i >= 0, name
    j = src.find("{", i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[i:k + 1]


def test_orbit_mode_is_the_only_globe_surface():
    """Local detail meshes must never render over the planet sphere.

    The defect that produced the 'blue square' over the globe was the local
    terrain groups being offset 125 units off-centre and left visible.
    """
    js = _script()
    start = js.find('if (pairName === "orbit") {')
    assert start > 0
    end = js.find('applyCameraMode("orbit", true);', start)
    branch = js[start:end]
    for group in ("continentGroups.cont_a.visible = false;",
                  "continentGroups.cont_b.visible = false;",
                  "sceneryGroups.cont_a.visible = false;",
                  "objectGroups.cont_a.visible = false;"):
        assert group in branch, group
    assert "position.set(-125, 0, 0)" not in js, (
        "the stale side-by-side offset must not return")
